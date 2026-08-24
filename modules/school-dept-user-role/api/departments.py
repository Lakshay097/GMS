"""
Department API endpoints implementing PRS §19 Department Management.
"""
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel, Field
from datetime import datetime
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
    auto_accept_requests: bool = False


class DepartmentUpdateRequest(BaseModel):
    """Request model for department update."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    head_user_id: Optional[UUID] = None
    auto_accept_requests: Optional[bool] = None


class DepartmentResponse(BaseModel):
    """Response model for department."""
    id: UUID
    school_id: UUID
    school_name: Optional[str] = None
    school_code: Optional[str] = None
    name: str
    code: str
    status: str
    description: Optional[str]
    head_user_id: Optional[UUID]
    auto_accept_requests: bool
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]
    
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


@router.post("", response_model=DepartmentResponse, status_code=http_status.HTTP_201_CREATED)
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
    Only SuperAdmin can create standard departments (based on KPI seed data).
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can create departments"}}
        )
    
    # Standard department codes based on KPI seed data (department names, not role names)
    STANDARD_DEPT_CODES = {"ACADEMICS", "SOTC", "ACCOUNTS", "FACILITY", "IT", "STORE", "SECURITY", "MARKETING", "TELECALLING"}
    
    # If trying to create a standard department, only SuperAdmin can do it
    if request.code in STANDARD_DEPT_CODES and UserRole.SUPERADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin can create standard departments"}}
        )
    
    # If Admin, check they're creating in their own school
    if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
        if str(request.school_id) != tenant_context.school_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Admin can only create departments in their own school"}}
            )
    
    try:
        department = await department_service.create_department(
            school_id=request.school_id,
            name=request.name,
            code=request.code,
            description=request.description,
            head_user_id=request.head_user_id,
            auto_accept_requests=request.auto_accept_requests,
            created_by_user_id=UUID(tenant_context.user_id)
        )
        return DepartmentResponse.model_validate(department)
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


@router.get("", response_model=DepartmentListResponse)
async def list_departments(
    school_id: Optional[UUID] = None,
    status_filter: Optional[DepartmentStatus] = None,
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
            status=status_filter,
            page=page,
            page_size=page_size
        )
        
        # Create simple response without complex field additions
        department_responses = []
        for dept in departments:
            dept_data = {
                "id": dept.id,
                "school_id": dept.school_id,
                "school_name": dept.school.name if dept.school else None,
                "school_code": dept.school.code if dept.school else None,
                "name": dept.name,
                "code": dept.code,
                "status": dept.status.value if hasattr(dept.status, 'value') else dept.status,
                "description": dept.description,
                "head_user_id": dept.head_user_id,
                "auto_accept_requests": dept.auto_accept_requests,
                "created_at": dept.created_at,
                "updated_at": dept.updated_at,
                "archived_at": dept.archived_at
            }
            department_responses.append(DepartmentResponse(**dept_data))
        
        return DepartmentListResponse(
            data=department_responses,
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
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "Department not found"}}
            )
        
        return DepartmentResponse.model_validate(department)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Department not found"}}
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
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
    Only SuperAdmin can update standard departments (based on KPI seed data).
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can update departments"}}
        )
    
    try:
        # First get the department to check scope
        department = await department_service.get_department(department_id)
        
        # Standard department codes based on KPI seed data (department names, not role names)
        STANDARD_DEPT_CODES = {"ACADEMICS", "SOTC", "ACCOUNTS", "FACILITY", "IT", "STORE", "SECURITY", "MARKETING", "TELECALLING"}
        
        # If trying to update a standard department, only SuperAdmin can do it
        if department.code in STANDARD_DEPT_CODES and UserRole.SUPERADMIN.value not in tenant_context.roles:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin can update standard departments"}}
            )
        
        # If Admin, check they're updating in their own school
        if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
            if str(department.school_id) != tenant_context.school_id:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "FORBIDDEN", "message": "Admin can only update departments in their own school"}}
                )
        
        updated_department = await department_service.update_department(
            department_id=department_id,
            name=request.name,
            description=request.description,
            head_user_id=request.head_user_id,
            auto_accept_requests=request.auto_accept_requests,
            updated_by_user_id=UUID(tenant_context.user_id)
        )
        return DepartmentResponse.model_validate(updated_department)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Department not found"}}
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


@router.post("/{department_id}/archive", response_model=DepartmentResponse)
async def archive_department(
    department_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    department_service: DepartmentService = Depends(get_department_service)
):
    """
    Archive a department (soft delete).
    FR-014: Block archival while open Tasks or unresolved Discrepancies exist
    Only SuperAdmin can archive standard departments (based on KPI seed data).
    Admin can only archive non-standard departments in their own school.
    """
    # Check permission: SuperAdmin or Admin
    if UserRole.SUPERADMIN.value not in tenant_context.roles and UserRole.ADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin or Admin can archive departments"}}
        )
    
    try:
        # First get the department to check scope
        department = await department_service.get_department(department_id)
        
        # Standard department codes based on KPI seed data (department names, not role names)
        STANDARD_DEPT_CODES = {"ACADEMICS", "SOTC", "ACCOUNTS", "FACILITY", "IT", "STORE", "SECURITY", "MARKETING", "TELECALLING"}
        
        # If trying to archive a standard department, only SuperAdmin can do it
        if department.code in STANDARD_DEPT_CODES and UserRole.SUPERADMIN.value not in tenant_context.roles:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin can archive standard departments"}}
            )
        
        # If Admin, check they're archiving in their own school
        if UserRole.ADMIN.value in tenant_context.roles and UserRole.SUPERADMIN.value not in tenant_context.roles:
            if str(department.school_id) != tenant_context.school_id:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={"error": {"code": "FORBIDDEN", "message": "Admin can only archive departments in their own school"}}
                )
        
        archived_department = await department_service.archive_department(
            department_id=department_id,
            archived_by_user_id=UUID(tenant_context.user_id)
        )
        return DepartmentResponse.model_validate(archived_department)
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Department not found"}}
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


@router.post("/standard-departments/create-all", response_model=dict)
async def create_standard_departments_all_schools(
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Create standard departments across all schools based on KPI seed data.
    This is a SuperAdmin-only operation.
    Standard departments are: PRINCIPAL, SOTC, ACCOUNTANT, FACILITY, IT, STORE, SECURITY, MARKETING, TELECALLER
    """
    # Check permission: Only SuperAdmin
    if UserRole.SUPERADMIN.value not in tenant_context.roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Only SuperAdmin can create standard departments across all schools"}}
        )
    
    # Standard departments based on KPI seed data (department names, not role names)
    STANDARD_DEPARTMENTS = [
        {"name": "Academics", "code": "ACADEMICS", "description": "Academic administration and leadership"},
        {"name": "SOTC", "code": "SOTC", "description": "Safety, Operations, Transport & Compliance"},
        {"name": "Accounts", "code": "ACCOUNTS", "description": "Financial management and accounting"},
        {"name": "Facility", "code": "FACILITY", "description": "Infrastructure and facilities management"},
        {"name": "IT", "code": "IT", "description": "Information technology and systems management"},
        {"name": "Store", "code": "STORE", "description": "Inventory and store management"},
        {"name": "Security", "code": "SECURITY", "description": "Campus security and safety"},
        {"name": "Marketing", "code": "MARKETING", "description": "Marketing and admissions"},
        {"name": "Telecalling", "code": "TELECALLING", "description": "Telecommunications and parent communication"}
    ]
    
    try:
        from sqlalchemy import select
        from shared.models import School, Department, DepartmentStatus
        from shared.datetime_utils import utc_now
        import uuid
        
        # Get all active schools
        schools_result = await db.execute(
            select(School).where(School.status == "active")
        )
        schools = schools_result.scalars().all()
        
        if not schools:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "NOT_FOUND", "message": "No active schools found"}}
            )
        
        results = {
            "schools_processed": len(schools),
            "departments_created": 0,
            "departments_already_existed": 0,
            "details": []
        }
        
        for school in schools:
            school_details = {
                "school_id": str(school.id),
                "school_name": school.name,
                "school_code": school.code,
                "departments_created": [],
                "departments_already_existed": []
            }
            
            # Check existing departments for this school
            existing_depts_result = await db.execute(
                select(Department.code).where(Department.school_id == school.id)
            )
            existing_codes = {row[0] for row in existing_depts_result.fetchall()}
            
            # Create missing standard departments
            for dept in STANDARD_DEPARTMENTS:
                if dept["code"] not in existing_codes:
                    new_dept = Department(
                        id=uuid.uuid4(),
                        school_id=school.id,
                        name=dept["name"],
                        code=dept["code"],
                        status=DepartmentStatus.ACTIVE,
                        description=dept["description"],
                        created_at=utc_now(),
                        updated_at=utc_now()
                    )
                    db.add(new_dept)
                    school_details["departments_created"].append(dept["code"])
                    results["departments_created"] += 1
                else:
                    school_details["departments_already_existed"].append(dept["code"])
                    results["departments_already_existed"] += 1
            
            results["details"].append(school_details)
        
        await db.commit()
        
        return results
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "INTERNAL_ERROR", "message": str(e)}}
        )