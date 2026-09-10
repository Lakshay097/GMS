"""
User API endpoints implementing PRS §20 User Management.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from shared.database import get_db
from shared.models import UserStatus, UserRole
from shared.errors import ValidationError, NotFoundError, AuthorizationError
from shared.permissions import can_manage_role
from shared.middleware.tenancy import require_tenant_context, TenantContext
from shared.middleware.permissions import PermissionChecker, Module, Action
from shared.models import User, UserSchoolGrant, AuthSession, PasswordResetToken
from shared.auth import (
    hash_password,
    validate_password_policy,
    generate_password_reset_token,
    _session_cache_invalidate,
)
from shared.datetime_utils import utc_now

from modules.school_dept_user_role.services.user_service import UserService
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.configuration_engine.constants import ConfigKey


router = APIRouter(prefix="/users", tags=["users"])


# Request/Response Models
class UserCreateRequest(BaseModel):
    """Request model for user creation."""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    school_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    roles: List[UserRole] = Field(..., min_length=1)
    phone: Optional[str] = Field(None, max_length=50)
    employee_id: Optional[str] = Field(None, max_length=50)
    manager_id: Optional[UUID] = None
    designation: Optional[str] = Field(None, max_length=120)
    location: Optional[str] = Field(None, max_length=120)
    password: Optional[str] = Field(None, max_length=1024, description="Initial password. If omitted, the user sets it via forgot-password flow.")


class UserUpdateRequest(BaseModel):
    """Request model for user update."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    department_id: Optional[UUID] = None
    phone: Optional[str] = Field(None, max_length=50)
    employee_id: Optional[str] = Field(None, max_length=50)
    manager_id: Optional[UUID] = None
    designation: Optional[str] = Field(None, max_length=120)
    location: Optional[str] = Field(None, max_length=120)
    language_preference: Optional[str] = Field(None, min_length=2, max_length=10)


class UserResponse(BaseModel):
    """Response model for user."""
    id: UUID
    email: str
    full_name: str
    school_id: Optional[UUID]
    school_name: Optional[str] = None        # enriched by list_users JOIN
    department_id: Optional[UUID]
    department_name: Optional[str] = None    # enriched by list_users JOIN
    status: str
    roles: List[str]
    mfa_enabled: bool
    phone: Optional[str]
    employee_id: Optional[str]
    manager_id: Optional[UUID] = None
    designation: Optional[str] = None
    location: Optional[str] = None
    last_login_at: Optional[datetime] = None
    email_verified: bool = False
    language_preference: str
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]

    model_config = {"from_attributes": True}


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


class SetPasswordRequest(BaseModel):
    """Request model for admin password set/force-reset.

    password omitted → generate a one-time reset token instead (returned to
    the authenticated admin, who hands it to the user over any channel).
    """
    password: Optional[str] = Field(None, max_length=1024)


class SetPasswordResponse(BaseModel):
    """Response model for admin password set/force-reset."""
    success: bool
    mode: str  # "password" | "reset_token"
    message: str
    reset_token: Optional[str] = None


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

    # Role-hierarchy guard (spec §11): no privilege escalation on creation.
    for requested_role in request.roles:
        if not can_manage_role(tenant_context.roles, requested_role.value):
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": f"You may not assign the role '{requested_role.value}'"}}
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
            email=request.email,
            full_name=request.full_name,
            school_id=request.school_id,
            department_id=request.department_id,
            roles=request.roles,
            phone=request.phone,
            employee_id=request.employee_id,
            manager_id=request.manager_id,
            designation=request.designation,
            location=request.location,
            created_by_user_id=UUID(tenant_context.user_id)
        )

        # Self-managed auth: optionally set the initial password at creation time.
        # Admins typically leave it blank and share a one-time reset instead.
        if request.password:
            from shared.auth import hash_password, validate_password_policy
            policy_error = validate_password_policy(request.password)
            if policy_error:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "WEAK_PASSWORD", "message": policy_error}},
                )
            user.password_hash = hash_password(request.password)
            user.updated_at = datetime.utcnow()
            await user_service.db.commit()

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
        # If not SuperAdmin, restrict to their school. A non-superadmin with no
        # school (school_id NULL) gets an empty list — never a cross-school view.
        if UserRole.SUPERADMIN.value not in tenant_context.roles:
            if not tenant_context.school_id:
                return UserListResponse(
                    data=[],
                    pagination={"page": page, "page_size": page_size, "total_count": 0, "has_next": False},
                )
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
            manager_id=request.manager_id,
            designation=request.designation,
            location=request.location,
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


async def _revoke_user_sessions(db: AsyncSession, user_id: UUID) -> int:
    """Delete all auth_sessions for a user and evict the in-process cache."""
    result = await db.execute(select(AuthSession).where(AuthSession.user_id == user_id))
    rows = result.scalars().all()
    for row in rows:
        await db.delete(row)
        _session_cache_invalidate(row.token_hash)
    return len(rows)


@router.post("/{user_id}/set-password", response_model=SetPasswordResponse)
async def admin_set_password(
    user_id: UUID,
    body: SetPasswordRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service),
):
    """
    Admin sets or force-resets a user's password (self-managed auth onboarding).

    Two modes:
      - body.password given: hash (Argon2id) and store it directly. Use when the
        admin hands the password to the user over a trusted channel.
      - body.password omitted: generate a single-use reset token (30-minute
        expiry) and return it HERE in the response — the admin relays it to
        the user, who completes POST /auth/reset-password. This works with NO
        email provider configured, so an admin-created user can always log in.

    Both modes revoke all of the user's existing sessions. Authorization:
    SuperAdmin anywhere; Admin only within their own school (same rules as
    role assignment). Password policy is enforced in both modes.
    """
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can set passwords"}}
        )

    try:
        target = await user_service.get_user(user_id)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}}
        )

    # Scope check: Admins may only manage users in their own school
    if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
        if str(target.school_id) != tenant_context.school_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Admin can only set passwords for users in their own school"}}
            )

    if target.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "USER_ARCHIVED", "message": "Cannot set a password for an archived user"}}
        )

    if body.password:
        policy_error = validate_password_policy(body.password)
        if policy_error:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "WEAK_PASSWORD", "message": policy_error}}
            )
        target.password_hash = hash_password(body.password)
        mode = "password"
        message = "Password set. Share it with the user over a trusted channel."
        reset_token = None
    else:
        raw_token, token_hash, expires_at = generate_password_reset_token()
        db_session = user_service.db
        db_session.add(PasswordResetToken(
            user_id=target.id,
            token_hash=token_hash,
            created_at=datetime.now(timezone.utc),  # password_reset_tokens.created_at is TIMESTAMP WITH TIME ZONE
            expires_at=expires_at,
        ))
        mode = "reset_token"
        message = "One-time reset token generated. Give it to the user; they set their own password at /auth/reset-password (valid 30 minutes)."
        reset_token = raw_token

    target.failed_login_count = 0
    target.locked_until = None
    target.updated_at = utc_now()

    # Force-reset semantics: any existing session is stale after this change
    await _revoke_user_sessions(user_service.db, target.id)
    await user_service.db.commit()

    # If the user is PENDING and an email provider is configured, send an
    # activation email automatically so they don't need the token hand-delivered.
    # The reset_token is still returned in the response as a fallback channel.
    if mode == "reset_token" and os.getenv("EMAIL_PROVIDER_API_KEY"):
        try:
            app_url = (os.getenv("APP_URL") or "http://localhost:5173").rstrip("/")
            activate_link = f"{app_url}/auth/reset-password?token={raw_token}"
            from platform_services.notification_service.service import NotificationPayload, NotificationService
            from shared.platform_models import NotificationCategory, NotificationChannel
            was_pending = target.status == UserStatus.PENDING
            email_title = "Activate your SchoolOps account" if was_pending else "Your SchoolOps password has been reset by an administrator"
            email_body = (
                f"<p>Hi {target.full_name or 'there'},</p>"
                + (
                    "<p>Your SchoolOps account has been created. Click the link below to set your password and activate your account.</p>"
                    if was_pending else
                    "<p>An administrator has issued a password reset for your SchoolOps account.</p>"
                )
                + f"<p><a href=\"{activate_link}\">Set my password</a></p>"
                + f"<p>Or copy this link:<br>{activate_link}</p>"
                + "<p>This link expires in 30 minutes and can only be used once.</p>"
            )
            await NotificationService(user_service.db).dispatch(NotificationPayload(
                user_id=target.id,
                category=NotificationCategory.INFORMATIONAL.value,
                title=email_title,
                body=email_body,
                channel=NotificationChannel.EMAIL,
                entity_type="user",
                entity_id=target.id,
            ))
        except Exception as exc:
            import logging as _logging
            _logging.getLogger(__name__).warning("Activation email dispatch failed for user %s: %s", target.id, exc)

    return SetPasswordResponse(success=True, mode=mode, message=message, reset_token=reset_token)


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

    # Role-hierarchy guard (spec §11): a DEPARTMENT_HEAD must not be able to
    # change a user to SUPERADMIN or ADMIN; nobody can grant a role at or
    # above their own level.
    if not can_manage_role(tenant_context.roles, request.role.value):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": f"You may not assign the role '{request.role.value}'"}}
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

    # Role-hierarchy guard (spec §11): prevent privilege escalation.
    if not can_manage_role(tenant_context.roles, role_code):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": f"You may not revoke the role '{role_code}'"}}
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


class StatusChangeRequest(BaseModel):
    confirm: bool = Field(True, description="Confirm the status change")


def _can_manage_target(tenant_context: TenantContext, target: User) -> None:
    """SuperAdmin: anyone. Admin: users in own school only."""
    roles = [r.lower() for r in tenant_context.roles]
    if "superadmin" in roles:
        return
    if "admin" in roles:
        if target.school_id and tenant_context.school_id and str(target.school_id) != tenant_context.school_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "You can only manage users in your own school"}},
            )
        return
    raise HTTPException(
        status_code=http_status.HTTP_403_FORBIDDEN,
        detail={"error": {"code": "FORBIDDEN", "message": "You do not have permission to perform this action."}},
    )


@router.post("/{user_id}/disable", response_model=UserResponse)
async def disable_user(
    user_id: UUID,
    body: StatusChangeRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service),
):
    """Disable a user (status=inactive). Login is blocked; history is retained."""
    if not body.confirm:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                            detail={"error": {"code": "CONFIRMATION_REQUIRED", "message": "Set confirm=true"}})
    user = await user_service.get_user(user_id)
    _can_manage_target(tenant_context, user)
    if str(user.id) == tenant_context.user_id:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                            detail={"error": {"code": "VALIDATION_ERROR", "message": "You cannot disable your own account"}})
    user.status = UserStatus.INACTIVE
    user.updated_at = utc_now()
    # Security: a disabled user's sessions die immediately
    await _revoke_user_sessions(user_service.db, user.id)
    await user_service.db.commit()

    try:
        from platform_services.audit_log_service import AuditLogService
        await AuditLogService(user_service.db).append(
            "user_disabled", "user", user.id,
            actor_id=UUID(tenant_context.user_id), school_id=user.school_id,
            old_values={"status": "active"}, new_values={"status": "inactive"},
        )
        await user_service.db.commit()
    except Exception:
        pass
    return UserResponse.model_validate(user)


@router.post("/{user_id}/enable", response_model=UserResponse)
async def enable_user(
    user_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service),
):
    """Re-enable a disabled user (status=active)."""
    user = await user_service.get_user(user_id)
    _can_manage_target(tenant_context, user)
    user.status = UserStatus.ACTIVE
    user.failed_login_count = 0
    user.locked_until = None
    user.updated_at = utc_now()
    await user_service.db.commit()

    try:
        from platform_services.audit_log_service import AuditLogService
        await AuditLogService(user_service.db).append(
            "user_enabled", "user", user.id,
            actor_id=UUID(tenant_context.user_id), school_id=user.school_id,
            old_values={"status": user.status.value}, new_values={"status": "active"},
        )
        await user_service.db.commit()
    except Exception:
        pass
    return UserResponse.model_validate(user)


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