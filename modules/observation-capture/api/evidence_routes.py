"""
Evidence API routes per PRS §24 and PRS §47/BR-27.
Provides endpoints for evidence upload and deletion with retention checks.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.errors import ValidationError as ServiceValidationError, BusinessRuleError as ServiceBusinessRuleError
from modules.observation_capture.services.evidence_service import EvidenceService
from shared.middleware import get_current_user, require_roles

router = APIRouter(prefix="/evidence", tags=["evidence"])


# ── Schemas ──────────────────────────────────────────────────────────────

class EvidenceUploadResponse(BaseModel):
    cloudinary_public_id: str
    cloudinary_url: str
    file_size_bytes: int
    format: Optional[str]
    resource_type: Optional[str]


class EvidenceDeletionEligibilityResponse(BaseModel):
    eligible: bool
    retention_period_days: int
    submitted_at: str
    retention_eligible_at: str
    days_until_eligible: int
    public_id: str


class EvidenceDeletionRequest(BaseModel):
    observation_id: UUID
    public_id: str
    reason: Optional[str] = Field(None, description="Optional reason for deletion")


class EvidenceDeletionResponse(BaseModel):
    success: bool
    public_id: str
    observation_id: str
    deleted_at: str
    audit_log_id: str
    reason: Optional[str]


# ── Evidence Endpoints ───────────────────────────────────────────────────

@router.post("/upload", response_model=EvidenceUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    file_data: bytes = Field(..., description="File data as bytes"),
    file_name: str = Field(..., description="Original file name"),
    content_type: str = Field(..., description="MIME content type"),
    school_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload evidence file to Cloudinary."""
    service = EvidenceService(db)
    try:
        result = await service.upload_evidence(
            file_data=file_data,
            file_name=file_name,
            content_type=content_type,
            school_id=str(school_id) if school_id else None,
        )
        return EvidenceUploadResponse(**result)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/deletion-eligibility/{observation_id}/{public_id}", response_model=EvidenceDeletionEligibilityResponse)
async def check_evidence_deletion_eligibility(
    observation_id: UUID,
    public_id: str,
    school_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Check if evidence is eligible for deletion per PRS §47/BR-27.
    Available to Admin and SuperAdmin roles.
    """
    # Require Admin or SuperAdmin role
    user_roles = current_user.get("roles", [])
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or SuperAdmin role required")
    
    service = EvidenceService(db)
    try:
        eligibility = await service.is_evidence_deletion_eligible(
            observation_id=observation_id,
            public_id=public_id,
            school_id=school_id,
        )
        return EvidenceDeletionEligibilityResponse(**eligibility)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/delete", response_model=EvidenceDeletionResponse)
async def delete_evidence(
    request: EvidenceDeletionRequest,
    school_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Delete evidence with explicit Admin/SuperAdmin action and audit logging per PRS §47/BR-27, FR-271–274.
    
    Enforces:
    - Retention period must have elapsed (rejects deletion even for SuperAdmin)
    - Actor must be Admin or SuperAdmin
    - Deletion is logged to Audit Log with actor identity and timestamp
    """
    # Require Admin or SuperAdmin role
    user_roles = current_user.get("roles", [])
    if "admin" not in user_roles and "super_admin" not in user_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or SuperAdmin role required")
    
    service = EvidenceService(db)
    try:
        result = await service.delete_evidence_with_audit(
            observation_id=request.observation_id,
            public_id=request.public_id,
            actor_id=current_user.get("user_id"),
            school_id=school_id,
            reason=request.reason,
        )
        return EvidenceDeletionResponse(**result)
    except ServiceBusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
