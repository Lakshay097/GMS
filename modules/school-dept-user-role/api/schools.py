"""
School API endpoints implementing PRS §18 School Management.
"""
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import SchoolStatus, UserRole
from shared.errors import ValidationError, NotFoundError, AuthorizationError
from shared.middleware.tenancy import require_tenant_context, TenantContext
from shared.middleware.permissions import PermissionChecker, Module, Action
from shared.models import School

from modules.school_dept_user_role.services.school_service import SchoolService


router = APIRouter(prefix="/schools", tags=["schools"])


# Request/Response Models
class SchoolCreateRequest(BaseModel):
    """Request model for school creation."""
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    address: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)


class SchoolUpdateRequest(BaseModel):
    """Request model for school update."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)


class SchoolResponse(BaseModel):
    """Response model for school."""
    id: UUID
    name: str
    code: str
    status: str
    address: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    timezone: Optional[str]
    working_days: List[str]
    created_at: datetime
    updated_at: datetime
    deactivated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class SchoolListResponse(BaseModel):
    """Response model for school list."""
    data: List[SchoolResponse]
    pagination: dict


def get_school_service(db: AsyncSession = Depends(get_db)) -> SchoolService:
    """
    Dependency to get SchoolService instance.
    """
    from platform_services.configuration_engine import ConfigurationEngine
    from platform_services.audit_log_service import AuditLogService
    
    # This is a simplified implementation - in production, these would be properly injected
    config_engine = ConfigurationEngine(db)
    audit_log = AuditLogService(db)
    
    return SchoolService(db, config_engine, audit_log)


@router.post("", response_model=SchoolResponse, status_code=http_status.HTTP_201_CREATED)
async def create_school(
    request: SchoolCreateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    school_service: SchoolService = Depends(get_school_service)
):
    """
    Create a new school.
    FR-001: Only SuperAdmin can create schools
    FR-006: Atomic operation - creates departments + imports KPI library + creates first Admin
    """
    # FR-001: Only SuperAdmin can create schools
    if UserRole.SUPERADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin can create schools"}}
        )
    
    try:
        school = await school_service.create_school(
            name=request.name,
            code=request.code,
            address=request.address,
            contact_email=request.contact_email,
            contact_phone=request.contact_phone,
            created_by_user_id=UUID(tenant_context.user_id)
        )
        return SchoolResponse.model_validate(school)
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


@router.get("", response_model=SchoolListResponse)
async def list_schools(
    status_filter: Optional[SchoolStatus] = None,
    page: int = 1,
    page_size: int = 50,
    tenant_context: TenantContext = Depends(require_tenant_context),
    school_service: SchoolService = Depends(get_school_service)
):
    """
    List schools.
    SuperAdmin: All schools
    Viewer: Granted schools only
    """
    try:
        schools, total = await school_service.list_schools(
            status=status_filter,
            page=page,
            page_size=page_size
        )
        
        return SchoolListResponse(
            data=[SchoolResponse.model_validate(school) for school in schools],
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


@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    school_service: SchoolService = Depends(get_school_service)
):
    """
    Get school by ID.
    """
    try:
        school = await school_service.get_school(school_id)
        
        # Check scope access
        from shared.middleware.tenancy import scoped_to_tenant
        if not scoped_to_tenant(tenant_context, str(school.id)):
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "School not found"}}
            )
        
        return SchoolResponse.model_validate(school)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "School not found"}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.patch("/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: UUID,
    request: SchoolUpdateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    school_service: SchoolService = Depends(get_school_service)
):
    """
    Update school details.
    Only SuperAdmin can update schools.
    """
    # Only SuperAdmin can update schools
    if UserRole.SUPERADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin can update schools"}}
        )
    
    try:
        school = await school_service.update_school(
            school_id=school_id,
            name=request.name,
            address=request.address,
            contact_email=request.contact_email,
            contact_phone=request.contact_phone,
            updated_by_user_id=UUID(tenant_context.user_id)
        )
        return SchoolResponse.model_validate(school)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "School not found"}}
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


@router.post("/{school_id}/deactivate", response_model=SchoolResponse)
async def deactivate_school(
    school_id: UUID,
    confirm: bool = Query(False, description="Must be true to confirm destructive action"),
    tenant_context: TenantContext = Depends(require_tenant_context),
    school_service: SchoolService = Depends(get_school_service)
):
    """
    Deactivate a school (soft delete).
    FR-007: Prevent hard deletion, only deactivation permitted
    Only SuperAdmin can deactivate schools.
    
    SECURITY FIX (Route Hygiene): Requires explicit confirmation for destructive action.
    """
    # Only SuperAdmin can deactivate schools
    if UserRole.SUPERADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin can deactivate schools"}}
        )
    
    # Require explicit confirmation (Route Hygiene security fix)
    if not confirm:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "CONFIRMATION_REQUIRED", "message": "Destructive action requires confirmation. Set confirm=true to proceed."}}
        )
    
    try:
        school = await school_service.deactivate_school(
            school_id=school_id,
            deactivated_by_user_id=UUID(tenant_context.user_id)
        )
        return SchoolResponse.model_validate(school)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "School not found"}}
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