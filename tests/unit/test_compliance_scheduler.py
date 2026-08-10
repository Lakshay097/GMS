"""Unit tests for Compliance Scheduler — Architecture §5.7a, BR-24."""
import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from platform_services.compliance_scheduler.holiday_resolver import localize_due_date
from platform_services.compliance_scheduler.service import ComplianceScheduler
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.master_data_service.service import MasterDataService
from shared.datetime_utils import utc_now
from shared.platform_models import (
    ComplianceObservation,
    ComplianceSchedulerRunLog,
    KPI,
    KRA,
    NonWorkingDayPolicy,
)


@pytest.mark.asyncio
async def test_BR24_compliance_scheduler_idempotent(db, school, kpi):
    """BR-24/R-76: double-run produces zero duplicate compliance records."""
    await ConfigurationEngine(db).seed_defaults()
    scheduler = ComplianceScheduler(db)
    as_of = datetime(2026, 8, 7, 12, 0, 0)

    result_1 = await scheduler.run(as_of=as_of)
    result_2 = await scheduler.run(as_of=as_of)

    assert result_1.records_generated >= 1
    assert result_2.records_generated == 0

    count = await db.scalar(select(func.count()).select_from(ComplianceObservation))
    assert count == result_1.records_generated


@pytest.mark.asyncio
async def test_R77_school_timezone_due_dates(db, school, kpi):
    """R-77/FR-251: due dates computed in school timezone, not UTC."""
    school.timezone = "America/New_York"
    await db.commit()
    await ConfigurationEngine(db).seed_defaults()

    scheduler = ComplianceScheduler(db)
    as_of = datetime(2026, 8, 7, 4, 0, 0)  # 4 AM UTC = midnight EDT
    await scheduler.run(as_of=as_of)

    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None

    localized = localize_due_date(date(2026, 8, 7), timezone_name="America/New_York")
    assert record.due_at == localized


@pytest.mark.asyncio
async def test_BR24_backfill_missed_runs(db, school, kpi):
    """BR-24: missed run backfilled at correct original due date."""
    await ConfigurationEngine(db).seed_defaults()
    scheduler = ComplianceScheduler(db)

    last_run = datetime(2026, 8, 5, 12, 0, 0)
    as_of = datetime(2026, 8, 7, 12, 0, 0)

    result = await scheduler.run(as_of=as_of, last_run_at=last_run)
    assert result.records_backfilled >= 1

    runs = await db.execute(select(ComplianceSchedulerRunLog))
    run_log = runs.scalars().first()
    assert run_log.records_backfilled >= 1


@pytest.mark.asyncio
async def test_BR22_skip_policy_on_holiday(db, school, user):
    """BR-22: Skip policy produces no record on non-working day."""
    master_data = MasterDataService(db)
    await master_data.add_holiday(
        date(2026, 8, 7),
        "Holiday",
        school_id=school.id,
        created_by=user.id,
    )
    await ConfigurationEngine(db).seed_defaults()

    kra = KRA(id=uuid.uuid4(), name="KRA Skip", created_at=utc_now())
    db.add(kra)
    await db.flush()
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Skip KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        non_working_day_policy=NonWorkingDayPolicy.SKIP,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()

    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 7, 12, 0, 0))
    assert result.records_generated == 0


@pytest.mark.asyncio
async def test_BR22_shift_forward_policy(db, school):
    """BR-22: Shift Forward moves due date to next working day."""
    await ConfigurationEngine(db).seed_defaults()

    kra = KRA(id=uuid.uuid4(), name="KRA Forward", created_at=utc_now())
    db.add(kra)
    await db.flush()
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Forward KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_FORWARD,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()

    # Saturday 2026-08-08 should shift to Monday 2026-08-10
    scheduler = ComplianceScheduler(db)
    await scheduler.run(as_of=datetime(2026, 8, 8, 12, 0, 0))

    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None
    assert record.due_at.date() == date(2026, 8, 10)


@pytest.mark.asyncio
async def test_BR22_shift_backward_policy(db, school):
    """BR-22: Shift Backward moves due date to previous working day."""
    await ConfigurationEngine(db).seed_defaults()

    kra = KRA(id=uuid.uuid4(), name="KRA Backward", created_at=utc_now())
    db.add(kra)
    await db.flush()
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Backward KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_BACKWARD,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()

    # Sunday 2026-08-09 should shift to Friday 2026-08-07
    scheduler = ComplianceScheduler(db)
    await scheduler.run(as_of=datetime(2026, 8, 9, 12, 0, 0))

    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None
    assert record.due_at.date() == date(2026, 8, 7)
