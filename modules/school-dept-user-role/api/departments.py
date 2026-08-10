"""
Department API endpoints implementing PRS §19 Department Management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import DepartmentStatus, UserRole
from shared.errors import ValidationError, NotFoundError, AuthorizationError
from shared.middleware.tenancy import require_tenant_context, TenantContext
from shared.middleware.permissions import PermissionChecker, Module, Action
from shared.models import Department

from modules.school_dept_user_role.services.department_service import DepartmentService


router = APIRouter(prefix="/departments", tags=["departments"])


# Request/Response Models
class DepartmentCreateRequest(BaseModel):
    """Request model for department creation."""
    school_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    head_user_id: Optional[UUID] = None


class DepartmentUpdateRequest(BaseModel):
    """Request model for department update."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    head_user_id: Optional[UUID] = None


class DepartmentResponse(BaseModel):
    """Response model for department."""
    id: UUID
    school_id: UUID
    name: str
    code: str
    status: str
    description: Optional[str]
    head_user_id: Optional[UUID]
    created_at: str
    updated_at: str
    archived_at: Optional[str]
    
    class Config:
        from_attributes = True


class DepartmentListResponse(BaseModel):
    """Response model for department list."""
    data: List[DepartmentResponse]
    pagination: dict


def get_department_service(db: AsyncSession = Depends(get_db)) -> DepartmentService:
    """
    Dependency to get DepartmentService instance.
    """
    from platform_services.audit_log_service import AuditLogService
    
    # This is a simplified implementation - in production, these would be properly injected
    audit_log = AuditLogService(db)
    
    return DepartmentService(db, audit_log)


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    request: DepartmentCreateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    department_service: DepartmentService = Depends(get_department_service)
):
    """
    Create a new department.
    FR-018: Admin can create additional departments beyond auto-created defaults
    SuperAdmin can create departments in any school
    Admin can only create departments in their own school
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can create departments"}}
        )
    
    # If Admin, check they're creating in their own school
    if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
        if str(request.school_id) != tenant_context.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Admin can only create departments in their own school"}}
            )
    
    try:
        department = await department_service.create_department(
            school_id=request.school_id,
            name=request.name,
            code=request.code,
            description=request.description,
            head_user_id=request.head_user_id,
            created_by_user_id=UUID(tenant_context.user_id)
        )
        return DepartmentResponse.model_validate(department)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(e)}}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.get("", response_model=DepartmentListResponse)
async def list_departments(
    school_id: Optional[UUID] = None,
    status: Optional[DepartmentStatus] = None,
    page: int = 1,
    page_size: int = 50,
    tenant_context: TenantContext = Depends(require_tenant_context),
    department_service: DepartmentService = Depends(get_department_service)
):
    """
    List departments.
    All roles can view departments within their scope.
    """
    try:
        # If not SuperAdmin, restrict to their school
        if UserRole.SUPERADMIN.value not in tenant_context.roles:
            school_id = UUID(tenant_context.school_id)
        
        departments, total = await department_service.list_departments(
            school_id=school_id,
            status=status,
            page=page,
            page_size=page_size
        )
        
        return DepartmentListResponse(
            data=[DepartmentResponse.model_validate(dept) for dept in departments],
            pagination={
                "page": page,
                "page_size": page_size,
                "total_count": total,
                "has_next": page * page_size < total
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    department_service: DepartmentService = Depends(get_department_service)
):
    """
    Get department by ID.
    """
    try:
        department = await department_service.get_department(department_id)
        
        # Check scope access
        from shared.middleware.tenancy import scoped_to_tenant
        if not scoped_to_tenant(tenant_context, str(department.school_id), str(department.id)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Department not found"}}
            )
        
        return DepartmentResponse.model_validate(department)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Department not found"}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: UUID,
    request: DepartmentUpdateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    department_service: DepartmentService = Depends(get_department_service)
):
    """
    Update department details.
    SuperAdmin can update any department.
    Admin can only update departments in their own school.
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can update departments"}}
        )
    
    try:
        # First get the department to check scope
        department = await department_service.get_department(department_id)
        
        # If Admin, check they're updating in their own school
        if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
            if str(department.school_id) != tenant_context.school_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "FORBIDDEN", "message": "Admin can only update departments in their own school"}}
                )
        
        updated_department = await department_service.update_department(
            department_id=department_id,
            name=request.name,
            description=request.description,
            head_user_id=request.head_user_id,
            updated_by_user_id=UUID(tenant_context.user_id)
        )
        return DepartmentResponse.model_validate(updated_department)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Department not found"}}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )


@router.post("/{department_id}/archive", response_model=DepartmentResponse)
async def archive_department(
    department_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    department_service: DepartmentService = Depends(get_department_service)
):
    """
    Archive a department (soft delete).
    FR-014: Block archival while open Tasks or unresolved Discrepancies exist
    SuperAdmin can archive any department.
    Admin can only archive departments in their own school.
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can archive departments"}}
        )
    
    try:
        # First get the department to check scope
        department = await department_service.get_department(department_id)
        
        # If Admin, check they're archiving in their own school
        if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
            if str(department.school_id) != tenant_context.school_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "FORBIDDEN", "message": "Admin can only archive departments in their own school"}}
                )
        
        archived_department = await department_service.archive_department(
            department_id=department_id,
            archived_by_user_id=UUID(tenant_context.user_id)
        )
        return DepartmentResponse.model_validate(archived_department)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Department not found"}}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(e), "field": e.field}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )