"""
Tenancy filter middleware per Architecture §6 and R-02.
Enforces row-level tenant isolation using school_id/department_id.
Scope isolation is a mandatory query-layer filter applied BEFORE and INDEPENDENT of role-permission checks.
"""
import uuid
from typing import Optional, List
from fastapi import Request, HTTPException, status
from sqlalchemy import false
from sqlalchemy.sql import Select
from shared.auth import decode_access_token
from shared.errors import AuthorizationError
from shared.models import UserSchoolGrant


class TenantContext:
    """
    Tenant context extracted from auth token.
    Contains user's scope for mandatory query-layer filtering per R-02.
    """
    def __init__(
        self,
        user_id: str,
        school_id: Optional[str],
        department_id: Optional[str],
        roles: List[str],
        accessible_school_ids: Optional[List[str]] = None
    ):
        self.user_id = user_id
        self.school_id = school_id  # Primary school (None for SuperAdmin)
        self.department_id = department_id
        self.roles = roles
        self.accessible_school_ids = accessible_school_ids or []  # For Viewer multi-school access


def extract_tenant_context(request: Request) -> TenantContext:
    """
    Extract tenant context from the request's auth token.
    
    Args:
        request: FastAPI request object
        
    Returns:
        TenantContext with user's tenant information
        
    Raises:
        AuthenticationError if token is invalid or missing
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTHENTICATION_ERROR", "message": "Missing or invalid authorization header"}}
        )
    
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTHENTICATION_ERROR", "message": "Invalid or expired token"}}
        )
    
    return TenantContext(
        user_id=payload.get("sub"),
        school_id=payload.get("school_id"),
        department_id=payload.get("department_id"),
        roles=payload.get("roles", []),
        accessible_school_ids=payload.get("accessible_school_ids", [])
    )


def require_tenant_context(request: Request) -> TenantContext:
    """
    Dependency to require tenant context in a route.
    
    Args:
        request: FastAPI request object
        
    Returns:
        TenantContext
    """
    return extract_tenant_context(request)


def apply_tenant_filter(query: Select, tenant_context: TenantContext) -> Select:
    """
    Apply mandatory tenant filter to a database query per R-02.
    This is applied BEFORE and INDEPENDENT of role-permission checks.
    
    SuperAdmin: No school filter (all schools accessible)
    Viewer: Filter by accessible_school_ids from user_school_grants
    Other roles: Filter by school_id (and department_id if set)
    
    Args:
        query: SQLAlchemy query object
        tenant_context: TenantContext with filtering criteria
        
    Returns:
        Filtered query with mandatory scope isolation
    """
    # Normalize roles to lowercase for comparison
    normalized_roles = [role.lower() if role else role for role in tenant_context.roles]
    
    # SuperAdmin has access to all schools (no filter)
    if "superadmin" in normalized_roles:
        return query
    
    # Viewer with multi-school access via user_school_grants
    if "viewer" in normalized_roles:
        if tenant_context.accessible_school_ids:
            # Convert string UUIDs to UUID objects for comparison
            school_uuids = [
                uuid.UUID(s) if isinstance(s, str) else s
                for s in tenant_context.accessible_school_ids
            ]
            return query.where(
                query.selected_columns.school_id.in_(school_uuids)
            )
        else:
            # Viewer without grants sees no data
            return query.where(false())
    
    # All other roles: filter by primary school
    if tenant_context.school_id:
        # Convert string UUID to UUID object for comparison
        school_uuid = (
            uuid.UUID(tenant_context.school_id)
            if isinstance(tenant_context.school_id, str)
            else tenant_context.school_id
        )
        query = query.where(query.selected_columns.school_id == school_uuid)
    else:
        # Non-SuperAdmin without school_id is invalid
        raise AuthorizationError("User must have a school_id assigned")
    
    # If user has department_id, filter by it as well
    # SuperAdmin/Admin bypass this via role checks, not here
    if tenant_context.department_id:
        # Convert string UUID to UUID object for comparison
        dept_uuid = (
            uuid.UUID(tenant_context.department_id)
            if isinstance(tenant_context.department_id, str)
            else tenant_context.department_id
        )
        query = query.where(query.selected_columns.department_id == dept_uuid)
    
    return query


def scoped_to_tenant(tenant_context: TenantContext, resource_school_id: str, resource_department_id: Optional[str] = None) -> bool:
    """
    Check if a resource is within the user's tenant scope.
    This is a pre-check before permission evaluation per R-02.
    
    Args:
        tenant_context: User's tenant context
        resource_school_id: School ID of the resource
        resource_department_id: Optional department ID of the resource
        
    Returns:
        True if resource is within scope, False otherwise
    """
    # Normalize roles to lowercase for comparison
    normalized_roles = [role.lower() if role else role for role in tenant_context.roles]
    
    # SuperAdmin has access to all schools
    if "superadmin" in normalized_roles:
        return True
    
    # Viewer with multi-school access
    if "viewer" in normalized_roles and tenant_context.accessible_school_ids:
        return resource_school_id in tenant_context.accessible_school_ids
    
    # All other roles: must match primary school
    if tenant_context.school_id != resource_school_id:
        return False
    
    # If user has department scope, resource must be in same department
    # Cross-department access is handled by role permissions, not scope filter
    if tenant_context.department_id and resource_department_id:
        if tenant_context.department_id != resource_department_id:
            # Check if user has cross-department access via roles
            cross_dept_roles = ["superadmin", "admin"]
            if not any(role in cross_dept_roles for role in normalized_roles):
                return False
    
    return True
