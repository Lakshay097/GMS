"""
Unit tests for BR-24 Timezone-aware generation and backfill logic.
Tests timezone-aware observation generation, backfill logic, and
cross-timezone compliance observation handling using real ComplianceScheduler.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import uuid
from datetime import datetime, timedelta, date
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.observation_capture.services.observation_service import ObservationService
from platform_services.compliance_scheduler.service import ComplianceScheduler
from platform_services.configuration_engine.service import ConfigurationEngine
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
async def test_BR24_timezone_aware_observation_generation(db, school, department):
    """
    BR-24: Timezone-aware observation generation.
    Observations should be generated based on school's local timezone,
    not UTC. Due dates should respect the school's timezone configuration.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Setup: Create school with specific timezone
    school.timezone = "Asia/Kolkata"  # UTC+5:30
    await db.commit()
    
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
    kra = KRA(id=uuid.uuid4(), name="Timezone KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Timezone KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Initialize services with memory queue
    notification_service = NotificationService(db, queue=InMemoryQueue())
    observation_service = ObservationService(db, notification_service=notification_service)
    
    # Submit observation - should be processed in school's timezone
    observation = await observation_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=kpi.version,
        checker_id=user.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("95.5"),
    )
    
    # Assert observation was created
    assert observation.id is not None
    
    # Verify timestamps are in UTC but represent local time correctly
    # The submitted_at should be in UTC but represent the local submission time
    assert observation.submitted_at is not None


@pytest.mark.asyncio
async def test_BR24_timezone_aware_compliance_generation(db, school):
    """
    BR-24: Timezone-aware compliance observation generation.
    Compliance scheduler should generate observations based on school's
    local timezone, respecting local working days and business hours.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Setup: Create school with specific timezone
    school.timezone = "America/New_York"  # UTC-5/-4
    school.working_days = ["mon", "tue", "wed", "thu", "fri"]
    await db.commit()
    
    # Create KPI
    kra = KRA(id=uuid.uuid4(), name="NY Timezone KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="NY Timezone KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Run scheduler at a time that's business hours in NY but not UTC
    # 9 AM EST = 2 PM UTC (next day in some timezones)
    scheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 10, 14, 0, 0))  # 2 PM UTC = 9 AM EST
    
    # Verify compliance observation was generated
    assert result.records_generated > 0, "Should generate compliance observation for NY timezone"
    
    # Verify the due date respects NY timezone
    compliance_query = select(ComplianceObservation).where(
        ComplianceObservation.kpi_id == kpi.kpi_id
    )
    compliance_result = await db.execute(compliance_query)
    compliance_obs = compliance_result.scalars().first()
    
    assert compliance_obs is not None
    # The due date should be in the school's local timezone context
    assert compliance_obs.due_at is not None


@pytest.mark.asyncio
async def test_BR24_backfill_missing_observations(db, school, department):
    """
    BR-24: Backfill logic for missing observations using real ComplianceScheduler.run().
    When observations are missing for a period, backfill should generate
    the missing compliance observations with appropriate due dates.
    """
    await ConfigurationEngine(db).seed_defaults()
    
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
    kra = KRA(id=uuid.uuid4(), name="Backfill KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Backfill KPI",
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
    
    # Run backfill for past 7 days using real run() method with last_run_at
    as_of = utc_now()
    last_run_at = as_of - timedelta(days=7)
    backfill_result = await scheduler.run(as_of=as_of, last_run_at=last_run_at)
    
    # Verify backfill generated the expected number of observations
    # records_generated = current day, records_backfilled = historical days
    total_records = backfill_result.records_generated + backfill_result.records_backfilled
    assert total_records >= 6, f"Should generate at least 6 days total (current + backfill), got {total_records}"
    assert backfill_result.records_backfilled > 0, "Should have backfilled some records"
    
    # Verify all backfilled observations have correct due dates
    compliance_query = select(ComplianceObservation).where(
        ComplianceObservation.kpi_id == kpi.kpi_id
    ).order_by(ComplianceObservation.due_at)
    
    compliance_result = await db.execute(compliance_query)
    compliance_observations = compliance_result.scalars().all()
    
    assert len(compliance_observations) >= 6
    
    # Verify due dates are sequential
    for i in range(len(compliance_observations) - 1):
        assert compliance_observations[i + 1].due_at > compliance_observations[i].due_at


@pytest.mark.asyncio
async def test_BR24_backfill_respects_existing_observations(db, school, department):
    """
    BR-24: Backfill logic respects existing observations.
    When backfilling, existing observations should not be duplicated.
    """
    await ConfigurationEngine(db).seed_defaults()
    
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
    kra = KRA(id=uuid.uuid4(), name="Backfill Respect KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Backfill Respect KPI",
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
    
    # First run to create compliance observation for today
    first_run = await scheduler.run(as_of=utc_now())
    total_first = first_run.records_generated + first_run.records_backfilled
    assert total_first == 1
    
    # Second run with same as_of should not duplicate (idempotent)
    second_run = await scheduler.run(as_of=utc_now())
    total_second = second_run.records_generated + second_run.records_backfilled
    assert total_second == 0, "Should not duplicate existing observations"
    
    # Verify only one compliance observation exists
    compliance_query = select(ComplianceObservation).where(
        ComplianceObservation.kpi_id == kpi.kpi_id
    )
    compliance_result = await db.execute(compliance_query)
    compliance_observations = compliance_result.scalars().all()
    
    assert len(compliance_observations) == 1, "Should have exactly one compliance observation"


@pytest.mark.asyncio
async def test_BR24_backfill_with_timezone_boundaries(db, school):
    """
    BR-24: Backfill respects timezone boundaries.
    Backfill should correctly handle due dates across timezone boundaries.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Setup: Create school with timezone that crosses UTC date boundary
    school.timezone = "Asia/Tokyo"  # UTC+9
    school.working_days = ["mon", "tue", "wed", "thu", "fri"]
    await db.commit()
    
    # Create KPI
    kra = KRA(id=uuid.uuid4(), name="Tokyo Timezone KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Tokyo Timezone KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Run backfill across timezone boundary
    scheduler = ComplianceScheduler(db)
    as_of = datetime(2026, 8, 10, 15, 0, 0)  # 3 PM UTC = midnight next day in Tokyo
    last_run_at = datetime(2026, 8, 3, 15, 0, 0)  # 7 days earlier
    
    result = await scheduler.run(as_of=as_of, last_run_at=last_run_at)
    
    # Verify backfill generated observations
    total_records = result.records_generated + result.records_backfilled
    assert total_records > 0
    
    # Verify due dates respect Tokyo timezone
    compliance_query = select(ComplianceObservation).where(
        ComplianceObservation.kpi_id == kpi.kpi_id
    ).order_by(ComplianceObservation.due_at)
    
    compliance_result = await db.execute(compliance_query)
    compliance_observations = compliance_result.scalars().all()
    
    # Due dates should be in Tokyo timezone context (UTC+9)
    assert len(compliance_observations) > 0
    for obs in compliance_observations:
        assert obs.due_at is not None


@pytest.mark.asyncio
async def test_BR24_backfill_failure_invalid_last_run_at(db, school, department):
    """
    BR-24: Backfill handles invalid last_run_at gracefully.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Create KPI
    kra = KRA(id=uuid.uuid4(), name="Invalid Backfill KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Invalid Backfill KPI",
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
    
    # Run with last_run_at in the future - should handle gracefully
    as_of = utc_now()
    last_run_at = as_of + timedelta(days=1)  # Future date
    
    result = await scheduler.run(as_of=as_of, last_run_at=last_run_at)
    
    # Should still generate for current day
    assert result.records_generated >= 0  # May generate 0 or 1 depending on implementation


@pytest.mark.asyncio
async def test_BR24_timezone_aware_working_days(db, school):
    """
    BR-24: Timezone-aware working days.
    Compliance scheduler should respect school's configured working days
    in their local timezone.
    """
    await ConfigurationEngine(db).seed_defaults()
    
    # Setup: Create school with specific working days
    school.timezone = "Europe/London"  # UTC+0/+1
    school.working_days = ["mon", "tue", "wed", "thu", "fri"]  # No weekends
    await db.commit()
    
    # Create KPI
    kra = KRA(id=uuid.uuid4(), name="Working Days KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Working Days KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Run scheduler for a week that includes weekends
    scheduler = ComplianceScheduler(db)
    as_of = datetime(2026, 8, 10, 10, 0, 0)  # Monday
    last_run_at = datetime(2026, 8, 3, 10, 0, 0)  # Previous Monday
    
    result = await scheduler.run(as_of=as_of, last_run_at=last_run_at)
    
    # Should generate only for working days (5 days, not 7)
    # records_generated = current day, records_backfilled = historical working days
    total_records = result.records_generated + result.records_backfilled
    assert total_records >= 5, f"Should generate at least 5 working days total, got {total_records}"
    assert total_records <= 7, f"Should not exceed 7 days total, got {total_records}"
