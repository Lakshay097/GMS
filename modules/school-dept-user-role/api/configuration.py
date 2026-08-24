"""
Configuration API endpoints implementing PRS §54 Configuration Management.
"""
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import UserRole
from shared.errors import ValidationError, NotFoundError, AuthorizationError
from shared.middleware.tenancy import require_tenant_context, TenantContext
from shared.middleware.permissions import PermissionChecker, Module, Action

from modules.school_dept_user_role.services.configuration_service import ConfigurationService


router = APIRouter(prefix="/configuration", tags=["configuration"])


# Request/Response Models
class GlobalConfigurationUpdateRequest(BaseModel):
    """Request model for global configuration update."""
    updates: Dict[str, Any] = Field(..., description="Configuration key-value pairs to update")


class SchoolConfigurationUpdateRequest(BaseModel):
    """Request model for school configuration update."""
    school_id: UUID
    updates: Dict[str, Any] = Field(..., description="Configuration key-value pairs to update")


class SchoolConfigurationResetRequest(BaseModel):
    """Request model for school configuration reset."""
    school_id: UUID
    keys: list[str] = Field(..., description="Configuration keys to reset to global defaults")


class ConfigurationResponse(BaseModel):
    """Response model for configuration."""
    configuration: Dict[str, Any]


def get_configuration_service(db: AsyncSession = Depends(get_db)) -> ConfigurationService:
    """
    Dependency to get ConfigurationService instance.
    """
    from platform_services.configuration_engine import ConfigurationEngine
    from platform_services.audit_log_service import AuditLogService
    
    # This is a simplified implementation - in production, these would be properly injected
    config_engine = ConfigurationEngine(db)
    audit_log = AuditLogService(db)
    
    return ConfigurationService(db, config_engine, audit_log)


@router.get("/global", response_model=ConfigurationResponse)
async def get_global_configuration(
    tenant_context: TenantContext = Depends(require_tenant_context),
    config_service: ConfigurationService = Depends(get_configuration_service)
):
    """
    Get global configuration values.
    All roles can read global configuration.
    """
    try:
        config = await config_service.get_global_configuration()
        return ConfigurationResponse(configuration=config)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.patch("/global", response_model=ConfigurationResponse)
async def update_global_configuration(
    request: GlobalConfigurationUpdateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    config_service: ConfigurationService = Depends(get_configuration_service)
):
    """
    Update global configuration values.
    R-44: Only SuperAdmin manages Global Configuration
    """
    # Only SuperAdmin can update global configuration
    if UserRole.SUPERADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin can update global configuration"}}
        )
    
    try:
        config = await config_service.update_global_configuration(
            updates=request.updates,
            updated_by_user_id=UUID(tenant_context.user_id)
        )
        return ConfigurationResponse(configuration=config)
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


@router.get("/schools/{school_id}", response_model=ConfigurationResponse)
async def get_school_configuration(
    school_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    config_service: ConfigurationService = Depends(get_configuration_service)
):
    """
    Get school-specific configuration values.
    Includes global defaults with school overrides applied.
    """
    try:
        # Check scope access
        from shared.middleware.tenancy import scoped_to_tenant
        if not scoped_to_tenant(tenant_context, str(school_id)):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "School not found"}}
            )
        
        config = await config_service.get_school_configuration(school_id)
        return ConfigurationResponse(configuration=config)
    except NotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.patch("/schools/{school_id}", response_model=ConfigurationResponse)
async def update_school_configuration(
    school_id: UUID,
    request: SchoolConfigurationUpdateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    config_service: ConfigurationService = Depends(get_configuration_service)
):
    """
    Update school-specific configuration values.
    R-44: School-scoped subsets are delegable to Admin only where PRS §54 explicitly says so
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can update school configuration"}}
        )
    
    # If Admin, check they're updating their own school
    if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
        if str(school_id) != tenant_context.school_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Admin can only update configuration for their own school"}}
            )
    
    try:
        config = await config_service.update_school_configuration(
            school_id=school_id,
            updates=request.updates,
            updated_by_user_id=UUID(tenant_context.user_id)
        )
        return ConfigurationResponse(configuration=config)
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


@router.post("/schools/{school_id}/reset", response_model=ConfigurationResponse)
async def reset_school_configuration(
    school_id: UUID,
    request: SchoolConfigurationResetRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    config_service: ConfigurationService = Depends(get_configuration_service)
):
    """
    Reset school-specific configuration keys to global defaults.
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can reset school configuration"}}
        )
    
    # If Admin, check they're resetting their own school
    if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
        if str(school_id) != tenant_context.school_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Admin can only reset configuration for their own school"}}
            )
    
    try:
        config = await config_service.reset_school_configuration(
            school_id=school_id,
            keys=request.keys,
            reset_by_user_id=UUID(tenant_context.user_id)
        )
        return ConfigurationResponse(configuration=config)
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