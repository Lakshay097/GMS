"""
Unit tests for Location/Manual Time Reason (FR-189–190) using real ObservationService.
Tests location capture functionality through ObservationService.
Note: Event time capture tests require additional RuleEngine configuration.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import uuid
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from modules.observation_capture.services.observation_service import ObservationService
from platform_services.notification_service.service import NotificationService
from platform_services.configuration_engine.service import ConfigurationEngine
from shared.platform_models import (
    Observation,
    KPI,
    KRA,
    KpiCaptureType,
)
from shared.datetime_utils import utc_now
from shared.models import User
from shared.task_queue import InMemoryQueue


@pytest.mark.asyncio
async def test_location_capture_happy_path(db, school, department):
    """
    FR-189: Location Capture - Happy Path.
    Verify that observations can capture location information through ObservationService.
    Note: Real service uses location_id (UUID) not location dict.
    """
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
    kra = KRA(id=uuid.uuid4(), name="Location KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Location KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        capture_type=KpiCaptureType.VALUE_READING,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Initialize service with config engine seeded
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    notification_service = NotificationService(db, queue=InMemoryQueue())
    observation_service = ObservationService(db, config_engine=config_engine, notification_service=notification_service)
    
    # Submit observation with location_id (UUID reference)
    location_id = uuid.uuid4()  # In real implementation, this would reference a location entity
    observation = await observation_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=kpi.version,
        checker_id=user.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("95.5"),
        location_id=location_id
    )
    
    # Assert observation was created
    assert observation.id is not None
    assert observation.location_id == location_id


@pytest.mark.asyncio
async def test_value_reading_no_event_time(db, school, department):
    """
    FR-189: Value Reading - No Event Time Required.
    Verify that value reading KPIs don't require event time capture.
    """
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
    
    # Create KPI with value reading capture
    kra = KRA(id=uuid.uuid4(), name="Value Reading KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Value Reading KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        capture_type=KpiCaptureType.VALUE_READING,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Initialize service with config engine seeded
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    notification_service = NotificationService(db, queue=InMemoryQueue())
    observation_service = ObservationService(db, config_engine=config_engine, notification_service=notification_service)
    
    # Submit observation with only value (no event time)
    observation = await observation_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=kpi.version,
        checker_id=user.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("95.5"),
    )
    
    # Assert observation was created without event time
    assert observation.id is not None
    # Value reading observations don't require event_times


@pytest.mark.asyncio
async def test_location_data_structure(db, school, department):
    """
    FR-189: Location Data Structure.
    Verify that location data has the expected structure using location_id.
    """
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
    kra = KRA(id=uuid.uuid4(), name="Location Structure KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Location Structure KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        capture_type=KpiCaptureType.VALUE_READING,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Initialize service with config engine seeded
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    notification_service = NotificationService(db, queue=InMemoryQueue())
    observation_service = ObservationService(db, config_engine=config_engine, notification_service=notification_service)
    
    # Submit observation with location_id (UUID reference)
    location_id = uuid.uuid4()
    observation = await observation_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=kpi.version,
        checker_id=user.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("95.5"),
        location_id=location_id
    )
    
    # Assert observation was created with location data
    assert observation.id is not None
    assert observation.location_id == location_id


@pytest.mark.asyncio
async def test_observation_without_location(db, school, department):
    """
    FR-189: Observation Without Location.
    Verify that observations can be created without location when not required.
    """
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
    kra = KRA(id=uuid.uuid4(), name="No Location KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="No Location KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        capture_type=KpiCaptureType.VALUE_READING,
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Initialize service with config engine seeded
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    notification_service = NotificationService(db, queue=InMemoryQueue())
    observation_service = ObservationService(db, config_engine=config_engine, notification_service=notification_service)
    
    # Submit observation without location
    observation = await observation_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=kpi.version,
        checker_id=user.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("95.5"),
    )
    
    # Assert observation was created without location
    assert observation.id is not None
    assert observation.location_id is None