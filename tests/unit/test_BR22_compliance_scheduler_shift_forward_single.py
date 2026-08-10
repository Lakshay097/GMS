"""Unit test for BR-22 Compliance Scheduler Shift Forward Policy."""
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
async def test_BR22_compliance_scheduler_shift_forward_single(db, school):
    """
    BR-22: Shift Forward policy produces exactly one record shifted to next working day.
    When a due date falls on a non-working day with SHIFT_FORWARD policy, 
    exactly one compliance record should be generated for the next working day.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SHIFT_FORWARD policy and Mon-Fri working days
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
        working_days=["mon", "tue", "wed", "thu", "fri"],  # Mon-Fri only
        non_working_day_policy=NonWorkingDayPolicy.SHIFT_FORWARD,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Run scheduler on Saturday (non-working day)
    # Saturday 2026-08-08 should shift to Monday 2026-08-10
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 8, 12, 0, 0))
    
    # Verify exactly one record was generated
    assert result.records_generated == 1, "SHIFT_FORWARD policy should produce exactly one record"
    
    # Verify database has exactly one compliance record
    count = await db.scalar(select(func.count()).select_from(ComplianceObservation))
    assert count == 1, "Database should contain exactly one compliance record"
    
    # Verify the due date was shifted to Monday
    result = await db.execute(select(ComplianceObservation))
    record = result.scalars().first()
    assert record is not None, "Compliance record should exist"
    assert record.due_at.date() == date(2026, 8, 10), "Due date should be shifted to Monday 2026-08-10"
