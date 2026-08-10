"""
Additional unit tests for BR-22 Compliance Scheduler policies.
Tests various edge cases and combinations of SHIFT_FORWARD, SHIFT_BACKWARD, and SKIP policies.
"""
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from platform_services.compliance_scheduler.service import ComplianceScheduler
from platform_services.configuration_engine.service import ConfigurationEngine
from shared.datetime_utils import utc_now
from shared.platform_models import (
    ComplianceObservation,
    KPI,
    KRA,
    NonWorkingDayPolicy,
)


@pytest.mark.asyncio
async def test_BR22_shift_forward_vs_skip_distinction(db, school):
    """
    BR-22: Verify distinction between SHIFT_FORWARD and SKIP policies.
    SHIFT_FORWARD should move to next working day, SKIP should not generate record.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SHIFT_FORWARD policy
    kra_forward = KRA(id=uuid.uuid4(), name="KRA Forward", created_at=utc_now())
    db.add(kra_forward)
    await db.flush()
    
    kpi_forward = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra_forward.id,
        title="Forward KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_FORWARD,
        created_at=utc_now(),
    )
    db.add(kpi_forward)
    
    # Create KPI with SKIP policy
    kra_skip = KRA(id=uuid.uuid4(), name="KRA Skip", created_at=utc_now())
    db.add(kra_skip)
    await db.flush()
    
    kpi_skip = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra_skip.id,
        title="Skip KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        non_working_day_policy=NonWorkingDayPolicy.SKIP,
        created_at=utc_now(),
    )
    db.add(kpi_skip)
    await db.commit()
    
    # Run scheduler on Saturday
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 8, 12, 0, 0))
    
    # Verify SHIFT_FORWARD generated 1 record
    forward_count = await db.scalar(
        select(func.count()).select_from(ComplianceObservation).where(
            ComplianceObservation.kpi_id == kpi_forward.kpi_id
        )
    )
    assert forward_count == 1, "SHIFT_FORWARD should generate 1 record"
    
    # Verify SKIP generated 0 records
    skip_count = await db.scalar(
        select(func.count()).select_from(ComplianceObservation).where(
            ComplianceObservation.kpi_id == kpi_skip.kpi_id
        )
    )
    assert skip_count == 0, "SKIP should not generate any records"


@pytest.mark.asyncio
async def test_BR22_shift_backward_with_holiday(db, school):
    """
    BR-22: Shift Backward policy with holiday configuration.
    When due date falls on a holiday, should shift to previous working day.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SHIFT_BACKWARD policy
    kra = KRA(id=uuid.uuid4(), name="KRA Holiday Backward", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Holiday Backward KPI",
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
    
    # Configure a holiday on Thursday
    from shared.platform_models import Holiday
    holiday = Holiday(
        id=uuid.uuid4(),
        school_id=school.id,
        date=date(2026, 8, 6),  # Thursday
        name="Test Holiday",
        is_school_wide=True,
        created_at=utc_now(),
    )
    db.add(holiday)
    await db.commit()
    
    # Run scheduler on Thursday (holiday)
    # Thursday 2026-08-06 should shift to Wednesday 2026-08-05
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 6, 12, 0, 0))
    
    # Verify exactly one record was generated
    assert result.records_generated == 1, "Should generate exactly one record for holiday"
    
    # Verify the due date was shifted to Wednesday
    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None, "Compliance record should exist"
    assert record.due_at.date() == date(2026, 8, 5), "Due date should be shifted to Wednesday 2026-08-05"


@pytest.mark.asyncio
async def test_BR22_shift_forward_with_holiday(db, school):
    """
    BR-22: Shift Forward policy with holiday configuration.
    When due date falls on a holiday, should shift to next working day.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SHIFT_FORWARD policy
    kra = KRA(id=uuid.uuid4(), name="KRA Holiday Forward", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Holiday Forward KPI",
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
    
    # Configure a holiday on Thursday
    from shared.platform_models import Holiday
    holiday = Holiday(
        id=uuid.uuid4(),
        school_id=school.id,
        date=date(2026, 8, 6),  # Thursday
        name="Test Holiday",
        is_school_wide=True,
        created_at=utc_now(),
    )
    db.add(holiday)
    await db.commit()
    
    # Run scheduler on Thursday (holiday)
    # Thursday 2026-08-06 should shift to Friday 2026-08-07
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 6, 12, 0, 0))
    
    # Verify exactly one record was generated
    assert result.records_generated == 1, "Should generate exactly one record for holiday"
    
    # Verify the due date was shifted to Friday
    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None, "Compliance record should exist"
    assert record.due_at.date() == date(2026, 8, 7), "Due date should be shifted to Friday 2026-08-07"


@pytest.mark.asyncio
async def test_BR22_custom_working_days_shift_forward(db, school):
    """
    BR-22: Shift Forward policy with custom working days.
    Tests that shift logic respects custom working day configurations.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with custom working days (Tue-Sat)
    kra = KRA(id=uuid.uuid4(), name="KRA Custom Days", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Custom Days KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["tue", "wed", "thu", "fri", "sat"],  # Tue-Sat only
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_FORWARD,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Run scheduler on Monday (non-working day for this KPI)
    # Monday 2026-08-10 should shift to Tuesday 2026-08-11
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 10, 12, 0, 0))
    
    # Verify exactly one record was generated
    assert result.records_generated == 1, "Should generate exactly one record"
    
    # Verify the due date was shifted to Tuesday
    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None, "Compliance record should exist"
    assert record.due_at.date() == date(2026, 8, 11), "Due date should be shifted to Tuesday 2026-08-11"


@pytest.mark.asyncio
async def test_BR22_multiple_kpis_different_policies(db, school):
    """
    BR-22: Multiple KPIs with different non-working day policies.
    Verifies that scheduler correctly applies different policies to different KPIs.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SHIFT_FORWARD
    kra_forward = KRA(id=uuid.uuid4(), name="KRA Forward", created_at=utc_now())
    db.add(kra_forward)
    await db.flush()
    
    kpi_forward = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra_forward.id,
        title="Forward KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_FORWARD,
        created_at=utc_now(),
    )
    db.add(kpi_forward)
    
    # Create KPI with SHIFT_BACKWARD
    kra_backward = KRA(id=uuid.uuid4(), name="KRA Backward", created_at=utc_now())
    db.add(kra_backward)
    await db.flush()
    
    kpi_backward = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra_backward.id,
        title="Backward KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_BACKWARD,
        created_at=utc_now(),
    )
    db.add(kpi_backward)
    
    # Create KPI with SKIP
    kra_skip = KRA(id=uuid.uuid4(), name="KRA Skip", created_at=utc_now())
    db.add(kra_skip)
    await db.flush()
    
    kpi_skip = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra_skip.id,
        title="Skip KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        non_working_day_policy=NonWorkingDayPolicy.SKIP,
        created_at=utc_now(),
    )
    db.add(kpi_skip)
    await db.commit()
    
    # Run scheduler on Saturday
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 8, 12, 0, 0))
    
    # Verify SHIFT_FORWARD generated 1 record (shifted to Monday)
    forward_record = await db.execute(
        select(ComplianceObservation).where(
            ComplianceObservation.kpi_id == kpi_forward.kpi_id
        )
    )
    forward = forward_record.scalars().first()
    assert forward is not None, "SHIFT_FORWARD should generate record"
    assert forward.due_at.date() == date(2026, 8, 10), "SHIFT_FORWARD should shift to Monday"
    
    # Verify SHIFT_BACKWARD generated 1 record (shifted to Friday)
    backward_record = await db.execute(
        select(ComplianceObservation).where(
            ComplianceObservation.kpi_id == kpi_backward.kpi_id
        )
    )
    backward = backward_record.scalars().first()
    assert backward is not None, "SHIFT_BACKWARD should generate record"
    assert backward.due_at.date() == date(2026, 8, 7), "SHIFT_BACKWARD should shift to Friday"
    
    # Verify SKIP generated 0 records
    skip_count = await db.scalar(
        select(func.count()).select_from(ComplianceObservation).where(
            ComplianceObservation.kpi_id == kpi_skip.kpi_id
        )
    )
    assert skip_count == 0, "SKIP should not generate any records"