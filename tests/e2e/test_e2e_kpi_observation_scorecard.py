"""
End-to-end test for KPI â Observation â Scorecard workflow.

Uses real KraService / KpiService / ObservationService / ScorecardService.
Scorecard generation is synchronous via ScorecardService.generate()
(ScorecardScheduler exists for periodic/review-driven jobs, but is not
required for ad-hoc generation from observation data).
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import pytest

# Module removed - skip entire test file (must be before importing from it)
pytest.importorskip("modules.performance_scorecards", reason="performance_scorecards module removed")

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func

from modules.observation_capture.services.observation_service import ObservationService
from modules.kra_kpi_library.services.kpi_service import KpiService
from modules.kra_kpi_library.services.kra_service import KraService
from modules.performance_scorecards.services.scorecard_service import ScorecardService
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.rule_engine.service import RuleEngine
from platform_services.rule_engine.strategies import WorstStatusWinsStrategy
from shared.platform_models import (
    Observation,
    ScorecardSubjectType,
    AutoResult,
    RagStatus,
    KpiCaptureType,
)
from shared.datetime_utils import utc_now
from shared.models import User

# Module removed  skip entire test file
pytest.importorskip("modules.performance_scorecards", reason="performance_scorecards module removed")



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
    }


@pytest.mark.asyncio
async def test_e2e_kpi_observation_scorecard(db, school, department, seed_configuration):
    """
    Happy path: KPI create/retrieve â observations with real RAG â scorecard.

    Workflow:
    1. KRA + KPI created (amber band 5%)
    2. KPI retrieved via get_current_kpi
    3. Green / amber / red observations submitted against that KPI
    4. Scorecard generated synchronously via ScorecardService.generate()
    5. Scorecard RAG = worst-status-wins (RED), pct_kpis_met reflects unmet KPI
    """
    checker = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="checker-kpi-sc@test.com",
        full_name="Data Checker",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(checker)
    await db.commit()

    services = _build_services(db)
    kra_service = services["kra_service"]
    kpi_service = services["kpi_service"]
    observation_service = services["observation_service"]
    scorecard_service = services["scorecard_service"]

    # STEP 1: Create KRA
    kra = await kra_service.create_kra(
        name="Academic Excellence",
        description="Measure of academic performance and quality",
    )
    assert kra.id is not None
    assert kra.name == "Academic Excellence"
    assert kra.status == "active"

    # STEP 2: Create KPI with thresholds (amber band 5% â matches config default)
    kpi = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="Student Attendance Rate",
        target_value=Decimal("95.0"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        amber_tolerance_band=Decimal("5.0"),
    )
    assert kpi.kpi_id is not None
    assert kpi.title == "Student Attendance Rate"
    assert kpi.target_value == Decimal("95.0")
    assert kpi.comparator == ">="
    assert kpi.amber_tolerance_band == Decimal("5.0")
    assert kpi.status == "active"

    # STEP 3: Retrieve current KPI version
    retrieved = await kpi_service.get_current_kpi(kpi.kpi_id)
    assert retrieved.kpi_id == kpi.kpi_id
    assert retrieved.version == kpi.version
    assert retrieved.title == "Student Attendance Rate"

    # STEP 4: Submit green / amber / red observations
    # target=95, comparator>=, amber_band=5%:
    #   96.5 â GREEN/MET (meets)
    #   92.0 â AMBER/NOT_MET (within 5% of target, does not meet)
    #   80.0 â RED/NOT_MET (outside amber band)
    cases = [
        (Decimal("96.5"), AutoResult.MET, RagStatus.GREEN),
        (Decimal("92.0"), AutoResult.NOT_MET, RagStatus.AMBER),
        (Decimal("80.0"), AutoResult.NOT_MET, RagStatus.RED),
    ]
    observations = []
    for value, expected_auto, expected_rag in cases:
        observation = await observation_service.submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=checker.id,
            department_id=department.id,
            school_id=school.id,
            value_numeric=value,
            asset_id=uuid.uuid4(),
            submission_token=uuid.uuid4(),
        )
        observations.append(observation)
        assert observation.id is not None
        assert observation.value_numeric == value
        assert observation.kpi_id == kpi.kpi_id
        assert observation.kpi_version == kpi.version
        assert observation.auto_result == expected_auto, (
            f"value={value}: expected auto_result={expected_auto}, got {observation.auto_result}"
        )
        assert observation.rag_status == expected_rag, (
            f"value={value}: expected rag_status={expected_rag}, got {observation.rag_status}"
        )

    observation_count = await db.scalar(
        select(func.count()).select_from(Observation).where(
            Observation.kpi_id == kpi.kpi_id
        )
    )
    assert observation_count == 3

    # STEP 5: Generate scorecard synchronously (manual/ad-hoc trigger)
    cycle_start = date.today() - timedelta(days=7)
    cycle_end = date.today()

    scorecard = await scorecard_service.generate(
        subject_type=ScorecardSubjectType.USER,
        subject_id=checker.id,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
    )

    assert scorecard.id is not None
    assert scorecard.subject_type == ScorecardSubjectType.USER
    assert scorecard.subject_id == checker.id
    assert scorecard.cycle_start == cycle_start
    assert scorecard.cycle_end == cycle_end
    assert scorecard.version == 1
    assert scorecard.superseded_by_id is None

    # STEP 6: Worst-status-wins across green+amber+red â RED; KPI not met â 0%
    assert scorecard.rag_status == RagStatus.RED, (
        f"Expected RED (worst-status-wins) but got {scorecard.rag_status}"
    )
    assert scorecard.pct_kpis_met == Decimal("0.00"), (
        f"Expected 0.00 but got {scorecard.pct_kpis_met}"
    )
    assert scorecard.kpi_breakdown is not None
    assert len(scorecard.kpi_breakdown) == 1
    breakdown = scorecard.kpi_breakdown[0]
    assert breakdown.get("kpi_id") == str(kpi.kpi_id)
    assert breakdown.get("rag_status") == RagStatus.RED.value

    # STEP 7: All-green second cycle proves GREEN + pct_kpis_met=100 path
    green_checker = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="checker-green@test.com",
        full_name="Green Checker",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(green_checker)
    await db.commit()

    for value in (Decimal("96.0"), Decimal("97.5"), Decimal("99.0")):
        await observation_service.submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=green_checker.id,
            department_id=department.id,
            school_id=school.id,
            value_numeric=value,
            asset_id=uuid.uuid4(),
            submission_token=uuid.uuid4(),
        )

    green_scorecard = await scorecard_service.generate(
        subject_type=ScorecardSubjectType.USER,
        subject_id=green_checker.id,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
    )
    assert green_scorecard.rag_status == RagStatus.GREEN
    assert green_scorecard.pct_kpis_met == Decimal("100.00")
    assert green_scorecard.kpi_breakdown[0]["rag_status"] == RagStatus.GREEN.value


@pytest.mark.asyncio
async def test_e2e_observation_without_kpi_link_fails(db, school, department, seed_configuration):
    """Failure path: observation without a valid KPI link is rejected (R-23/BR-20)."""
    checker = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="checker-nokpi@test.com",
        full_name="Data Checker",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(checker)
    await db.commit()

    services = _build_services(db)
    observation_service = services["observation_service"]

    with pytest.raises(Exception) as exc_info:
        await observation_service.submit_observation(
            kpi_id=uuid.uuid4(),
            kpi_version=1,
            checker_id=checker.id,
            department_id=department.id,
            school_id=school.id,
            value_numeric=Decimal("95.0"),
        )

    assert "kpi" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_e2e_observation_invalid_value_fails(db, school, department, seed_configuration):
    """Failure path: VALUE_READING KPI rejects missing numeric value."""
    checker = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="checker-badval@test.com",
        full_name="Data Checker",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(checker)
    await db.commit()

    services = _build_services(db)
    kra = await services["kra_service"].create_kra(
        name="Test KRA Invalid Value",
        description="Test description",
    )
    kpi = await services["kpi_service"].create_kpi(
        kra_id=kra.id,
        title="Test KPI",
        target_value=Decimal("100.0"),
        comparator=">=",
        unit_of_measure="count",
        frequency_code="daily",
        capture_type=KpiCaptureType.VALUE_READING.value,
    )

    with pytest.raises(Exception) as exc_info:
        await services["observation_service"].submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=checker.id,
            department_id=department.id,
            school_id=school.id,
            value_numeric=None,
            value_text="some text",
        )

    error_msg = str(exc_info.value).lower()
    assert "value" in error_msg or "numeric" in error_msg or "capture" in error_msg
