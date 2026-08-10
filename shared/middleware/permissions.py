"""
Permission check middleware per PRS §12 and Architecture §6.
Enforces role-based and scope-based authorization with permission matrix.
Every request re-evaluates permissions at execution time per R-48.
"""
from typing import Optional, List, Set
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from shared.errors import AuthorizationError
from shared.middleware.tenancy import TenantContext
from shared.permissions import PermissionMatrix, Module, Action
from shared.database import get_db


class PermissionChecker:
    """
    Permission checker for role and scope validation.
    Uses the canonical permission matrix from PRS §12.
    """
    
    @staticmethod
    async def require_permission(
        module: Module,
        action: Action,
        tenant_context: TenantContext,
        db: AsyncSession,
        scope_constraint: Optional[str] = None
    ) -> bool:
        """
        Check if user has permission for a given module/action.
        Re-evaluates on every request per R-48.
        
        Args:
            module: Module name
            action: Action name
            tenant_context: User's tenant context with roles
            db: Database session
            scope_constraint: Optional scope constraint to verify
            
        Returns:
            True if allowed
            
        Raises:
            AuthorizationError if permission denied
        """
        return await PermissionMatrix.check_permission(
            db=db,
            user_roles=tenant_context.roles,
            module=module.value,
            action=action.value,
            scope_constraint=scope_constraint
        )
    
    @staticmethod
    def require_roles(required_roles: Set[str]):
        """
        Decorator to require specific roles for a route.
        Legacy compatibility - prefer require_permission where possible.
        
        Args:
            required_roles: Set of roles that grant permission
            
        Returns:
            Decorator function
        """
        def decorator(func):
            async def wrapper(*args, tenant_context: TenantContext, **kwargs):
                if not any(role in required_roles for role in tenant_context.roles):
                    raise AuthorizationError(
                        f"Requires one of roles: {', '.join(required_roles)}"
                    )
                return await func(*args, tenant_context=tenant_context, **kwargs)
            return wrapper
        return decorator


# Common role sets per PRS §12
ADMIN_ROLES = {"Admin", "SuperAdmin"}
MANAGEMENT_ROLES = {"Admin", "SuperAdmin"}
ALL_ROLES = {"SuperAdmin", "Admin", "Checker", "Auditor", "Viewer"}


def check_self_audit_block(
    tenant_context: TenantContext,
    target_user_id: Optional[str]
) -> bool:
    """
    Enforce self-audit block per BR-16: users cannot audit their own observations.
    
    Args:
        tenant_context: User's tenant context
        target_user_id: ID of the user being audited
        
    Returns:
        True if allowed, False if blocked
        
    Raises:
        AuthorizationError if self-audit is attempted
    """
    if tenant_context.user_id == target_user_id:
        raise AuthorizationError("Users cannot audit their own observations")
    return True


def check_investigation_approval_separation(
    tenant_context: TenantContext,
    investigator_id: str,
    approver_id: str
) -> bool:
    """
    Enforce investigation/approval separation per BR-17.
    The same person cannot both investigate and approve a discrepancy.
    
    Args:
        tenant_context: User's tenant context
        investigator_id: ID of the investigator
        approver_id: ID of the approver
        
    Returns:
        True if allowed, False if blocked
        
    Raises:
        AuthorizationError if separation is violated
    """
    if investigator_id == approver_id:
        raise AuthorizationError("The same person cannot both investigate and approve a discrepancy")
    return True
