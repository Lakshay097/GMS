"""Unit test for BR-22 Compliance Scheduler Holiday Skip Policy."""
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from platform_services.compliance_scheduler.service import ComplianceScheduler
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.master_data_service.service import MasterDataService
from shared.datetime_utils import utc_now
from shared.platform_models import (
    ComplianceObservation,
    KPI,
    KRA,
    NonWorkingDayPolicy,
)


@pytest.mark.asyncio
async def test_BR22_compliance_scheduler_holiday_skip(db, school, user):
    """
    BR-22: Skip policy produces zero records on holiday.
    When a due date falls on a holiday with SKIP policy, no compliance record should be generated.
    """
    master_data = MasterDataService(db)
    
    # Add a holiday for the test date
    await master_data.add_holiday(
        date(2026, 8, 8),  # Friday holiday
        "Test Holiday",
        school_id=school.id,
        created_by=user.id,
    )
    
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI with SKIP policy
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
    
    # Run scheduler on the holiday date
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 8, 12, 0, 0))
    
    # Verify zero records were generated
    assert result.records_generated == 0, "SKIP policy should produce zero records on holiday"
    
    # Verify database has no compliance records for this date
    count = await db.scalar(select(func.count()).select_from(ComplianceObservation))
    assert count == 0, "Database should contain zero compliance records"
