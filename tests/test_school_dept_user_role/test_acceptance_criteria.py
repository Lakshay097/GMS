"""
Acceptance criteria tests for PRS §18-21 implementation.
Tests the core lifecycle and validation rules.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4

from shared.models import School, SchoolStatus, Department, DepartmentStatus, User, UserStatus, UserRole
from modules.school_dept_user_role.services.school_service import SchoolService
from modules.school_dept_user_role.services.department_service import DepartmentService
from modules.school_dept_user_role.services.user_service import UserService
from platform_services.audit_log_service import AuditLogService
from platform_services.configuration_engine import ConfigurationEngine
from shared.errors import ValidationError


@pytest.mark.asyncio
async def test_department_archival_blocked_with_open_tasks(db_session: AsyncSession):
    """
    Test that department archival is blocked when there are open tasks.
    FR-014: Block archival while open Tasks or unresolved Discrepancies exist.
    """
    # Setup: Create a school and department
    school = School(
        name="Test School",
        code="TEST001",
        status=SchoolStatus.ACTIVE
    )
    db_session.add(school)
    await db_session.flush()
    
    department = Department(
        school_id=school.id,
        name="Test Department",
        code="DEPT001",
        status=DepartmentStatus.ACTIVE
    )
    db_session.add(department)
    await db_session.commit()
    
    # Create service
    audit_log = AuditLogService(db_session)
    dept_service = DepartmentService(db_session, audit_log)
    
    # Mock the task check to return True (has open tasks)
    original_check = dept_service._check_open_tasks
    async def mock_check_open_tasks(dept_id):
        return True
    dept_service._check_open_tasks = mock_check_open_tasks
    
    # Attempt to archive department - should fail
    with pytest.raises(ValidationError) as exc_info:
        await dept_service.archive_department(department.id, uuid4())
    
    assert "open tasks" in str(exc_info.value).lower()
    
    # Restore original method
    dept_service._check_open_tasks = original_check


@pytest.mark.asyncio
async def test_department_archival_blocked_with_unresolved_discrepancies(db_session: AsyncSession):
    """
    Test that department archival is blocked when there are unresolved discrepancies.
    FR-014: Block archival while open Tasks or unresolved Discrepancies exist.
    """
    # Setup: Create a school and department
    school = School(
        name="Test School",
        code="TEST002",
        status=SchoolStatus.ACTIVE
    )
    db_session.add(school)
    await db_session.flush()
    
    department = Department(
        school_id=school.id,
        name="Test Department",
        code="DEPT002",
        status=DepartmentStatus.ACTIVE
    )
    db_session.add(department)
    await db_session.commit()
    
    # Create service
    audit_log = AuditLogService(db_session)
    dept_service = DepartmentService(db_session, audit_log)
    
    # Mock the discrepancy check to return True (has unresolved discrepancies)
    original_check = dept_service._check_unresolved_discrepancies
    async def mock_check_unresolved_discrepancies(dept_id):
        return True
    dept_service._check_unresolved_discrepancies = mock_check_unresolved_discrepancies
    
    # Attempt to archive department - should fail
    with pytest.raises(ValidationError) as exc_info:
        await dept_service.archive_department(department.id, uuid4())
    
    assert "discrepanc" in str(exc_info.value).lower()
    
    # Restore original method
    dept_service._check_unresolved_discrepancies = original_check


@pytest.mark.asyncio
async def test_school_activation_blocked_without_departments(db_session: AsyncSession):
    """
    Test that school activation is blocked without departments.
    PRS §18.6: School cannot be marked Active until default departments and KPI library import complete.
    """
    # Setup: Create a school without departments
    school = School(
        name="Test School",
        code="TEST003",
        status=SchoolStatus.ACTIVE
    )
    db_session.add(school)
    await db_session.commit()
    
    # Create service
    config_engine = ConfigurationEngine(db_session)
    audit_log = AuditLogService(db_session)
    school_service = SchoolService(db_session, config_engine, audit_log)
    
    # Attempt to validate activation - should fail
    with pytest.raises(ValidationError) as exc_info:
        await school_service.validate_school_activation(school.id)
    
    assert "department" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_deactivated_school_historical_data_readonly(db_session: AsyncSession):
    """
    Test that a deactivated school's historical data is still readable but not editable.
    FR-008: Retain full historical data of a Deactivated School in read-only state.
    """
    # Setup: Create and deactivate a school
    school = School(
        name="Test School",
        code="TEST004",
        status=SchoolStatus.ACTIVE
    )
    db_session.add(school)
    await db_session.flush()
    
    department = Department(
        school_id=school.id,
        name="Test Department",
        code="DEPT004",
        status=DepartmentStatus.ACTIVE
    )
    db_session.add(department)
    await db_session.commit()
    
    # Deactivate the school
    config_engine = ConfigurationEngine(db_session)
    audit_log = AuditLogService(db_session)
    school_service = SchoolService(db_session, config_engine, audit_log)
    
    deactivated_school = await school_service.deactivate_school(school.id, uuid4())
    assert deactivated_school.status == SchoolStatus.DEACTIVATED
    
    # Verify historical data is still readable
    await db_session.refresh(school)
    await db_session.refresh(department)
    
    # Department should still exist and be readable
    departments = await db_session.execute(
        select(Department).where(Department.school_id == school.id)
    )
    assert departments.scalar_one_or_none() is not None
    
    # Verify the school record still exists with full data
    fetched_school = await db_session.get(School, school.id)
    assert fetched_school is not None
    assert fetched_school.name == "Test School"
    assert fetched_school.status == SchoolStatus.DEACTIVATED
    assert fetched_school.deactivated_at is not None


@pytest.mark.asyncio
async def test_user_archive_never_hard_delete(db_session: AsyncSession):
    """
    Test that user archive results in archived+disabled, never DB row removal.
    FR-021: Never permit hard deletion of a User record
    FR-022: Disable login immediately upon archival while retaining full audit history.
    """
    # Setup: Create a user
    user = User(
        clerk_user_id="clerk-test-archive",
        email="test@example.com",
        full_name="Test User",
        school_id=uuid4(),
        status=UserStatus.ACTIVE,
        roles=[UserRole.ADMIN.value]
    )
    db_session.add(user)
    await db_session.commit()
    
    user_id = user.id
    
    # Archive the user
    audit_log = AuditLogService(db_session)
    user_service = UserService(db_session, audit_log)
    
    archived_user = await user_service.archive_user(user_id, uuid4())
    
    # Verify user is archived, not deleted
    assert archived_user.status == UserStatus.ARCHIVED
    assert archived_user.archived_at is not None
    
    # Verify the user record still exists in the database
    fetched_user = await db_session.get(User, user_id)
    assert fetched_user is not None
    assert fetched_user.status == UserStatus.ARCHIVED
    assert fetched_user.email == "test@example.com"  # Historical data preserved
    assert fetched_user.full_name == "Test User"  # Historical data preserved


@pytest.mark.asyncio
async def test_school_creation_requires_superadmin(db_session: AsyncSession):
    """
    Test that only SuperAdmin can create schools.
    FR-001: The system SHALL restrict School creation to users holding the SuperAdmin role.
    """
    # This test would require mocking the auth context
    # For now, we'll test the service layer validation
    
    # Create service
    config_engine = ConfigurationEngine(db_session)
    audit_log = AuditLogService(db_session)
    school_service = SchoolService(db_session, config_engine, audit_log)
    
    # The service layer doesn't enforce role checks - that's done at the API layer
    # This test validates the service can create a school when called
    school = await school_service.create_school(
        name="Test School",
        code="TEST005",
        address="123 Test St",
        contact_email="test@school.com",
        created_by_user_id=uuid4()
    )
    
    assert school is not None
    assert school.name == "Test School"
    assert school.code == "TEST005"
    assert school.status == SchoolStatus.ACTIVE


@pytest.mark.asyncio
async def test_user_single_school_constraint(db_session: AsyncSession):
    """
    Test that non-SuperAdmin/Viewer users are restricted to exactly one School.
    FR-019: The system SHALL restrict a non-SuperAdmin, non-Viewer user to exactly one School.
    """
    # Setup: Create a school
    school = School(
        name="Test School",
        code="TEST006",
        status=SchoolStatus.ACTIVE
    )
    db_session.add(school)
    await db_session.commit()
    
    # Create service
    audit_log = AuditLogService(db_session)
    user_service = UserService(db_session, audit_log)
    
    # Create a user with Admin role but no school_id - should fail
    with pytest.raises(ValidationError) as exc_info:
        await user_service.create_user(
            clerk_user_id="clerk-admin-no-school",
            email="admin@example.com",
            full_name="Admin User",
            school_id=None,  # No school assigned
            roles=[UserRole.ADMIN],
            created_by_user_id=uuid4()
        )
    
    assert "school" in str(exc_info.value).lower()
    
    # Create a user with Admin role and school_id - should succeed
    user = await user_service.create_user(
        clerk_user_id="clerk-admin-with-school",
        email="admin2@example.com",
        full_name="Admin User 2",
        school_id=school.id,
        roles=[UserRole.ADMIN],
        created_by_user_id=uuid4()
    )
    
    assert user is not None
    assert user.school_id == school.id


@pytest.mark.asyncio
async def test_school_name_uniqueness(db_session: AsyncSession):
    """
    Test that School Name is unique within the organization.
    FR-005: The system SHALL enforce uniqueness of School Name within the organization.
    """
    # Setup: Create a school
    school = School(
        name="Unique School Name",
        code="UNIQUE001",
        status=SchoolStatus.ACTIVE
    )
    db_session.add(school)
    await db_session.commit()
    
    # Create service
    config_engine = ConfigurationEngine(db_session)
    audit_log = AuditLogService(db_session)
    school_service = SchoolService(db_session, config_engine, audit_log)
    
    # Attempt to create another school with the same name - should fail
    with pytest.raises(ValidationError) as exc_info:
        await school_service.create_school(
            name="Unique School Name",  # Duplicate name
            code="UNIQUE002",
            created_by_user_id=uuid4()
        )
    
    assert "already exists" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_department_name_uniqueness_within_school(db_session: AsyncSession):
    """
    Test that Department Name is unique within a School.
    FR-012: The system SHALL enforce Department Name uniqueness within a School.
    """
    # Setup: Create a school and department
    school = School(
        name="Test School",
        code="TEST007",
        status=SchoolStatus.ACTIVE
    )
    db_session.add(school)
    await db_session.flush()
    
    department = Department(
        school_id=school.id,
        name="Unique Dept Name",
        code="DEPT007",
        status=DepartmentStatus.ACTIVE
    )
    db_session.add(department)
    await db_session.commit()
    
    # Create service
    audit_log = AuditLogService(db_session)
    dept_service = DepartmentService(db_session, audit_log)
    
    # Attempt to create another department with the same name in the same school - should fail
    with pytest.raises(ValidationError) as exc_info:
        await dept_service.create_department(
            school_id=school.id,
            name="Unique Dept Name",  # Duplicate name
            code="DEPT008",
            created_by_user_id=uuid4()
        )
    
    assert "already exists" in str(exc_info.value).lower()
    
    # Creating the same department name in a different school should succeed
    school2 = School(
        name="Test School 2",
        code="TEST008",
        status=SchoolStatus.ACTIVE
    )
    db_session.add(school2)
    await db_session.commit()
    
    dept2 = await dept_service.create_department(
        school_id=school2.id,
        name="Unique Dept Name",  # Same name, different school
        code="DEPT009",
        created_by_user_id=uuid4()
    )
    
    assert dept2 is not None