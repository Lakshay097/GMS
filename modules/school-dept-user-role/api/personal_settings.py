"""
Personal settings API endpoints for FR-163 Language Preference selection.
Implements GET/PATCH /settings/me per API-Spec §14.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.errors import ValidationError, NotFoundError
from shared.middleware.tenancy import require_tenant_context, TenantContext

from modules.school_dept_user_role.services.user_service import UserService
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.configuration_engine.constants import ConfigKey


router = APIRouter(prefix="/settings", tags=["settings"])


class PersonalSettingsResponse(BaseModel):
    """Response model for the current user's personal settings."""
    language_preference: str


class PersonalSettingsUpdateRequest(BaseModel):
    """Request model for updating personal settings."""
    language_preference: Optional[str] = Field(None, min_length=2, max_length=10)


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """Dependency to get UserService instance."""
    from platform_services.audit_log_service import AuditLogService

    audit_log = AuditLogService(db)
    return UserService(db, audit_log)


def get_config_engine(db: AsyncSession = Depends(get_db)) -> ConfigurationEngine:
    """Dependency to get ConfigurationEngine instance."""
    return ConfigurationEngine(db)


@router.get("/me", response_model=PersonalSettingsResponse)
async def get_my_settings(
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service),
):
    """
    Get the current user's personal settings.
    FR-163: Per-user Language Preference selection.
    Always returns the authenticated user's own preference (self-only).
    """
    try:
        user = await user_service.get_user(UUID(tenant_context.user_id))
        return PersonalSettingsResponse(language_preference=user.language_preference)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}},
        )


@router.patch("/me", response_model=PersonalSettingsResponse)
async def update_my_settings(
    request: PersonalSettingsUpdateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    user_service: UserService = Depends(get_user_service),
    config_engine: ConfigurationEngine = Depends(get_config_engine),
):
    """
    Update the current user's personal settings.
    FR-163: Language preference validated against ConfigurationEngine.LOCALES.
    Always updates the authenticated user's own preference (self-only).
    To update another user's preference, use PATCH /users/{user_id} (Admin/SuperAdmin only).
    """
    try:
        if request.language_preference is not None:
            locales = await config_engine.get(ConfigKey.LOCALES)
            if request.language_preference not in locales:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": f"Invalid language preference. Must be one of: {locales}",
                            "field": "language_preference",
                        }
                    },
                )

        updated_user = await user_service.update_user(
            user_id=UUID(tenant_context.user_id),
            language_preference=request.language_preference,
            updated_by_user_id=UUID(tenant_context.user_id),
        )
        return PersonalSettingsResponse(language_preference=updated_user.language_preference)
    except HTTPException:
        raise
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "User not found"}},
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}},
        )
