"""
Acceptance tests for Notification Service wiring per PRS §49.
Verifies that all modules fire events through the real dispatch path.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import pytest
import uuid
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.notification_service.service import NotificationService, NotificationPayload
from platform_services.notification_service.providers import InAppProvider
from shared.platform_models import Notification, NotificationCategory, NotificationChannel, NotificationStatus
from shared.datetime_utils import utc_now


@pytest.mark.asyncio
async def test_discrepancy_creates_audit_failure_notification(db: AsyncSession):
    """
    Acceptance test: Triggering a Discrepancy creates an Audit Failure notification.
    Verifies category 2 (AUDIT_FAILURE) is used and cannot be muted.
    """
    from modules.audit_discrepancy.services.discrepancy_service import DiscrepancyService
    from shared.models import User, UserRole, UserStatus, School, SchoolStatus, Department, DepartmentStatus, DiscrepancyCategory, Observation, KPI, KRA
    
    # Setup: Create school, department, admin user, observation, discrepancy category
    school = School(id=uuid4(), name="Test School", code="TS001", status=SchoolStatus.ACTIVE)
    db.add(school)
    
    dept = Department(id=uuid4(), school_id=school.id, name="Test Dept", code="TD001", status=DepartmentStatus.ACTIVE)
    db.add(dept)
    
    auditor = User(
        id=uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="auditor@test.com",
        full_name="Test Auditor",
        school_id=school.id,
        roles=[UserRole.AUDITOR.value],
        status=UserStatus.ACTIVE,
    )
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
    
    category = DiscrepancyCategory(id=uuid4(), name="Test Category", status="active", allow_delegate=False)
    db.add(category)
    
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
        status="active"
    )
    db.add(kpi)
    
    observation = Observation(
        id=uuid4(),
        kpi_id=kpi.kpi_id,
        kpi_version=1,
        checker_id=uuid4(),
        department_id=dept.id,
        school_id=school.id,
        value_numeric=50,
        auto_result="not_met",
        rag_status="red",
        submitted_at=utc_now()
    )
    db.add(observation)
    
    await db.commit()
    
    # Create discrepancy service with real notification service
    notification_service = NotificationService(db)
    discrepancy_service = DiscrepancyService(db, notification_service=notification_service)
    
    db.add(auditor)
    await db.commit()
    
    # Raise discrepancy (must use Auditor role per PRS §12)
    discrepancy = await discrepancy_service.raise_discrepancy(
        observation_id=observation.id,
        category_id=category.id,
        school_id=school.id,
        department_id=dept.id,
        raised_by_user_id=auditor.id,
        description="Test discrepancy"
    )
    
    # Verify notification was created with correct category
    result = await db.execute(
        select(Notification).where(
            Notification.entity_id == discrepancy.id,
            Notification.entity_type == "discrepancy"
        )
    )
    notifications = result.scalars().all()
    
    assert len(notifications) > 0, "No notification created for discrepancy"
    
    notification = notifications[0]
    assert notification.category == NotificationCategory.AUDIT_FAILURE.value, \
        f"Expected category {NotificationCategory.AUDIT_FAILURE.value}, got {notification.category}"
    assert notification.status == NotificationStatus.PENDING
    
    # Verify mandatory category enforcement
    with pytest.raises(Exception):  # BusinessRuleError
        await notification_service.dispatch(
            NotificationPayload(
                user_id=admin.id,
                category=NotificationCategory.AUDIT_FAILURE.value,
                title="Test",
                body="Test",
                muted_categories={NotificationCategory.AUDIT_FAILURE.value}
            )
        )


@pytest.mark.asyncio
async def test_task_assignment_notification(db: AsyncSession):
    """
    Acceptance test: Task assignment creates TASK_ASSIGNMENT notification (category 3).
    """
    from modules.task_management.services.task_service import TaskService
    from shared.models import User, UserRole, UserStatus, School, SchoolStatus, Department, DepartmentStatus, TaskCompletionRule
    
    # Setup
    school = School(id=uuid4(), name="Test School", code="TS001", status=SchoolStatus.ACTIVE)
    db.add(school)
    
    dept = Department(id=uuid4(), school_id=school.id, name="Test Dept", code="TD001", status=DepartmentStatus.ACTIVE)
    db.add(dept)
    
    owner = User(
        id=uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="owner@test.com",
        full_name="Test Owner",
        school_id=school.id,
        roles=[UserRole.CHECKER.value],
        status=UserStatus.ACTIVE,
    )
    db.add(owner)
    
    await db.commit()
    
    # Create task with notification service
    notification_service = NotificationService(db)
    task_service = TaskService(db, notification_service=notification_service)
    
    # Create task
    task = await task_service.create_task(
        title="Test Task",
        owner_ids=[owner.id],
        completion_rule=TaskCompletionRule.ANY_OWNER,
        eta=utc_now() + timedelta(hours=24),
        school_id=school.id,
        created_by=owner.id
    )
    
    # Verify notification was created
    result = await db.execute(
        select(Notification).where(
            Notification.entity_id == task.id,
            Notification.entity_type == "task"
        )
    )
    notifications = result.scalars().all()
    
    assert len(notifications) > 0, "No notification created for task assignment"
    
    notification = notifications[0]
    assert notification.category == NotificationCategory.TASK_ASSIGNMENT.value, \
        f"Expected category {NotificationCategory.TASK_ASSIGNMENT.value}, got {notification.category}"


@pytest.mark.asyncio
async def test_escalation_notification_priority_order(db: AsyncSession):
    """
    Acceptance test: Verify fixed priority order (1-7) is enforced server-side.
    Escalation (1) and Audit Failure (2) cannot be muted by client requests.
    """
    notification_service = NotificationService(db)
    user_id = uuid4()
    
    # Test that mandatory categories cannot be muted
    mandatory_categories = [NotificationCategory.ESCALATION.value, NotificationCategory.AUDIT_FAILURE.value]
    
    for category in mandatory_categories:
        with pytest.raises(Exception):  # BusinessRuleError
            await notification_service.dispatch(
                NotificationPayload(
                    user_id=user_id,
                    category=category,
                    title="Test",
                    body="Test",
                    muted_categories={category}
                )
            )
    
    # Test that non-mandatory categories can be muted
    try:
        await notification_service.dispatch(
            NotificationPayload(
                user_id=user_id,
                category=NotificationCategory.TASK_ASSIGNMENT.value,
                title="Test",
                body="Test",
                muted_categories={NotificationCategory.TASK_ASSIGNMENT.value}
            )
        )
        # Should succeed without raising exception
    except Exception:
        pytest.fail("Non-mandatory category should be mutable")


@pytest.mark.asyncio
async def test_notification_priority_order_enforced(db: AsyncSession):
    """
    Acceptance test: Verify the notification priority enum has correct fixed order.
    """
    # Verify the enum values match the fixed priority order from PRS §49
    assert NotificationCategory.ESCALATION.value == 1
    assert NotificationCategory.AUDIT_FAILURE.value == 2
    assert NotificationCategory.TASK_ASSIGNMENT.value == 3
    assert NotificationCategory.DUE_TODAY.value == 4
    assert NotificationCategory.KPI_REMINDER.value == 5
    assert NotificationCategory.COMMENTS.value == 6
    assert NotificationCategory.INFORMATIONAL.value == 7
