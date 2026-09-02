"""
School-level scorecard tests â PRS Â§29.

Tests that:
1. School-level scorecards can be generated with SCHOOL enum value
2. Notification logic handles SCHOOL subject type
3. Invalid/nonexistent school_id is handled gracefully

Business rules enforced:
  R-18/BR-14/C6   Scorecards are GENERATED, never updated or deleted.
  BR-14           Worst-status-wins for RAG computation at school level.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

pytest.importorskip("modules.performance_scorecards", reason="performance_scorecards module removed")
from modules.performance_scorecards.services.scorecard_service import ScorecardService
from shared.platform_models import (
    Scorecard,
    ScorecardSubjectType,
    RagStatus,
)
from shared.models import Department, DepartmentStatus, User, UserStatus, UserRole, School, SchoolStatus
from shared.datetime_utils import utc_now

# Module removed  skip entire test file



@pytest.mark.asyncio
class TestSchoolLevelScorecards:
    """
    Test school-level scorecard generation per PRS Â§29.
    """

    async def test_school_scorecard_generation_succeeds(
        self,
        db: AsyncSession,
        school,
    ):
        """
        Test that school-level scorecards can be generated with SCHOOL enum value.
        
        Given:
          - A valid school
        When:
          - Generate a school-level scorecard
        Then:
          - Scorecard is created successfully with SCHOOL subject type
          - No AttributeError occurs (regression test for missing enum value)
        """
        # Act
        cycle_start = date(2026, 8, 1)
        cycle_end = date(2026, 8, 31)
        
        service = ScorecardService(db)
        school_scorecard = await service.generate(
            subject_type=ScorecardSubjectType.SCHOOL,
            subject_id=school.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()

        # Assert - School scorecard created successfully
        assert school_scorecard.subject_type == ScorecardSubjectType.SCHOOL
        assert school_scorecard.subject_id == school.id
        assert school_scorecard.version == 1
        assert school_scorecard.superseded_by_id is None

    async def test_school_notification_to_admins(
        self,
        db: AsyncSession,
        school,
        department,
        user,
    ):
        """
        Test that school-level scorecard notifications go to school admins.
        
        Given:
          - A school with admin users
          - A school-level scorecard is generated
        When:
          - Generate school-level scorecard
        Then:
          - Notifications are dispatched to all school admins
        """
        # Arrange - Create an admin user
        admin = User(
            id=uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
            email=f"admin-{uuid4()}@test.com",
            full_name="Test Admin",
            school_id=school.id,
            department_id=department.id,
            status=UserStatus.ACTIVE,
            roles=[UserRole.ADMIN.value],
            language_preference="en",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(admin)
        await db.commit()

        # Act
        cycle_start = date(2026, 8, 1)
        cycle_end = date(2026, 8, 31)
        
        service = ScorecardService(db)
        school_scorecard = await service.generate(
            subject_type=ScorecardSubjectType.SCHOOL,
            subject_id=school.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()

        # Assert - Check notification was created for admin
        from shared.platform_models import Notification
        result = await db.execute(
            select(Notification).where(Notification.user_id == admin.id)
        )
        notifications = result.scalars().all()
        
        assert len(notifications) > 0
        # Find the scorecard notification
        scorecard_notifications = [
            n for n in notifications 
            if "School Scorecard Generated" in n.title
        ]
        assert len(scorecard_notifications) > 0

    async def test_school_scorecard_invalid_school_id(
        self,
        db: AsyncSession,
    ):
        """
        Test that invalid school_id is handled gracefully.
        
        Given:
          - A non-existent school_id
        When:
          - Attempt to generate school-level scorecard
        Then:
          - Service handles gracefully (returns NOT_SUBMITTED with no data)
        """
        # Act
        cycle_start = date(2026, 8, 1)
        cycle_end = date(2026, 8, 31)
        fake_school_id = uuid4()
        
        service = ScorecardService(db)
        school_scorecard = await service.generate(
            subject_type=ScorecardSubjectType.SCHOOL,
            subject_id=fake_school_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()

        # Assert - Should generate with NOT_SUBMITTED status (no data available)
        assert school_scorecard.subject_type == ScorecardSubjectType.SCHOOL
        assert school_scorecard.subject_id == fake_school_id
        assert school_scorecard.rag_status == RagStatus.NOT_SUBMITTED
        assert school_scorecard.pct_kpis_met == Decimal("0.00")
        assert school_scorecard.open_discrepancy_count == 0

    async def test_school_scorecard_versioning(
        self,
        db: AsyncSession,
        school,
    ):
        """
        Test that school-level scorecards support versioning.
        
        Given:
          - A school-level scorecard v1 exists
        When:
          - Generate another school-level scorecard for the same cycle
        Then:
          - v2 is created with superseded_by_id pointing from v1 to v2
        """
        # Arrange - Generate v1
        cycle_start = date(2026, 8, 1)
        cycle_end = date(2026, 8, 31)
        
        service = ScorecardService(db)
        v1 = await service.generate(
            subject_type=ScorecardSubjectType.SCHOOL,
            subject_id=school.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        assert v1.version == 1
        assert v1.superseded_by_id is None
        
        # Act - Generate v2
        v2 = await service.generate(
            subject_type=ScorecardSubjectType.SCHOOL,
            subject_id=school.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        # Assert
        assert v2.version == 2
        assert v2.superseded_by_id is None
        assert v2.id != v1.id
        
        await db.refresh(v1)
        assert v1.superseded_by_id == v2.id
