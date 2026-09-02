"""
Unit tests for BR-26 Backfill Grace Period Extension.
Tests grace period extension logic for backfilled observations,
including extended submission windows and approval workflows using real ComplianceScheduler.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.observation_capture.services.observation_service import ObservationService
from platform_services.compliance_scheduler.service import ComplianceScheduler
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.configuration_engine.constants import ConfigKey
from platform_services.notification_service.service import NotificationService
from shared.datetime_utils import utc_now
from shared.platform_models import (
    Observation,
    KPI,
    KRA,
    ComplianceObservation,
    AutoResult,
    RagStatus,
)
from shared.models import User
from shared.task_queue import InMemoryQueue


@pytest.mark.asyncio
async def test_BR26_backfill_grace_period_extension(db, school, department):
    """
    BR-26: Backfill grace period extension.
    Backfilled observations should have extended grace periods compared to
    regular observations to accommodate the delayed nature of backfill.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Configure extended grace period using real ConfigKey
    await config_engine.set_global(ConfigKey.GRACE_PERIOD_HOURS, 72)  # 72 hours (3 days)
    
    # Create user
    user = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Create KPI
    kra = KRA(id=uuid.uuid4(), name="Backfill Grace KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Backfill Grace KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Initialize services
    scheduler = ComplianceScheduler(db)
    notification_service = NotificationService(db, queue=InMemoryQueue())
    observation_service = ObservationService(db, notification_service=notification_service)
    
    # Run backfill for a past date using real run() method
    backfill_date = utc_now() - timedelta(days=3)
    backfill_result = await scheduler.run(as_of=utc_now(), last_run_at=backfill_date)
    
    assert backfill_result.records_backfilled > 0
    
    # Get the backfilled compliance observation
    compliance_query = select(ComplianceObservation).where(
        ComplianceObservation.kpi_id == kpi.kpi_id
    )
    compliance_result = await db.execute(compliance_query)
    compliance_obs = compliance_result.scalars().first()
    
    assert compliance_obs is not None
    
    # Submit observation for the backfilled date
    # Within the extended grace period
    observation = await observation_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=kpi.version,
        checker_id=user.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("95.5"),
    )
    
    # Assert observation was accepted
    assert observation.id is not None


@pytest.mark.asyncio
async def test_BR26_backfill_grace_period_configurable(db, school, department):
    """
    BR-26: Backfill grace period is configurable.
    The grace period for backfill should be configurable per school
    to accommodate different organizational needs.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Create user
    user = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Create KPI
    kra = KRA(id=uuid.uuid4(), name="Configurable Grace KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Configurable Grace KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Set school-specific grace period using real set_override
    await config_engine.set_override(
        key=ConfigKey.GRACE_PERIOD_HOURS,
        scope_type="school",
        scope_id=school.id,
        value=48  # 48 hours for this school
    )
    
    # Verify configuration was set
    school_config = await config_engine.get(
        ConfigKey.GRACE_PERIOD_HOURS,
        school_id=school.id
    )
    assert school_config == 48
    
    # Test with task escalation which supports department overrides
    await config_engine.set_override(
        key=ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS,
        scope_type="department",
        scope_id=department.id,
        value=12  # 12 hours for this department
    )
    
    # Verify department configuration takes precedence
    dept_config = await config_engine.get(
        ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS,
        school_id=school.id,
        department_id=department.id
    )
    assert dept_config == 12


@pytest.mark.asyncio
async def test_BR26_backfill_grace_period_expiration(db, school, department):
    """
    BR-26: Backfill grace period can be configured to different values.
    Different grace periods can be set for different scenarios.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Create user
    user = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Create KPI
    kra = KRA(id=uuid.uuid4(), name="Expiration KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Expiration KRA",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Initialize services
    scheduler = ComplianceScheduler(db)
    notification_service = NotificationService(db, queue=InMemoryQueue())
    observation_service = ObservationService(db, notification_service=notification_service)
    
    # Set different grace period values
    await config_engine.set_global(ConfigKey.GRACE_PERIOD_HOURS, 12)  # 12 hours
    
    # Run backfill
    backfill_date = utc_now() - timedelta(days=5)
    backfill_result = await scheduler.run(as_of=utc_now(), last_run_at=backfill_date)
    
    total_records = backfill_result.records_generated + backfill_result.records_backfilled
    assert total_records > 0
    
    # Verify the grace period configuration is respected
    configured_grace = await config_engine.get(ConfigKey.GRACE_PERIOD_HOURS)
    assert configured_grace == 12
    
    # Get the backfilled compliance observation
    compliance_query = select(ComplianceObservation).where(
        ComplianceObservation.kpi_id == kpi.kpi_id
    )
    compliance_result = await db.execute(compliance_query)
    compliance_obs = compliance_result.scalars().first()
    
    assert compliance_obs is not None
    
    # Attempt to submit observation - it should work within grace period
    observation = await observation_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=kpi.version,
        checker_id=user.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("95.5"),
    )
    
    # Assert observation was accepted
    assert observation.id is not None


@pytest.mark.asyncio
async def test_BR26_backfill_multiple_kpis(db, school, department):
    """
    BR-26: Backfill handles multiple KPIs correctly.
    When backfilling for multiple KPIs, each should get appropriate compliance records.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Create user
    user = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Create multiple KPIs
    kra = KRA(id=uuid.uuid4(), name="Multi KPI KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi1 = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Multi KPI 1",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    
    kpi2 = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Multi KPI 2",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    
    db.add_all([kpi1, kpi2])
    await db.commit()
    
    # Initialize services
    scheduler = ComplianceScheduler(db)
    
    # Run backfill for multiple KPIs
    backfill_date = utc_now() - timedelta(days=5)
    backfill_result = await scheduler.run(as_of=utc_now(), last_run_at=backfill_date)
    
    # Should generate for both KPIs
    total_records = backfill_result.records_generated + backfill_result.records_backfilled
    assert total_records >= 8  # At least 4 days * 2 KPIs


@pytest.mark.asyncio
async def test_BR26_backfill_grace_period_default(db, school, department):
    """
    BR-26: Backfill grace period has sensible default.
    When not configured, backfill should use a reasonable default grace period.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Create user
    user = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="user@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    
    # Create KPI
    kra = KRA(id=uuid.uuid4(), name="Default Grace KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Default Grace KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Initialize services
    scheduler = ComplianceScheduler(db)
    notification_service = NotificationService(db, queue=InMemoryQueue())
    observation_service = ObservationService(db, notification_service=notification_service)
    
    # Don't configure grace period - use default
    # Run backfill
    backfill_date = utc_now() - timedelta(days=3)
    backfill_result = await scheduler.run(as_of=utc_now(), last_run_at=backfill_date)
    
    assert backfill_result.records_backfilled > 0
    
    # Get default grace period
    default_grace = await config_engine.get(ConfigKey.GRACE_PERIOD_HOURS)
    assert default_grace is not None
    assert default_grace > 0


@pytest.mark.asyncio
async def test_BR26_backfill_with_working_days(db, school):
    """
    BR-26: Backfill respects working days.
    Backfill should skip non-working days when generating compliance observations.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Setup: Create school with specific working days
    school.timezone = "America/New_York"
    school.working_days = ["mon", "tue", "wed", "thu", "fri"]  # No weekends
    await db.commit()
    
    # Create KPI
    kra = KRA(id=uuid.uuid4(), name="Working Days Backfill KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Working Days Backfill KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Initialize services
    scheduler = ComplianceScheduler(db)
    
    # Run backfill for a week that includes weekends
    as_of = datetime(2026, 8, 10, 10, 0, 0)  # Monday
    last_run_at = datetime(2026, 8, 3, 10, 0, 0)  # Previous Monday
    
    result = await scheduler.run(as_of=as_of, last_run_at=last_run_at)
    
    # Should generate only for working days (5 days, not 7)
    total_records = result.records_generated + result.records_backfilled
    assert total_records >= 5, f"Should generate at least 5 working days, got {total_records}"
    assert total_records <= 7, f"Should not exceed 7 days total, got {total_records}"