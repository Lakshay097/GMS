"""
Department request approval API endpoints.
Handles approval/rejection of self-service department requests.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.models import (
    User, UserStatus, Department, DepartmentRequestStatus, DepartmentStatus
)
from shared.database import get_db
from shared.middleware.tenancy import get_current_user
from modules.school_dept_user_role.services.department_service import DepartmentService


router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalRequestResponse(BaseModel):
    """Department request response model."""
    id: str
    user_id: str
    full_name: str
    email: str
    school_id: str
    school_name: str
    school_code: str
    requested_department_id: str
    requested_department_name: str
    requested_department_code: str
    requested_at: str


class ApproveRequest(BaseModel):
    """Approve department request model."""
    department_id: str = Field(..., description="Department ID to approve")


class RejectRequest(BaseModel):
    """Reject department request model."""
    department_id: str = Field(..., description="Department ID to reject")
    rejection_reason: Optional[str] = Field(None, description="Optional rejection reason")


@router.get("/pending", response_model=List[ApprovalRequestResponse])
async def list_pending_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List pending department requests.
    SuperAdmin/Admin see all requests across all schools.
    Dept Heads see only their department's requests.
    """
    # Check permissions - SuperAdmin and Admin see all
    normalized_roles = [r.lower() if isinstance(r, str) else r for r in current_user.roles]
    is_superadmin = "superadmin" in normalized_roles
    is_admin = "admin" in normalized_roles

    # Build base query
    from shared.models import School
    query = (
        select(User, Department)
        .join(Department, User.requested_department_id == Department.id)
        .join(School, User.school_id == School.id)
        .where(User.department_request_status == DepartmentRequestStatus.PENDING)
        .where(User.status == UserStatus.ACTIVE)
    )

    # If Dept Head, filter to their department only
    if not is_superadmin and not is_admin:
        if current_user.department_id:
            query = query.where(Department.id == current_user.department_id)
        else:
            # Dept Head without department - return empty
            return []

    result = await db.execute(query)
    rows = result.all()

    requests = []
    for user, department in rows:
        requests.append(ApprovalRequestResponse(
            id=str(user.id),
            user_id=str(user.id),
            full_name=user.full_name,
            email=user.email,
            school_id=str(user.school_id),
            school_name=user.school.name if user.school else "",
            school_code=user.school.code if user.school else "",
            requested_department_id=str(department.id),
            requested_department_name=department.name,
            requested_department_code=department.code,
            requested_at=user.requested_at.isoformat() if user.requested_at else ""
        ))

    return requests


@router.post("/{user_id}/approve")
async def approve_request(
    user_id: str,
    request_data: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Approve a department request.
    Sets user's department_id and updates request status to approved.
    """
    # Find user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.department_request_status != DepartmentRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a pending department request"
        )

    # Verify the requested department matches
    if str(user.requested_department_id) != request_data.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department ID does not match requested department"
        )

    # Verify department exists and is active
    result = await db.execute(
        select(Department).where(
            Department.id == request_data.department_id,
            Department.status == DepartmentStatus.ACTIVE
        )
    )
    department = result.scalar_one_or_none()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found or inactive"
        )

    # Check permissions if not SuperAdmin/Admin
    normalized_roles = [r.lower() if isinstance(r, str) else r for r in current_user.roles]
    is_superadmin = "superadmin" in normalized_roles
    is_admin = "admin" in normalized_roles

    if not is_superadmin and not is_admin:
        if current_user.department_id != department.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only approve requests for your department"
            )

    # Approve the request
    user.department_id = department.id
    user.requested_department_id = None
    user.department_request_status = DepartmentRequestStatus.APPROVED

    await db.commit()

    return {"status": "approved"}


@router.post("/{user_id}/reject")
async def reject_request(
    user_id: str,
    request_data: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reject a department request.
    Resets request status to none, stores rejection reason.
    User can re-request later.
    """
    # Find user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.department_request_status != DepartmentRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a pending department request"
        )

    # Verify the requested department matches
    if str(user.requested_department_id) != request_data.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department ID does not match requested department"
        )

    # Verify department exists
    result = await db.execute(
        select(Department).where(Department.id == request_data.department_id)
    )
    department = result.scalar_one_or_none()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    # Check permissions if not SuperAdmin/Admin
    normalized_roles = [r.lower() if isinstance(r, str) else r for r in current_user.roles]
    is_superadmin = "superadmin" in normalized_roles
    is_admin = "admin" in normalized_roles

    if not is_superadmin and not is_admin:
        if current_user.department_id != department.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only reject requests for your department"
            )

    # Reject the request - reset to none so they can re-request
    user.requested_department_id = None
    user.department_request_status = DepartmentRequestStatus.NONE

    # Store rejection reason (could add a dedicated field for this in future)
    # For now, we'll store it in a temporary metadata field or just log it
    # TODO: Add rejection_reason field to User model if needed

    await db.commit()

    return {"status": "rejected"}
