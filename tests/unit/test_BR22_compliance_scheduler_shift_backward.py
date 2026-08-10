"""
Unit test for BR-22 Compliance Scheduler Shift Backward Policy.
Tests the SHIFT_BACKWARD policy where due dates on non-working days
are shifted to the previous working day.
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
async def test_BR22_compliance_scheduler_shift_backward_single(db, school):
    """
    BR-22: Shift Backward policy produces exactly one record shifted to previous working day.
    When a due date falls on a non-working day with SHIFT_BACKWARD policy, 
    exactly one compliance record should be generated for the previous working day.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SHIFT_BACKWARD policy and Mon-Fri working days
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
        working_days=["mon", "tue", "wed", "thu", "fri"],  # Mon-Fri only
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_BACKWARD,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Run scheduler on Saturday (non-working day)
    # Saturday 2026-08-08 should shift to Friday 2026-08-07
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 8, 12, 0, 0))
    
    # Verify exactly one record was generated
    assert result.records_generated == 1, "SHIFT_BACKWARD policy should produce exactly one record"
    
    # Verify database has exactly one compliance record
    count = await db.scalar(select(func.count()).select_from(ComplianceObservation))
    assert count == 1, "Database should contain exactly one compliance record"
    
    # Verify the due date was shifted to Friday
    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None, "Compliance record should exist"
    assert record.due_at.date() == date(2026, 8, 7), "Due date should be shifted to Friday 2026-08-07"


@pytest.mark.asyncio
async def test_BR22_compliance_scheduler_shift_backward_weekend(db, school):
    """
    BR-22: Shift Backward policy handles weekend correctly.
    When due date falls on Sunday, should shift to Friday (previous working day).
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SHIFT_BACKWARD policy and Mon-Fri working days
    kra = KRA(id=uuid.uuid4(), name="KRA Weekend Backward", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Weekend Backward KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],  # Mon-Fri only
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_BACKWARD,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Run scheduler on Sunday (non-working day)
    # Sunday 2026-08-09 should shift to Friday 2026-08-07
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 9, 12, 0, 0))
    
    # Verify exactly one record was generated
    assert result.records_generated == 1, "SHIFT_BACKWARD policy should produce exactly one record"
    
    # Verify the due date was shifted to Friday
    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None, "Compliance record should exist"
    assert record.due_at.date() == date(2026, 8, 7), "Due date should be shifted to Friday 2026-08-07"


@pytest.mark.asyncio
async def test_BR22_compliance_scheduler_shift_backward_consecutive_non_working(db, school):
    """
    BR-22: Shift Backward policy handles consecutive non-working days.
    When due date falls on a non-working day that is part of consecutive non-working days,
    should shift to the most recent working day.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SHIFT_BACKWARD policy and Mon-Fri working days
    kra = KRA(id=uuid.uuid4(), name="KRA Consecutive Backward", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Consecutive Backward KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],  # Mon-Fri only
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_BACKWARD,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Run scheduler on Sunday (end of weekend)
    # Sunday 2026-08-09 should shift to Friday 2026-08-07 (skipping Saturday)
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 9, 12, 0, 0))
    
    # Verify exactly one record was generated
    assert result.records_generated == 1, "SHIFT_BACKWARD policy should produce exactly one record"
    
    # Verify the due date was shifted to Friday (not Saturday)
    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None, "Compliance record should exist"
    assert record.due_at.date() == date(2026, 8, 7), "Due date should be shifted to Friday 2026-08-07, not Saturday"


@pytest.mark.asyncio
async def test_BR22_compliance_scheduler_shift_backward_working_day(db, school):
    """
    BR-22: Shift Backward policy on working day produces no shift.
    When due date falls on a working day with SHIFT_BACKWARD policy,
    the due date should remain unchanged.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SHIFT_BACKWARD policy and Mon-Fri working days
    kra = KRA(id=uuid.uuid4(), name="KRA Working Day", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Working Day KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],  # Mon-Fri only
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_BACKWARD,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Run scheduler on Monday (working day)
    # Monday 2026-08-10 should remain Monday 2026-08-10
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 10, 12, 0, 0))
    
    # Verify exactly one record was generated
    assert result.records_generated == 1, "Should produce exactly one record on working day"
    
    # Verify the due date was not shifted
    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None, "Compliance record should exist"
    assert record.due_at.date() == date(2026, 8, 10), "Due date should remain Monday 2026-08-10"