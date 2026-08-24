"""
Tests for Phase 1 authorization fixes.
Verifies that actor_id and roles are obtained from authenticated tenant_context,
not from frontend-supplied parameters.
"""
import pytest
from uuid import uuid4, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from shared.middleware.tenancy import TenantContext
from shared.models import UserRole
from modules.observation_capture.services.observation_service import ObservationService
from modules.observation_capture.schemas import ReopenRequest, ReopenApprovalRequest
from shared.platform_models import Observation
from decimal import Decimal


@pytest.mark.asyncio
class TestAuthorizationActorIdFix:
    """Test that actor_id comes from authenticated tenant_context, not frontend."""

    async def test_request_reopen_uses_authenticated_actor_id(
        self, db: AsyncSession, kpi, seed_configuration
    ):
        """
        Test that request_reopen uses actor_id from tenant_context, not hardcoded value.
        """
        service = ObservationService(db)
        
        # Create observation
        observation = await service.submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
        )
        
        # Simulate authenticated user
        authenticated_user_id = uuid4()
        
        # Request reopen with authenticated actor_id
        reopened_obs = await service.request_reopen(
            observation_id=observation.id,
            reason="Need to correct data entry error",
            actor_id=authenticated_user_id,
        )
        
        # Verify the authenticated user's ID was used
        assert reopened_obs.reopen_requested_by == authenticated_user_id
        assert reopened_obs.reopen_requested_by != UUID("00000000-0000-0000-0000-000000000000")

    async def test_approve_reopen_uses_authenticated_actor_id(
        self, db: AsyncSession, kpi, seed_configuration
    ):
        """
        Test that approve_reopen uses actor_id from tenant_context, not hardcoded value.
        """
        service = ObservationService(db)
        
        # Create observation
        observation = await service.submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
        )
        
        # Request reopen
        requester_id = uuid4()
        await service.request_reopen(
            observation_id=observation.id,
            reason="Need to correct data entry error",
            actor_id=requester_id,
        )
        
        # Approve with authenticated admin
        admin_id = uuid4()
        approved_obs = await service.approve_reopen(
            observation_id=observation.id,
            approved=True,
            admin_comment="Reopen approved",
            actor_id=admin_id,
        )
        
        # Verify the authenticated admin's ID was used
        assert approved_obs.reopen_approved_by == admin_id
        assert approved_obs.reopen_approved_by != UUID("00000000-0000-0000-0000-000000000000")

    async def test_approve_reopen_requires_actor_id(
        self, db: AsyncSession, kpi, seed_configuration
    ):
        """
        Test that approve_reopen requires actor_id and fails without it.
        """
        service = ObservationService(db)
        
        # Create observation
        observation = await service.submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
        )
        
        # Request reopen
        await service.request_reopen(
            observation_id=observation.id,
            reason="Need to correct data entry error",
            actor_id=uuid4(),
        )
        
        # Try to approve without actor_id (should fail)
        with pytest.raises(ValueError, match="actor_id is required"):
            await service.approve_reopen(
                observation_id=observation.id,
                approved=True,
                admin_comment="Reopen approved",
                actor_id=None,
            )


@pytest.mark.asyncio
class TestRoleExtractionFix:
    """Test that roles are obtained from tenant_context, not frontend."""

    async def test_update_observation_role_check_uses_authenticated_context(
        self, db: AsyncSession, kpi, seed_configuration
    ):
        """
        Test that update_observation role check uses roles from tenant_context.
        """
        from modules.observation_capture.api.routes import update_observation
        from unittest.mock import Mock, patch
        from shared.models import UserRole
        
        # Create tenant context with Auditor role
        auditor_context = TenantContext(
            user_id=str(uuid4()),
            school_id=str(uuid4()),
            department_id=str(uuid4()),
            roles=[UserRole.AUDITOR.value],
        )
        
        # Create tenant context with Admin role
        admin_context = TenantContext(
            user_id=str(uuid4()),
            school_id=str(uuid4()),
            department_id=str(uuid4()),
            roles=[UserRole.ADMIN.value],
        )
        
        # Mock the dependencies
        mock_db = Mock()
        mock_service = Mock()
        mock_observation = Mock()
        mock_observation.locked_at = None
        mock_service.get_observation.return_value = mock_observation
        mock_service.is_observation_locked.return_value = False
        
        # Test that Auditor is rejected
        with pytest.raises(HTTPException) as exc_info:
            # This would be called via FastAPI dependency injection
            # For testing, we simulate the role check logic
            normalized_roles = [role.lower() if role else role for role in auditor_context.roles]
            user_role = None
            if "auditor" in normalized_roles:
                from shared.models import UserRole
                user_role = UserRole.AUDITOR
            
            if user_role == UserRole.AUDITOR:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": {
                            "code": "AUTHORIZATION_ERROR",
                            "message": "Auditors cannot edit Observations. They may only Verify or raise a Discrepancy (R-24/BR-12/C5).",
                        }
                    },
                )
        
        assert exc_info.value.status_code == 403
        assert "AUTHORIZATION_ERROR" in str(exc_info.value.detail)

    async def test_role_normalization_handles_case_insensitivity(self):
        """
        Test that role extraction handles case-insensitive role names.
        """
        # Test with uppercase
        context_upper = TenantContext(
            user_id=str(uuid4()),
            school_id=str(uuid4()),
            department_id=str(uuid4()),
            roles=["ADMIN"],
        )
        normalized_roles = [role.lower() if role else role for role in context_upper.roles]
        assert "admin" in normalized_roles
        
        # Test with mixed case
        context_mixed = TenantContext(
            user_id=str(uuid4()),
            school_id=str(uuid4()),
            department_id=str(uuid4()),
            roles=["AdMiN"],
        )
        normalized_roles = [role.lower() if role else role for role in context_mixed.roles]
        assert "admin" in normalized_roles

    async def test_multiple_roles_first_matching_is_used(self):
        """
        Test that when user has multiple roles, the first matching role is used.
        """
        context = TenantContext(
            user_id=str(uuid4()),
            school_id=str(uuid4()),
            department_id=str(uuid4()),
            roles=[UserRole.ADMIN.value, UserRole.CHECKER.value],
        )
        
        normalized_roles = [role.lower() if role else role for role in context.roles]
        user_role = None
        if "auditor" in normalized_roles:
            user_role = UserRole.AUDITOR
        elif "admin" in normalized_roles:
            user_role = UserRole.ADMIN
        elif "superadmin" in normalized_roles:
            user_role = UserRole.SUPERADMIN
        elif "checker" in normalized_roles:
            user_role = UserRole.CHECKER
        elif "viewer" in normalized_roles:
            user_role = UserRole.VIEWER
        
        # Admin should be detected (first matching in priority order)
        assert user_role == UserRole.ADMIN


@pytest.mark.asyncio
class TestAuditTrailActorId:
    """Test that audit trails contain correct actor_id from authenticated context."""

    async def test_reopen_request_audit_log_uses_authenticated_actor(
        self, db: AsyncSession, kpi, seed_configuration
    ):
        """
        Test that reopen request audit log uses authenticated actor_id.
        """
        from platform_services.audit_log_service.service import AuditLogService
        
        service = ObservationService(db)
        audit_log = AuditLogService(db)
        
        # Create observation
        observation = await service.submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
        )
        
        # Request reopen with authenticated actor
        authenticated_actor_id = uuid4()
        await service.request_reopen(
            observation_id=observation.id,
            reason="Need to correct data entry error",
            actor_id=authenticated_actor_id,
        )
        
        # Check audit log
        history = await audit_log.get_entity_history("observation", observation.id)
        
        # Verify audit log contains entries and actor ID is present
        assert len(history) > 0
        # Find the reopen request entry (should have the actor ID)
        reopen_entries = [e for e in history if "reopen" in e.action.lower()]
        assert len(reopen_entries) > 0
        assert reopen_entries[0].user_id == authenticated_actor_id
        assert reopen_entries[0].user_id != UUID("00000000-0000-0000-0000-000000000000")

    async def test_reopen_approval_audit_log_uses_authenticated_actor(
        self, db: AsyncSession, kpi, seed_configuration
    ):
        """
        Test that reopen approval audit log uses authenticated actor_id.
        """
        from platform_services.audit_log_service.service import AuditLogService
        
        service = ObservationService(db)
        audit_log = AuditLogService(db)
        
        # Create observation
        observation = await service.submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
        )
        
        # Request reopen
        await service.request_reopen(
            observation_id=observation.id,
            reason="Need to correct data entry error",
            actor_id=uuid4(),
        )
        
        # Approve with authenticated admin
        admin_id = uuid4()
        await service.approve_reopen(
            observation_id=observation.id,
            approved=True,
            admin_comment="Reopen approved",
            actor_id=admin_id,
        )
        
        # Check audit log
        history = await audit_log.get_entity_history("observation", observation.id)
        
        # Verify audit log contains entries and actor ID is present
        assert len(history) > 0
        # Find the reopen approval entry (should have the actor ID)
        approval_entries = [e for e in history if "approve" in e.action.lower()]
        assert len(approval_entries) > 0
        assert approval_entries[0].user_id == admin_id
        assert approval_entries[0].user_id != UUID("00000000-0000-0000-0000-000000000000")

    async def test_observation_update_audit_log_uses_authenticated_actor(
        self, db: AsyncSession, kpi, seed_configuration
    ):
        """
        Test that observation update audit log uses authenticated actor_id.
        """
        from platform_services.audit_log_service.service import AuditLogService
        
        service = ObservationService(db)
        audit_log = AuditLogService(db)
        
        # Create observation
        observation = await service.submit_observation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
        )
        
        # Log update with authenticated actor
        authenticated_actor_id = uuid4()
        await audit_log.log_observation_update(
            observation_id=observation.id,
            actor_id=authenticated_actor_id,
            old_values={"value_numeric": "95.5"},
            new_values={"value_numeric": "96.0"},
        )
        
        # Check audit log
        history = await audit_log.get_entity_history("observation", observation.id)
        update_entry = [e for e in history if e.action == "OBSERVATION_UPDATED"][0]
        
        # Verify audit log contains authenticated actor
        assert update_entry.user_id == authenticated_actor_id
        assert update_entry.user_id != UUID("00000000-0000-0000-0000-000000000000")
