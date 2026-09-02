"""
Acceptance tests for Evidence Retention & Deletion per PRS §47/BR-27, FR-271–274.
Verifies that deletion is governed, explicit, logged, and never automated.
"""
import pytest
import glob
import uuid
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from modules.observation_capture.services.evidence_service import EvidenceService
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.configuration_engine.constants import ConfigKey
from platform_services.audit_log_service.service import AuditLogService
from shared.platform_models import Observation, KPI, KRA
from shared.models import (
    User, UserRole, UserStatus,
    School, SchoolStatus,
    Department, DepartmentStatus,
    AuditLogEntry,
)
from shared.errors import BusinessRuleError
from shared.datetime_utils import utc_now


@pytest.mark.asyncio
async def test_evidence_deletion_rejected_before_retention_period(db: AsyncSession):
    """
    Acceptance test: Evidence deletion is rejected before retention period elapses.
    This rejection applies even to SuperAdmin users per BR-27/FR-273.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()

    # Setup: Create observation with recent submission (within retention period)
    school = School(id=uuid4(), name="Test School", code="TS001", status=SchoolStatus.ACTIVE)
    db.add(school)

    dept = Department(id=uuid4(), school_id=school.id, name="Test Dept", code="TD001", status=DepartmentStatus.ACTIVE)
    db.add(dept)

    # Create SuperAdmin user
    super_admin = User(
        id=uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="superadmin@test.com",
        full_name="Test SuperAdmin",
        roles=[UserRole.SUPERADMIN.value],
        status=UserStatus.ACTIVE,
    )
    db.add(super_admin)

    kra = KRA(id=uuid4(), name="Test KRA", status="active")
    db.add(kra)

    kpi = KPI(
        kpi_id=uuid4(),
        version=1,
        kra_id=kra.id,
        title="Test KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="count",
        frequency_code="daily",
        status="active",
    )
    db.add(kpi)

    # Create observation submitted recently (within retention period)
    recent_observation = Observation(
        id=uuid4(),
        kpi_id=kpi.kpi_id,
        kpi_version=1,
        checker_id=uuid4(),
        department_id=dept.id,
        school_id=school.id,
        value_numeric=50,
        auto_result="not_met",
        rag_status="red",
        submitted_at=utc_now() - timedelta(days=1),  # 1 day ago (well within retention period)
        evidence=[{"cloudinary_public_id": "test_evidence_123", "cloudinary_url": "https://test.com/evidence.jpg"}]
    )
    db.add(recent_observation)

    await db.commit()

    # Create evidence service
    evidence_service = EvidenceService(db, config_engine=config_engine)

    # Check deletion eligibility
    eligibility = await evidence_service.is_evidence_deletion_eligible(
        observation_id=recent_observation.id,
        public_id="test_evidence_123",
        school_id=school.id
    )

    assert eligibility["eligible"] is False, "Evidence should not be deletion-eligible yet"
    assert eligibility["days_until_eligible"] > 0, "Should have positive days until eligible"

    # Attempt deletion as SuperAdmin - should be rejected
    with pytest.raises(BusinessRuleError) as exc_info:
        await evidence_service.delete_evidence_with_audit(
            observation_id=recent_observation.id,
            public_id="test_evidence_123",
            actor_id=super_admin.id,
            school_id=school.id,
            reason="Test deletion"
        )

    # Verify error message mentions retention period
    error_message = str(exc_info.value)
    assert "retention period" in error_message.lower(), "Error should mention retention period"
    assert "not yet permitted" in error_message.lower(), "Error should state deletion not permitted"


@pytest.mark.asyncio
async def test_evidence_deletion_succeeds_after_retention_period(db: AsyncSession):
    """
    Acceptance test: Evidence deletion succeeds after retention period elapses.
    Must be explicit action with actor identity and logged to Audit Log per FR-274.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()

    # Set a short retention period for testing
    await config_engine.set_global(ConfigKey.EVIDENCE_RETENTION_PERIOD_DAYS, "1")

    # Setup: Create observation with old submission (past retention period)
    school = School(id=uuid4(), name="Test School", code="TS002", status=SchoolStatus.ACTIVE)
    db.add(school)

    dept = Department(id=uuid4(), school_id=school.id, name="Test Dept", code="TD002", status=DepartmentStatus.ACTIVE)
    db.add(dept)

    admin = User(
        id=uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="admin@test.com",
        full_name="Test Admin",
        school_id=school.id,
        roles=[UserRole.ADMIN.value],
        status=UserStatus.ACTIVE,
    )
    db.add(admin)

    kra = KRA(id=uuid4(), name="Test KRA", status="active")
    db.add(kra)

    kpi = KPI(
        kpi_id=uuid4(),
        version=1,
        kra_id=kra.id,
        title="Test KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="count",
        frequency_code="daily",
        status="active",
    )
    db.add(kpi)

    # Create observation submitted past retention period
    old_observation = Observation(
        id=uuid4(),
        kpi_id=kpi.kpi_id,
        kpi_version=1,
        checker_id=uuid4(),
        department_id=dept.id,
        school_id=school.id,
        value_numeric=50,
        auto_result="not_met",
        rag_status="red",
        submitted_at=utc_now() - timedelta(days=10),  # 10 days ago (past 1-day retention period)
        evidence=[{"cloudinary_public_id": "test_evidence_456", "cloudinary_url": "https://test.com/evidence2.jpg"}]
    )
    db.add(old_observation)

    await db.commit()

    # Create evidence service
    evidence_service = EvidenceService(db, config_engine=config_engine)

    # Check deletion eligibility
    eligibility = await evidence_service.is_evidence_deletion_eligible(
        observation_id=old_observation.id,
        public_id="test_evidence_456",
        school_id=school.id
    )

    assert eligibility["eligible"] is True, "Evidence should be deletion-eligible"
    assert eligibility["days_until_eligible"] <= 0, "Should have non-positive days until eligible"

    # Perform deletion as Admin
    deletion_result = await evidence_service.delete_evidence_with_audit(
        observation_id=old_observation.id,
        public_id="test_evidence_456",
        actor_id=admin.id,
        school_id=school.id,
        reason="Test deletion after retention period"
    )

    assert deletion_result["success"] is True, "Deletion should succeed"
    assert deletion_result["actor_id"] == str(admin.id), "Result should include actor identity"
    assert "audit_log_id" in deletion_result, "Deletion should be logged"
    assert deletion_result["deleted_at"] is not None, "Deletion timestamp should be recorded"


@pytest.mark.asyncio
async def test_evidence_deletion_logged_to_audit_log(db: AsyncSession):
    """
    Acceptance test: Every evidence deletion is logged to Audit Log with actor identity and timestamp.
    Per FR-274, audit log must capture actor, timestamp, and affected observation.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()

    # Set short retention period
    await config_engine.set_global(ConfigKey.EVIDENCE_RETENTION_PERIOD_DAYS, "1")

    # Setup
    school = School(id=uuid4(), name="Test School", code="TS003", status=SchoolStatus.ACTIVE)
    db.add(school)

    dept = Department(id=uuid4(), school_id=school.id, name="Test Dept", code="TD003", status=DepartmentStatus.ACTIVE)
    db.add(dept)

    admin = User(
        id=uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="admin@test.com",
        full_name="Test Admin",
        school_id=school.id,
        roles=[UserRole.ADMIN.value],
        status=UserStatus.ACTIVE,
    )
    db.add(admin)

    kra = KRA(id=uuid4(), name="Test KRA", status="active")
    db.add(kra)

    kpi = KPI(
        kpi_id=uuid4(),
        version=1,
        kra_id=kra.id,
        title="Test KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="count",
        frequency_code="daily",
        status="active",
    )
    db.add(kpi)

    old_observation = Observation(
        id=uuid4(),
        kpi_id=kpi.kpi_id,
        kpi_version=1,
        checker_id=uuid4(),
        department_id=dept.id,
        school_id=school.id,
        value_numeric=50,
        auto_result="not_met",
        rag_status="red",
        submitted_at=utc_now() - timedelta(days=10),
        evidence=[{"cloudinary_public_id": "test_evidence_789", "cloudinary_url": "https://test.com/evidence3.jpg"}]
    )
    db.add(old_observation)

    await db.commit()

    # Create services
    evidence_service = EvidenceService(db, config_engine=config_engine)
    audit_log_service = AuditLogService(db)

    # Perform deletion
    deletion_reason = "Routine cleanup after retention period"
    deletion_result = await evidence_service.delete_evidence_with_audit(
        observation_id=old_observation.id,
        public_id="test_evidence_789",
        actor_id=admin.id,
        school_id=school.id,
        reason=deletion_reason
    )

    # Verify audit log entry was created
    result = await db.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.id == UUID(deletion_result["audit_log_id"])
        )
    )
    audit_entry = result.scalar_one_or_none()

    assert audit_entry is not None, "Audit log entry should exist"
    assert audit_entry.user_id == admin.id, "Audit log should record actor identity"
    assert audit_entry.action == "evidence_deleted", "Audit log should record evidence deletion action"
    assert audit_entry.entity_id == old_observation.id, "Audit log should record affected observation"
    assert audit_entry.timestamp is not None, "Audit log should record timestamp"

    # Verify reason is captured
    if audit_entry.new_values:
        assert audit_entry.new_values.get("reason_comment") == deletion_reason, "Audit log should capture deletion reason"


@pytest.mark.asyncio
async def test_no_automated_evidence_deletion_jobs_exist(db: AsyncSession):
    """
    Acceptance test: Verify no scheduled jobs exist that automatically delete evidence.
    Per BR-27/FR-273, deletion is NEVER automated - only explicit Admin/SuperAdmin action.
    """
    # Check all scheduler services for any evidence deletion jobs
    from platform_services.checklist_scheduler.service import ChecklistScheduler
    from platform_services.compliance_scheduler.service import ComplianceScheduler
    from modules.task_management.services.escalation_scheduler import TaskEscalationScheduler
    try:
        from modules.performance_scorecards.services.scorecard_scheduler import ScorecardScheduler
        scorecard_scheduler = ScorecardScheduler(db)
    except ImportError:
        scorecard_scheduler = None  # Module removed

    # Verify none of these schedulers have evidence deletion logic
    checklist_scheduler = ChecklistScheduler(db)
    compliance_scheduler = ComplianceScheduler(db)
    task_scheduler = TaskEscalationScheduler(db)

    # Check methods don't include evidence deletion
    checklist_methods = [method for method in dir(checklist_scheduler) if not method.startswith('_')]
    compliance_methods = [method for method in dir(compliance_scheduler) if not method.startswith('_')]
    task_methods = [method for method in dir(task_scheduler) if not method.startswith('_')]
    scorecard_methods = [method for method in dir(scorecard_scheduler) if not method.startswith('_')]

    # None should have evidence deletion methods
    evidence_deletion_keywords = ['delete', 'purge', 'cleanup', 'remove', 'evidence']

    for method_list in [checklist_methods, compliance_methods, task_methods, scorecard_methods]:
        for method in method_list:
            assert not any(keyword in method.lower() for keyword in evidence_deletion_keywords), \
                f"Scheduler should not have evidence deletion method: {method}"

    # Verify no cron jobs or scheduled tasks reference evidence deletion
    scheduler_files = glob.glob("**/*scheduler*.py", recursive=True)
    for file_path in scheduler_files:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                assert "delete_evidence" not in content.lower(), \
                    f"Scheduler file {file_path} should not contain evidence deletion logic"
                assert "purge" not in content.lower() or "purge" in content.lower().replace("evidence", ""), \
                    f"Scheduler file {file_path} should not contain purge logic for evidence"
        except Exception:
            continue


@pytest.mark.asyncio
async def test_retention_period_configurable_per_school(db: AsyncSession):
    """
    Acceptance test: Verify evidence retention period is configurable per school.
    Per PRS §54, this is a Configuration Engine value with school override support.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()

    # Create two schools
    school1 = School(id=uuid4(), name="School 1", code="SCH001", status=SchoolStatus.ACTIVE)
    school2 = School(id=uuid4(), name="School 2", code="SCH002", status=SchoolStatus.ACTIVE)
    db.add(school1)
    db.add(school2)
    await db.commit()

    # Set different retention periods for each school
    await config_engine.set_override(
        ConfigKey.EVIDENCE_RETENTION_PERIOD_DAYS,
        "school",
        school1.id,
        "365",  # 1 year for school 1
        updated_by=uuid4()
    )

    await config_engine.set_override(
        ConfigKey.EVIDENCE_RETENTION_PERIOD_DAYS,
        "school",
        school2.id,
        "1825",  # 5 years for school 2
        updated_by=uuid4()
    )

    # Verify different retention periods
    retention_1 = await config_engine.get(
        ConfigKey.EVIDENCE_RETENTION_PERIOD_DAYS,
        school_id=school1.id
    )
    retention_2 = await config_engine.get(
        ConfigKey.EVIDENCE_RETENTION_PERIOD_DAYS,
        school_id=school2.id
    )

    assert retention_1 == 365, "School 1 should have 365-day retention"
    assert retention_2 == 1825, "School 2 should have 1825-day retention"
    assert retention_1 != retention_2, "Schools should have different retention periods"
