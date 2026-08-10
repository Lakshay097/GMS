"""
E2E: Compliance Scheduler → Grace Period → Scorecard (v1.5).

Incremental coverage beyond BR-24/BR-26 unit tests:
  BR-24 timezone/backfill tests exercise scheduler → compliance shells.
  BR-26 / FR-263–264 grace tests exercise late flag + reopen, not scorecard.
  This E2E chains those into ScorecardService.generate() — a separate trigger
  (scorecard does NOT auto-run after grace closure).
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import uuid
import pytest
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from modules.observation_capture.services.observation_service import ObservationService
from modules.kra_kpi_library.services.kpi_service import KpiService
from modules.kra_kpi_library.services.kra_service import KraService
from modules.performance_scorecards.services.scorecard_service import ScorecardService
from platform_services.compliance_scheduler.service import ComplianceScheduler
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.configuration_engine.constants import ConfigKey
from platform_services.rule_engine.service import RuleEngine
from platform_services.rule_engine.strategies import WorstStatusWinsStrategy
from shared.platform_models import (
    ComplianceObservation,
    ComplianceStatus,
    ScorecardSubjectType,
    AutoResult,
    RagStatus,
)
from shared.datetime_utils import utc_now
from shared.models import User


class StubNotificationService:
    def __init__(self):
        self.dispatched: list[dict] = []

    async def dispatch(self, payload) -> uuid.UUID:
        self.dispatched.append({
            "user_id": payload.user_id,
            "category": payload.category,
            "title": payload.title,
        })
        return uuid.uuid4()


def _build_services(db):
    config_engine = ConfigurationEngine(db)
    rule_engine = RuleEngine()
    rule_engine.register_strategy(WorstStatusWinsStrategy())
    notification_service = StubNotificationService()
    return {
        "config_engine": config_engine,
        "rule_engine": rule_engine,
        "notification_service": notification_service,
        "kra_service": KraService(db),
        "kpi_service": KpiService(
            db,
            config_engine=config_engine,
            rule_engine=rule_engine,
            notification_service=notification_service,
        ),
        "observation_service": ObservationService(
            db,
            config_engine=config_engine,
            rule_engine=rule_engine,
            notification_service=notification_service,
        ),
        "scorecard_service": ScorecardService(
            db,
            rule_engine=rule_engine,
            notification_service=notification_service,
        ),
        "compliance_scheduler": ComplianceScheduler(db),
    }


async def _shell_for_kpi(db, kpi_id) -> ComplianceObservation:
    result = await db.execute(
        select(ComplianceObservation).where(ComplianceObservation.kpi_id == kpi_id)
    )
    shell = result.scalars().first()
    assert shell is not None, f"Expected compliance shell for KPI {kpi_id}"
    return shell


@pytest.mark.asyncio
async def test_e2e_scheduler_grace_period_scorecard(db, school, department, seed_configuration):
    """
    Full chain:
      1. Scheduler computes due_at + grace_period_elapsed_at (observation window opens)
      2. On-time submission for KPI A
      3. Late submission within grace for KPI B (grace-period recovered)
      4. Grace elapses with no submission for KPI C → CLOSED_MISSED via sweep
      5. Separate ScorecardService.generate() reflects A (GREEN) + B (AMBER late)
    """
    now = utc_now()
    checker = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="checker-grace-sc@test.com",
        full_name="Grace Checker",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=now,
        updated_at=now,
    )
    db.add(checker)
    await db.commit()

    services = _build_services(db)
    config_engine = services["config_engine"]
    kra_service = services["kra_service"]
    kpi_service = services["kpi_service"]
    observation_service = services["observation_service"]
    scorecard_service = services["scorecard_service"]
    scheduler = services["compliance_scheduler"]
    notifications = services["notification_service"]

    # Grace window: 2 hours after due_at
    await config_engine.set_global(ConfigKey.GRACE_PERIOD_HOURS, 2)
    assert await config_engine.get(ConfigKey.GRACE_PERIOD_HOURS) == 2

    kra = await kra_service.create_kra(
        name="Daily Compliance Chain",
        description="Scheduler → grace → scorecard E2E",
    )

    kpi_ontime = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="On-Time Safety Check",
        target_value=Decimal("100.0"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        amber_tolerance_band=Decimal("5.0"),
    )
    kpi_late = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="Late-Recovered Attendance",
        target_value=Decimal("100.0"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        amber_tolerance_band=Decimal("5.0"),
    )
    kpi_missed = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="Missed After Grace",
        target_value=Decimal("100.0"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        amber_tolerance_band=Decimal("5.0"),
    )

    # STEP 1: Scheduler opens observation windows (due_at + grace_period_elapsed_at)
    run_result = await scheduler.run(as_of=now)
    assert run_result.records_generated >= 3

    shell_ontime = await _shell_for_kpi(db, kpi_ontime.kpi_id)
    shell_late = await _shell_for_kpi(db, kpi_late.kpi_id)
    shell_missed = await _shell_for_kpi(db, kpi_missed.kpi_id)

    assert shell_ontime.due_at is not None
    assert shell_ontime.grace_period_elapsed_at is not None
    assert shell_ontime.grace_period_elapsed_at == shell_ontime.due_at + timedelta(hours=2)
    assert shell_ontime.compliance_status == ComplianceStatus.OPEN

    # STEP 2: On-time submission (within due window)
    on_time_obs = await observation_service.submit_observation(
        kpi_id=kpi_ontime.kpi_id,
        kpi_version=kpi_ontime.version,
        checker_id=checker.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("100.0"),
        is_late=False,
        submission_token=uuid.uuid4(),
    )
    assert on_time_obs.is_late is False
    assert on_time_obs.auto_result == AutoResult.MET
    assert on_time_obs.rag_status == RagStatus.GREEN
    shell_ontime.compliance_status = ComplianceStatus.SUBMITTED
    await db.flush()

    # STEP 3: Late but within grace — adjust shell so due has passed, grace has not
    shell_late.due_at = now - timedelta(hours=1)
    shell_late.grace_period_elapsed_at = now + timedelta(hours=1)
    shell_late.compliance_status = ComplianceStatus.LATE_SUBMITTABLE
    await db.flush()
    assert now < shell_late.grace_period_elapsed_at

    late_obs = await observation_service.submit_observation(
        kpi_id=kpi_late.kpi_id,
        kpi_version=kpi_late.version,
        checker_id=checker.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("100.0"),  # meets target; late → AMBER RAG
        is_late=True,
        submission_token=uuid.uuid4(),
    )
    assert late_obs.is_late is True
    assert late_obs.auto_result == AutoResult.MET
    assert late_obs.rag_status == RagStatus.AMBER
    shell_late.compliance_status = ComplianceStatus.SUBMITTED
    await db.flush()

    # Late submission notifies checker (grace-period recovered path)
    late_notifs = [
        n for n in notifications.dispatched
        if n["user_id"] == checker.id and n["title"] == "Late Observation Submitted"
    ]
    assert len(late_notifs) >= 1

    # STEP 4: Separate case — grace elapses with no submission → CLOSED_MISSED
    shell_missed.due_at = now - timedelta(hours=5)
    shell_missed.grace_period_elapsed_at = now - timedelta(hours=1)
    shell_missed.compliance_status = ComplianceStatus.LATE_SUBMITTABLE
    await db.flush()

    closed_count = await scheduler.sweep_grace_periods(as_of=now)
    assert closed_count >= 1
    await db.refresh(shell_missed)
    assert shell_missed.compliance_status == ComplianceStatus.CLOSED_MISSED

    # STEP 5: Scorecard is a SEPARATE trigger (does not auto-follow grace closure)
    cycle_start = (now - timedelta(days=1)).date()
    cycle_end = now.date()
    scorecard = await scorecard_service.generate(
        subject_type=ScorecardSubjectType.USER,
        subject_id=checker.id,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
    )

    assert scorecard.id is not None
    assert scorecard.version == 1
    # Worst-status-wins across GREEN (on-time) + AMBER (late-recovered) → AMBER
    assert scorecard.rag_status == RagStatus.AMBER
    # Only the on-time KPI counts as "met"; late-recovered is amber
    assert scorecard.pct_kpis_met == Decimal("50.00")

    by_kpi = {item["kpi_id"]: item["rag_status"] for item in scorecard.kpi_breakdown}
    assert by_kpi[str(kpi_ontime.kpi_id)] == RagStatus.GREEN.value
    assert by_kpi[str(kpi_late.kpi_id)] == RagStatus.AMBER.value
    # Missed shell has no Observation — does not appear in scorecard breakdown
    assert str(kpi_missed.kpi_id) not in by_kpi
