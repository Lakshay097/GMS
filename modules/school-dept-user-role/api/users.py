"""
User API endpoints implementing PRS §20 User Management.
"""
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import UserStatus, UserRole
from shared.errors import ValidationError, NotFoundError, AuthorizationError
from shared.middleware.tenancy import require_tenant_context, TenantContext
from shared.middleware.permissions import PermissionChecker, Module, Action
from shared.models import User, UserSchoolGrant

from modules.school_dept_user_role.services.user_service import UserService
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.configuration_engine.constants import ConfigKey


router = APIRouter(prefix="/users", tags=["users"])


# Request/Response Models
class UserCreateRequest(BaseModel):
    """Request model for user creation."""
    clerk_user_id: str = Field(..., min_length=1)
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    school_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    roles: List[UserRole] = Field(..., min_length=1)
    phone: Optional[str] = Field(None, max_length=50)
    employee_id: Optional[str] = Field(None, max_length=50)


class UserUpdateRequest(BaseModel):
    """Request model for user update."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    department_id: Optional[UUID] = None
    phone: Optional[str] = Field(None, max_length=50)
    employee_id: Optional[str] = Field(None, max_length=50)
    language_preference: Optional[str] = Field(None, min_length=2, max_length=10)


class UserResponse(BaseModel):
    """Response model for user."""
    id: UUID
    clerk_user_id: str
    email: str
    full_name: str
    school_id: Optional[UUID]
    department_id: Optional[UUID]
    status: str
    roles: List[str]
    mfa_enabled: bool
    phone: Optional[str]
    employee_id: Optional[str]
    language_preference: str
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Response model for user list."""
    data: List[UserResponse]
    pagination: dict


class RoleAssignmentRequest(BaseModel):
    """Request model for role assignment."""
    role: UserRole


class SchoolGrantRequest(BaseModel):
    """Request model for school access grant."""
    school_id: UUID
    expires_at: Optional[str] = None


class SchoolGrantResponse(BaseModel):
    """Response model for school access grant."""
    id: UUID
    user_id: UUID
    school_id: UUID
    granted_by_user_id: Optional[UUID]
    granted_at: str
    expires_at: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """
    Dependency to get UserService instance.
    """
    from platform_services.audit_log_service import AuditLogService
    
    # This is a simplified implementation - in production, these would be properly injected
    audit_log = AuditLogService(db)
    
    return UserService(db, audit_log)


def get_config_engine(db: AsyncSession = Depends(get_db)) -> ConfigurationEngine:
    """
    Dependency to get ConfigurationEngine instance.
    """
    return ConfigurationEngine(db)


@router.get("/roles")
async def list_roles():
    """
    List all available roles in the system.
    Used by Approval Chains and other UI components to populate role selectors.
    """
    roles = [
        {"id": role.value, "name": role.value, "description": _role_descriptions.get(role.value, "")}
        for role in UserRole
    ]
    return {"roles": roles}


_role_descriptions = {
    "superadmin": "Full platform access — manages all schools, users, departments, and settings",
    "admin": "School-level administration — manages users, departments, and settings for entire school",
    "dept_head": "Department head — manages KPIs, observations, and tasks within their specific department",
    "checker": "KPI verification and quality checks within their school",
    "auditor": "Audit and observation management — raises discrepancies and manages audit flow within school",
    "viewer": "Read-only access — views dashboard and reports within their school",
}


@router.post("", response_model=UserResponse, status_code=http_status.HTTP_201_CREATED)
async def create_user(
    request: UserCreateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service)
):
    """
    Create a new user.
    FR-030: Admin can manage Users only within their own School scope
    SuperAdmin can create users in any school
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can create users"}}
        )
    
    # If Admin, check they're creating in their own school
    if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
        if request.school_id and str(request.school_id) != tenant_context.school_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Admin can only create users in their own school"}}
            )
        # Force school_id to admin's school if not provided
        if not request.school_id:
            request.school_id = UUID(tenant_context.school_id)
    
    try:
        user = await user_service.create_user(
            clerk_user_id=request.clerk_user_id,
            email=request.email,
            full_name=request.full_name,
            school_id=request.school_id,
            department_id=request.department_id,
            roles=request.roles,
            phone=request.phone,
            employee_id=request.employee_id,
            created_by_user_id=UUID(tenant_context.user_id)
        )
        return UserResponse.model_validate(user)
    except NotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.get("", response_model=UserListResponse)
async def list_users(
    school_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
    status_filter: Optional[UserStatus] = None,
    role: Optional[UserRole] = None,
    page: int = 1,
    page_size: int = 50,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service)
):
    """
    List users.
    SuperAdmin: All users
    Admin: Users in their own school only
    """
    try:
        # If not SuperAdmin, restrict to their school
        if UserRole.SUPERADMIN.value not in tenant_context.roles:
            school_id = UUID(tenant_context.school_id)
        
        users, total = await user_service.list_users(
            school_id=school_id,
            department_id=department_id,
            status=status_filter,
            role=role,
            page=page,
            page_size=page_size
        )
        
        return UserListResponse(
            data=[UserResponse.model_validate(user) for user in users],
            pagination={
                "page": page,
                "page_size": page_size,
                "total_count": total,
                "has_next": page * page_size < total
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get user by ID.
    Users can view their own profile.
    SuperAdmin can view any user.
    Admin can view users in their own school.
    """
    try:
        user = await user_service.get_user(user_id)
        
        # Check if user is requesting their own profile
        if str(user.id) == tenant_context.user_id:
            return UserResponse.model_validate(user)
        
        # Check scope access for other users
        from shared.middleware.tenancy import scoped_to_tenant
        if not scoped_to_tenant(tenant_context, str(user.school_id), str(user.department_id)):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "User not found"}}
            )
        
        return UserResponse.model_validate(user)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service),
    config_engine: ConfigurationEngine = Depends(get_config_engine)
):
    """
    Update user details.
    Users can update their own profile (limited fields).
    SuperAdmin can update any user.
    Admin can update users in their own school.
    """
    try:
        # First get the user to check scope
        user = await user_service.get_user(user_id)
        
        # Check if user is updating their own profile
        is_self_update = str(user.id) == tenant_context.user_id
        
        if not is_self_update:
            # Check permission: SuperAdmin or Admin
            if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can update other users"}}
                )
            
            # If Admin, check they're updating in their own school
            if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
                if str(user.school_id) != tenant_context.school_id:
                    raise HTTPException(
                        status_code=http_status.HTTP_403_FORBIDDEN,
                        detail={"error": {"code": "FORBIDDEN", "message": "Admin can only update users in their own school"}}
                    )
        
        # Validate language_preference against ConfigurationEngine.LOCALES (FR-163)
        if request.language_preference is not None:
            locales = await config_engine.get(ConfigKey.LOCALES)
            if request.language_preference not in locales:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid language preference. Must be one of: {locales}", "field": "language_preference"}}
                )
        
        updated_user = await user_service.update_user(
            user_id=user_id,
            full_name=request.full_name,
            department_id=request.department_id,
            phone=request.phone,
            employee_id=request.employee_id,
            language_preference=request.language_preference,
            updated_by_user_id=UUID(tenant_context.user_id)
        )
        return UserResponse.model_validate(updated_user)
    except HTTPException:
        raise
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


class ArchiveConfirmRequest(BaseModel):
    confirm: bool = Field(False, description="Must be true to confirm destructive action")


@router.post("/{user_id}/archive", response_model=UserResponse)
async def archive_user(
    user_id: UUID,
    body: ArchiveConfirmRequest = ArchiveConfirmRequest(),
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service)
):
    """
    Archive a user (soft delete).
    FR-021: Never permit hard deletion of a User record
    FR-022: Disable login immediately upon archival
    SuperAdmin can archive any user.
    Admin can archive users in their own school.
    
    SECURITY FIX (Route Hygiene): Requires explicit confirmation for destructive action.
    """
    # Require explicit confirmation (Route Hygiene security fix)
    if not body.confirm:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "CONFIRMATION_REQUIRED", "message": "Destructive action requires confirmation. Set confirm=true to proceed."}}
        )
    
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can archive users"}}
        )
    
    try:
        # First get the user to check scope
        user = await user_service.get_user(user_id)
        
        # If Admin, check they're archiving in their own school
        if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
            if str(user.school_id) != tenant_context.school_id:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "FORBIDDEN", "message": "Admin can only archive users in their own school"}}
                )
        
        archived_user = await user_service.archive_user(
            user_id=user_id,
            archived_by_user_id=UUID(tenant_context.user_id)
        )
        return UserResponse.model_validate(archived_user)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.post("/{user_id}/roles", response_model=UserResponse)
async def assign_role(
    user_id: UUID,
    request: RoleAssignmentRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service)
):
    """
    Grant an additional role to a user.
    FR-023: Support assignment of multiple concurrent Roles
    SuperAdmin can assign roles to any user.
    Admin can assign roles to users in their own school.
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can assign roles"}}
        )
    
    try:
        # First get the user to check scope
        user = await user_service.get_user(user_id)
        
        # If Admin, check they're assigning in their own school
        if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
            if str(user.school_id) != tenant_context.school_id:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "FORBIDDEN", "message": "Admin can only assign roles to users in their own school"}}
                )
        
        updated_user = await user_service.assign_role(
            user_id=user_id,
            role=request.role,
            assigned_by_user_id=UUID(tenant_context.user_id)
        )
        return UserResponse.model_validate(updated_user)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.delete("/{user_id}/roles/{role_code}", response_model=UserResponse)
async def revoke_role(
    user_id: UUID,
    role_code: str,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service)
):
    """
    Revoke a role from a user.
    Last role cannot be revoked.
    SuperAdmin can revoke roles from any user.
    Admin can revoke roles from users in their own school.
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can revoke roles"}}
        )
    
    try:
        # First get the user to check scope
        user = await user_service.get_user(user_id)
        
        # If Admin, check they're revoking in their own school
        if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
            if str(user.school_id) != tenant_context.school_id:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "FORBIDDEN", "message": "Admin can only revoke roles from users in their own school"}}
                )
        
        # Convert role_code string to UserRole enum
        try:
            role = UserRole(role_code)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "VALIDATION_ERROR", "message": f"Invalid role: {role_code}", "field": "role_code"}}
            )
        
        updated_user = await user_service.revoke_role(
            user_id=user_id,
            role=role,
            revoked_by_user_id=UUID(tenant_context.user_id)
        )
        return UserResponse.model_validate(updated_user)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.post("/{user_id}/school-grants", response_model=SchoolGrantResponse)
async def grant_school_access(
    user_id: UUID,
    request: SchoolGrantRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service)
):
    """
    Grant a Viewer multi-school access via user_school_grants.
    FR-020: Allow Viewer to be granted access to multiple Schools
    Only SuperAdmin can grant school access.
    """
    # Only SuperAdmin can grant school access
    if UserRole.SUPERADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin can grant school access"}}
        )
    
    try:
        # Parse expires_at if provided
        expires_at = None
        if request.expires_at:
            from datetime import datetime
            expires_at = datetime.fromisoformat(request.expires_at)
        
        grant = await user_service.grant_school_access(
            user_id=user_id,
            school_id=request.school_id,
            granted_by_user_id=UUID(tenant_context.user_id),
            expires_at=expires_at
        )
        return SchoolGrantResponse.model_validate(grant)
    except NotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )