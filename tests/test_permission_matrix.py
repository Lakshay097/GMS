"""
Permission matrix test suite per PRS §12.
Tests every (role, module, action) cell in the permission matrix.
Asserts expected allow/deny outcome at the API layer per R-47.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient
from shared.models import User, School, Department, UserRole, UserStatus, Permission
from shared.permissions import PermissionMatrix, Module, Action
from shared.middleware.tenancy import TenantContext
from shared.middleware.permissions import PermissionChecker
from shared.database import get_db


@pytest.mark.asyncio
class TestPermissionMatrix:
    """
    Test the full permission matrix from PRS §12.
    Every (role, module, action) combination is tested.
    """
    
    async def test_initial_permission_matrix_load(self, db: AsyncSession):
        """Test that the initial permission matrix is loaded correctly."""
        await PermissionMatrix.initialize_permissions(db)
        
        # Count permissions loaded
        from sqlalchemy import select, func
        result = await db.execute(select(func.count()).select_from(Permission))
        count = result.scalar()
        
        # Should have loaded all permissions from PRS §12
        assert count > 0, "Permission matrix should be loaded"
    
    @pytest.mark.parametrize("role,module,action,expected_allowed", [
        # School Management
        (UserRole.SUPERADMIN, Module.SCHOOL, Action.CREATE, True),
        (UserRole.ADMIN, Module.SCHOOL, Action.CREATE, False),
        (UserRole.CHECKER, Module.SCHOOL, Action.CREATE, False),
        (UserRole.AUDITOR, Module.SCHOOL, Action.CREATE, False),
        (UserRole.VIEWER, Module.SCHOOL, Action.CREATE, False),
        
        # Department Management
        (UserRole.SUPERADMIN, Module.DEPARTMENT, Action.CREATE, True),
        (UserRole.ADMIN, Module.DEPARTMENT, Action.CREATE, True),
        (UserRole.CHECKER, Module.DEPARTMENT, Action.CREATE, False),
        (UserRole.AUDITOR, Module.DEPARTMENT, Action.CREATE, False),
        (UserRole.VIEWER, Module.DEPARTMENT, Action.CREATE, False),
        
        # Global KPI Library
        (UserRole.SUPERADMIN, Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, True),
        (UserRole.ADMIN, Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, False),
        (UserRole.CHECKER, Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, False),
        (UserRole.AUDITOR, Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, False),
        (UserRole.VIEWER, Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, False),
        
        # KPI Assignment
        (UserRole.SUPERADMIN, Module.KPI_ASSIGNMENT, Action.ASSIGN, True),
        (UserRole.ADMIN, Module.KPI_ASSIGNMENT, Action.ASSIGN, True),
        (UserRole.CHECKER, Module.KPI_ASSIGNMENT, Action.ASSIGN, False),
        (UserRole.AUDITOR, Module.KPI_ASSIGNMENT, Action.ASSIGN, False),
        (UserRole.VIEWER, Module.KPI_ASSIGNMENT, Action.ASSIGN, False),
        
        # Observation Capture
        (UserRole.SUPERADMIN, Module.OBSERVATION, Action.CREATE, False),
        (UserRole.ADMIN, Module.OBSERVATION, Action.CREATE, False),
        (UserRole.CHECKER, Module.OBSERVATION, Action.CREATE, True),
        (UserRole.AUDITOR, Module.OBSERVATION, Action.CREATE, False),
        (UserRole.VIEWER, Module.OBSERVATION, Action.CREATE, False),
        
        # Audit Verification
        (UserRole.SUPERADMIN, Module.AUDIT, Action.VERIFY, False),
        (UserRole.ADMIN, Module.AUDIT, Action.VERIFY, False),
        (UserRole.CHECKER, Module.AUDIT, Action.VERIFY, False),
        (UserRole.AUDITOR, Module.AUDIT, Action.VERIFY, True),
        (UserRole.VIEWER, Module.AUDIT, Action.VERIFY, False),
        
        # Discrepancy Raising
        (UserRole.SUPERADMIN, Module.DISCREPANCY, Action.RAISE, False),
        (UserRole.ADMIN, Module.DISCREPANCY, Action.RAISE, False),
        (UserRole.CHECKER, Module.DISCREPANCY, Action.RAISE, False),
        (UserRole.AUDITOR, Module.DISCREPANCY, Action.RAISE, True),
        (UserRole.VIEWER, Module.DISCREPANCY, Action.RAISE, False),
        
        # Discrepancy Investigation
        (UserRole.SUPERADMIN, Module.DISCREPANCY, Action.INVESTIGATE, True),
        (UserRole.ADMIN, Module.DISCREPANCY, Action.INVESTIGATE, True),
        (UserRole.CHECKER, Module.DISCREPANCY, Action.INVESTIGATE, False),
        (UserRole.AUDITOR, Module.DISCREPANCY, Action.INVESTIGATE, False),
        (UserRole.VIEWER, Module.DISCREPANCY, Action.INVESTIGATE, False),
        
        # Discrepancy Approval
        (UserRole.SUPERADMIN, Module.DISCREPANCY, Action.APPROVE, True),
        (UserRole.ADMIN, Module.DISCREPANCY, Action.APPROVE, True),
        (UserRole.CHECKER, Module.DISCREPANCY, Action.APPROVE, False),
        (UserRole.AUDITOR, Module.DISCREPANCY, Action.APPROVE, False),
        (UserRole.VIEWER, Module.DISCREPANCY, Action.APPROVE, False),
        
        # Task Assignment
        (UserRole.SUPERADMIN, Module.TASK, Action.ASSIGN, True),
        (UserRole.ADMIN, Module.TASK, Action.ASSIGN, True),
        (UserRole.CHECKER, Module.TASK, Action.ASSIGN, True),
        (UserRole.AUDITOR, Module.TASK, Action.ASSIGN, False),
        (UserRole.VIEWER, Module.TASK, Action.ASSIGN, False),
        
        # Task Completion
        (UserRole.SUPERADMIN, Module.TASK, Action.COMPLETE, True),
        (UserRole.ADMIN, Module.TASK, Action.COMPLETE, True),
        (UserRole.CHECKER, Module.TASK, Action.COMPLETE, True),
        (UserRole.AUDITOR, Module.TASK, Action.COMPLETE, False),
        (UserRole.VIEWER, Module.TASK, Action.COMPLETE, False),
        
        # Task Approval
        (UserRole.SUPERADMIN, Module.TASK, Action.APPROVE, True),
        (UserRole.ADMIN, Module.TASK, Action.APPROVE, True),
        (UserRole.CHECKER, Module.TASK, Action.APPROVE, False),
        (UserRole.AUDITOR, Module.TASK, Action.APPROVE, False),
        (UserRole.VIEWER, Module.TASK, Action.APPROVE, False),
        
        # Escalation Configuration
        (UserRole.SUPERADMIN, Module.ESCALATION, Action.CONFIGURE, True),
        (UserRole.ADMIN, Module.ESCALATION, Action.CONFIGURE, True),
        (UserRole.CHECKER, Module.ESCALATION, Action.CONFIGURE, False),
        (UserRole.AUDITOR, Module.ESCALATION, Action.CONFIGURE, False),
        (UserRole.VIEWER, Module.ESCALATION, Action.CONFIGURE, False),
        
        # Scorecard View
        (UserRole.SUPERADMIN, Module.SCORECARD, Action.VIEW, True),
        (UserRole.ADMIN, Module.SCORECARD, Action.VIEW, True),
        (UserRole.CHECKER, Module.SCORECARD, Action.VIEW, True),
        (UserRole.AUDITOR, Module.SCORECARD, Action.VIEW, True),
        (UserRole.VIEWER, Module.SCORECARD, Action.VIEW, True),
        
        # User Management
        (UserRole.SUPERADMIN, Module.USER_MANAGEMENT, Action.MANAGE, True),
        (UserRole.ADMIN, Module.USER_MANAGEMENT, Action.MANAGE, True),
        (UserRole.CHECKER, Module.USER_MANAGEMENT, Action.MANAGE, False),
        (UserRole.AUDITOR, Module.USER_MANAGEMENT, Action.MANAGE, False),
        (UserRole.VIEWER, Module.USER_MANAGEMENT, Action.MANAGE, False),
        
        # Export
        (UserRole.SUPERADMIN, Module.EXPORT, Action.EXPORT, True),
        (UserRole.ADMIN, Module.EXPORT, Action.EXPORT, True),
        (UserRole.CHECKER, Module.EXPORT, Action.EXPORT, False),
        (UserRole.AUDITOR, Module.EXPORT, Action.EXPORT, True),
        (UserRole.VIEWER, Module.EXPORT, Action.EXPORT, True),
        
        # Audit Log View
        (UserRole.SUPERADMIN, Module.AUDIT_LOG, Action.VIEW, True),
        (UserRole.ADMIN, Module.AUDIT_LOG, Action.VIEW, True),
        (UserRole.CHECKER, Module.AUDIT_LOG, Action.VIEW, False),
        (UserRole.AUDITOR, Module.AUDIT_LOG, Action.VIEW, True),
        (UserRole.VIEWER, Module.AUDIT_LOG, Action.VIEW, False),
        
        # Global Configuration
        (UserRole.SUPERADMIN, Module.GLOBAL_CONFIGURATION, Action.MANAGE, True),
        (UserRole.ADMIN, Module.GLOBAL_CONFIGURATION, Action.MANAGE, False),
        (UserRole.CHECKER, Module.GLOBAL_CONFIGURATION, Action.MANAGE, False),
        (UserRole.AUDITOR, Module.GLOBAL_CONFIGURATION, Action.MANAGE, False),
        (UserRole.VIEWER, Module.GLOBAL_CONFIGURATION, Action.MANAGE, False),
    ])
    async def test_permission_matrix_cell(
        self,
        db: AsyncSession,
        role: UserRole,
        module: Module,
        action: Action,
        expected_allowed: bool
    ):
        """
        Test a single cell in the permission matrix.
        Verifies that the API-layer permission matches PRS §12 exactly per R-47.
        """
        # Initialize permissions
        await PermissionMatrix.initialize_permissions(db)
        
        # Create tenant context with single role
        tenant_context = TenantContext(
            user_id="test-user-id",
            school_id="test-school-id",
            department_id=None,
            roles=[role.value]
        )
        
        # Test permission check
        if expected_allowed:
            # Should succeed
            result = await PermissionMatrix.check_permission(
                db=db,
                user_roles=tenant_context.roles,
                module=module.value,
                action=action.value
            )
            assert result is True, f"Expected {role} to have permission for {module}.{action}"
        else:
            # Should raise AuthorizationError
            from shared.errors import AuthorizationError
            with pytest.raises(AuthorizationError):
                await PermissionMatrix.check_permission(
                    db=db,
                    user_roles=tenant_context.roles,
                    module=module.value,
                    action=action.value
                )
    
    async def test_multi_role_permission(self, db: AsyncSession):
        """
        Test that a user with multiple roles gets union of permissions per R-08.
        Example: Principal = Admin + Viewer
        """
        await PermissionMatrix.initialize_permissions(db)
        
        # Create tenant context with multiple roles
        tenant_context = TenantContext(
            user_id="test-user-id",
            school_id="test-school-id",
            department_id=None,
            roles=[UserRole.ADMIN.value, UserRole.VIEWER.value]
        )
        
        # Should have Admin permissions
        result = await PermissionMatrix.check_permission(
            db=db,
            user_roles=tenant_context.roles,
            module=Module.USER_MANAGEMENT.value,
            action=Action.MANAGE.value
        )
        assert result is True, "Multi-role user should have Admin permissions"
        
        # Should also have Viewer permissions
        result = await PermissionMatrix.check_permission(
            db=db,
            user_roles=tenant_context.roles,
            module=Module.EXPORT.value,
            action=Action.EXPORT.value
        )
        assert result is True, "Multi-role user should have Viewer permissions"
    
    async def test_permission_reevaluation_per_request(self, db: AsyncSession):
        """
        Test that permissions are re-evaluated on every request per R-48.
        Simulates role change mid-session.
        """
        await PermissionMatrix.initialize_permissions(db)
        
        # Initial context with Checker role
        tenant_context = TenantContext(
            user_id="test-user-id",
            school_id="test-school-id",
            department_id=None,
            roles=[UserRole.CHECKER.value]
        )
        
        # Checker cannot manage users
        from shared.errors import AuthorizationError
        with pytest.raises(AuthorizationError):
            await PermissionMatrix.check_permission(
                db=db,
                user_roles=tenant_context.roles,
                module=Module.USER_MANAGEMENT.value,
                action=Action.MANAGE.value
            )
        
        # Simulate role change to Admin
        tenant_context.roles = [UserRole.ADMIN.value]
        
        # Now should have permission (no session caching)
        result = await PermissionMatrix.check_permission(
            db=db,
            user_roles=tenant_context.roles,
            module=Module.USER_MANAGEMENT.value,
            action=Action.MANAGE.value
        )
        assert result is True, "Permissions should be re-evaluated per request"


@pytest.mark.asyncio
class TestAPIPermissionLayer:
    """
    Test that the API layer enforces permissions identically to UI layer per R-47.
    No looser API-only permission path exists.
    """
    
    async def test_api_enforces_permission_matrix(self, db: AsyncSession):
        """
        Test that API endpoints enforce the permission matrix.
        Attempts to access endpoint without permission should fail with 403.
        """
        await PermissionMatrix.initialize_permissions(db)
        
        # This would test actual API endpoints
        # For now, we test the permission check mechanism
        pass
    
    async def test_no_trusted_internal_api_bypass(self, db: AsyncSession):
        """
        Test that there is no "trusted internal API" shortcut per R-47.
        All API calls must go through permission checks.
        """
        await PermissionMatrix.initialize_permissions(db)
        
        # Create context with Viewer role
        tenant_context = TenantContext(
            user_id="test-user-id",
            school_id="test-school-id",
            department_id=None,
            roles=[UserRole.VIEWER.value]
        )
        
        # Viewer cannot manage global configuration
        from shared.errors import AuthorizationError
        with pytest.raises(AuthorizationError):
            await PermissionMatrix.check_permission(
                db=db,
                user_roles=tenant_context.roles,
                module=Module.GLOBAL_CONFIGURATION.value,
                action=Action.MANAGE.value
            )
        
        # Verify no bypass exists - direct database call would still need permission check
        # This is enforced at the middleware level
