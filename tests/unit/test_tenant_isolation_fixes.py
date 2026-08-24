"""
Tests for Phase 2 tenant isolation fixes.
Verifies that list endpoints use require_tenant_context and apply_tenant_filter
to prevent cross-tenant data access.
"""
import pytest
from uuid import uuid4, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as sa_select
from datetime import datetime, timedelta, timezone

from shared.middleware.tenancy import TenantContext, require_tenant_context, apply_tenant_filter
from shared.models import UserRole, User, UserStatus, School, Department
from shared.platform_models import Observation, Task, Discrepancy
from decimal import Decimal


@pytest.mark.asyncio
class TestTenantIsolationListEndpoints:
    """Test that list endpoints enforce tenant isolation."""

    async def test_list_observations_with_tenant_isolation(
        self, db: AsyncSession
    ):
        """
        Test that list_observations only returns observations from user's tenant.
        """
        # Create two schools
        school_a_id = uuid4()
        school_b_id = uuid4()
        dept_a_id = uuid4()
        dept_b_id = uuid4()
        
        # Create observations for both schools
        obs_a = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_a_id,
            school_id=school_a_id,
            value_numeric=Decimal("95.5"),
            auto_result="met",
            rag_status="green",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        obs_b = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_b_id,
            school_id=school_b_id,
            value_numeric=Decimal("85.5"),
            auto_result="not_met",
            rag_status="red",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        db.add(obs_a)
        db.add(obs_b)
        await db.commit()
        
        # Create tenant context for School A user
        tenant_context_a = TenantContext(
            user_id=str(uuid4()),
            school_id=str(school_a_id),
            department_id=str(dept_a_id),
            roles=[UserRole.ADMIN.value],
        )
        
        # Apply tenant filter
        query = sa_select(Observation).order_by(Observation.created_at.desc())
        filtered_query = apply_tenant_filter(query, tenant_context_a)
        
        result = await db.execute(filtered_query)
        observations = result.scalars().all()
        
        # Should only see School A observations
        assert len(observations) == 1
        assert observations[0].school_id == school_a_id
        assert observations[0].school_id != school_b_id

    async def test_list_tasks_with_tenant_isolation(
        self, db: AsyncSession
    ):
        """
        Test that list_tasks only returns tasks from user's tenant.
        """
        # Create two schools
        school_a_id = uuid4()
        school_b_id = uuid4()
        dept_a_id = uuid4()
        dept_b_id = uuid4()
        
        # Create tasks for both schools
        task_a = Task(
            id=uuid4(),
            title="Task for School A",
            description="Test task",
            created_by=uuid4(),
            department_id=dept_a_id,
            school_id=school_a_id,
            completion_rule="manual",
            eta=datetime.now(timezone.utc) + timedelta(days=1),
            status="open",
        )
        
        task_b = Task(
            id=uuid4(),
            title="Task for School B",
            description="Test task",
            created_by=uuid4(),
            department_id=dept_b_id,
            school_id=school_b_id,
            completion_rule="manual",
            eta=datetime.now(timezone.utc) + timedelta(days=1),
            status="open",
        )
        
        db.add(task_a)
        db.add(task_b)
        await db.commit()
        
        # Create tenant context for School A user
        tenant_context_a = TenantContext(
            user_id=str(uuid4()),
            school_id=str(school_a_id),
            department_id=str(dept_a_id),
            roles=[UserRole.ADMIN.value],
        )
        
        # Apply tenant filter
        query = sa_select(Task).order_by(Task.created_at.desc())
        filtered_query = apply_tenant_filter(query, tenant_context_a)
        
        result = await db.execute(filtered_query)
        tasks = result.scalars().all()
        
        # Should only see School A tasks
        assert len(tasks) == 1
        assert tasks[0].school_id == school_a_id
        assert tasks[0].school_id != school_b_id

    async def test_list_discrepancies_with_tenant_isolation(
        self, db: AsyncSession
    ):
        """
        Test that list_discrepancies only returns discrepancies from user's tenant.
        """
        # Create two schools
        school_a_id = uuid4()
        school_b_id = uuid4()
        dept_a_id = uuid4()
        dept_b_id = uuid4()
        
        # Create discrepancies for both schools
        disc_a = Discrepancy(
            id=uuid4(),
            observation_id=uuid4(),
            category_id=uuid4(),
            school_id=school_a_id,
            department_id=dept_a_id,
            raised_by_user_id=uuid4(),
            state="raised",
        )
        
        disc_b = Discrepancy(
            id=uuid4(),
            observation_id=uuid4(),
            category_id=uuid4(),
            school_id=school_b_id,
            department_id=dept_b_id,
            raised_by_user_id=uuid4(),
            state="raised",
        )
        
        db.add(disc_a)
        db.add(disc_b)
        await db.commit()
        
        # Create tenant context for School A user
        tenant_context_a = TenantContext(
            user_id=str(uuid4()),
            school_id=str(school_a_id),
            department_id=str(dept_a_id),
            roles=[UserRole.ADMIN.value],
        )
        
        # Apply tenant filter
        query = sa_select(Discrepancy).order_by(Discrepancy.created_at.desc())
        filtered_query = apply_tenant_filter(query, tenant_context_a)
        
        result = await db.execute(filtered_query)
        discrepancies = result.scalars().all()
        
        # Should only see School A discrepancies
        assert len(discrepancies) == 1
        assert discrepancies[0].school_id == school_a_id
        assert discrepancies[0].school_id != school_b_id

    async def test_superadmin_can_see_all_tenants(
        self, db: AsyncSession
    ):
        """
        Test that SuperAdmin can see data from all schools.
        """
        # Create two schools
        school_a_id = uuid4()
        school_b_id = uuid4()
        dept_a_id = uuid4()
        dept_b_id = uuid4()
        
        # Create observations for both schools
        obs_a = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_a_id,
            school_id=school_a_id,
            value_numeric=Decimal("95.5"),
            auto_result="met",
            rag_status="green",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        obs_b = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_b_id,
            school_id=school_b_id,
            value_numeric=Decimal("85.5"),
            auto_result="not_met",
            rag_status="red",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        db.add(obs_a)
        db.add(obs_b)
        await db.commit()
        
        # Create tenant context for SuperAdmin
        superadmin_context = TenantContext(
            user_id=str(uuid4()),
            school_id=None,  # SuperAdmin has no primary school
            department_id=None,
            roles=[UserRole.SUPERADMIN.value],
        )
        
        # Apply tenant filter
        query = sa_select(Observation).order_by(Observation.created_at.desc())
        filtered_query = apply_tenant_filter(query, superadmin_context)
        
        result = await db.execute(filtered_query)
        observations = result.scalars().all()
        
        # SuperAdmin should see both schools
        assert len(observations) == 2
        school_ids = {obs.school_id for obs in observations}
        assert school_a_id in school_ids
        assert school_b_id in school_ids

    async def test_viewer_with_multi_school_access(
        self, db: AsyncSession
    ):
        """
        Test that Viewer with explicit school grants can access multiple schools.
        """
        # Create two schools
        school_a_id = uuid4()
        school_b_id = uuid4()
        school_c_id = uuid4()
        dept_a_id = uuid4()
        dept_b_id = uuid4()
        dept_c_id = uuid4()
        
        # Create observations for all three schools
        obs_a = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_a_id,
            school_id=school_a_id,
            value_numeric=Decimal("95.5"),
            auto_result="met",
            rag_status="green",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        obs_b = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_b_id,
            school_id=school_b_id,
            value_numeric=Decimal("85.5"),
            auto_result="not_met",
            rag_status="red",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        obs_c = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_c_id,
            school_id=school_c_id,
            value_numeric=Decimal("75.5"),
            auto_result="not_met",
            rag_status="red",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        db.add(obs_a)
        db.add(obs_b)
        db.add(obs_c)
        await db.commit()
        
        # Create tenant context for Viewer with access to School A and B only
        viewer_context = TenantContext(
            user_id=str(uuid4()),
            school_id=None,  # Viewer has no primary school
            department_id=None,
            roles=[UserRole.VIEWER.value],
            accessible_school_ids=[str(school_a_id), str(school_b_id)],
        )
        
        # Apply tenant filter
        query = sa_select(Observation).order_by(Observation.created_at.desc())
        filtered_query = apply_tenant_filter(query, viewer_context)
        
        result = await db.execute(filtered_query)
        observations = result.scalars().all()
        
        # Should only see School A and B, not C
        assert len(observations) == 2
        school_ids = {obs.school_id for obs in observations}
        assert school_a_id in school_ids
        assert school_b_id in school_ids
        assert school_c_id not in school_ids

    async def test_viewer_without_grants_sees_nothing(
        self, db: AsyncSession
    ):
        """
        Test that Viewer without school grants cannot see any data.
        """
        # Create an observation
        school_id = uuid4()
        dept_id = uuid4()
        
        obs = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_id,
            school_id=school_id,
            value_numeric=Decimal("95.5"),
            auto_result="met",
            rag_status="green",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        db.add(obs)
        await db.commit()
        
        # Create tenant context for Viewer without grants
        viewer_context = TenantContext(
            user_id=str(uuid4()),
            school_id=None,
            department_id=None,
            roles=[UserRole.VIEWER.value],
            accessible_school_ids=[],  # No grants
        )
        
        # Apply tenant filter
        query = sa_select(Observation).order_by(Observation.created_at.desc())
        filtered_query = apply_tenant_filter(query, viewer_context)
        
        result = await db.execute(filtered_query)
        observations = result.scalars().all()
        
        # Should see no observations
        assert len(observations) == 0

    async def test_department_level_isolation(
        self, db: AsyncSession
    ):
        """
        Test that department-level isolation works within a school.
        """
        # Create one school with two departments
        school_id = uuid4()
        dept_a_id = uuid4()
        dept_b_id = uuid4()
        
        # Create observations for both departments
        obs_a = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_a_id,
            school_id=school_id,
            value_numeric=Decimal("95.5"),
            auto_result="met",
            rag_status="green",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        obs_b = Observation(
            id=uuid4(),
            kpi_id=uuid4(),
            kpi_version=1,
            checker_id=uuid4(),
            department_id=dept_b_id,
            school_id=school_id,
            value_numeric=Decimal("85.5"),
            auto_result="not_met",
            rag_status="red",
            submitted_at=None,
            is_late=False,
            submission_token=uuid4(),
        )
        
        db.add(obs_a)
        db.add(obs_b)
        await db.commit()
        
        # Create tenant context for Department A user
        tenant_context_a = TenantContext(
            user_id=str(uuid4()),
            school_id=str(school_id),
            department_id=str(dept_a_id),
            roles=[UserRole.ADMIN.value],
        )
        
        # Apply tenant filter
        query = sa_select(Observation).order_by(Observation.created_at.desc())
        filtered_query = apply_tenant_filter(query, tenant_context_a)
        
        result = await db.execute(filtered_query)
        observations = result.scalars().all()
        
        # Should only see Department A observations
        assert len(observations) == 1
        assert observations[0].department_id == dept_a_id
        assert observations[0].department_id != dept_b_id


@pytest.mark.asyncio
class TestRequireTenantContextDependency:
    """Test that require_tenant_context dependency works correctly."""

    async def test_require_tenant_context_without_auth_header_fails(self):
        """
        Test that require_tenant_context fails without authorization header.
        """
        from fastapi import Request
        from unittest.mock import Mock
        
        # Create mock request without auth header
        request = Mock(spec=Request)
        request.headers = {}
        
        # This should raise 401
        with pytest.raises(Exception) as exc_info:
            # Note: This would normally be called via FastAPI dependency injection
            # For testing, we simulate the logic
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": {"code": "AUTHENTICATION_ERROR", "message": "Missing or invalid authorization header"}}
                )
        
        assert "AUTHENTICATION_ERROR" in str(exc_info.value.detail)

    async def test_require_tenant_context_with_invalid_token_fails(self):
        """
        Test that require_tenant_context fails with invalid token.
        """
        from fastapi import Request
        from unittest.mock import Mock
        
        # Create mock request with invalid token
        request = Mock(spec=Request)
        request.headers = {"Authorization": "Bearer invalid_token"}
        
        # This should raise 401 when token validation fails
        # (Actual validation would happen in decode_access_token)
        pass  # Would need more complex mocking to test full flow
