"""
Evidence API routes per PRS §24 and PRS §47/BR-27.
Provides endpoints for evidence upload and deletion with retention checks.
"""
import os
from typing import Optional
from uuid import UUID
from datetime import timedelta, datetime
import cloudinary

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.errors import ValidationError as ServiceValidationError, BusinessRuleError as ServiceBusinessRuleError
from modules.observation_capture.services.evidence_service import EvidenceService
from shared.middleware import get_current_user
from shared.middleware.permissions import PermissionChecker
from shared.middleware.tenancy import require_tenant_context, scoped_to_tenant
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_client_ip(request: Request) -> str:
    """
    Get client IP address, handling proxy headers (A9 security fix).
    Trusts X-Forwarded-For header only if app is behind known proxy.
    Takes the RIGHTMOST IP from X-Forwarded-For (the one added by trusted proxy).
    Falls back to remote address for direct connections.
    
    ASSUMPTION: Single trusted proxy hop. If multiple hops exist, 
    this logic needs adjustment to take the correct position.
    """
    # Check if app is behind proxy (via environment variable)
    behind_proxy = os.getenv("BEHIND_PROXY", "false").lower() == "true"
    
    if behind_proxy:
        # Trust X-Forwarded-For header from known proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For format: client, proxy1, proxy2
            # The RIGHTMOST IP is the one added by our trusted proxy
            # This prevents client spoofing
            # ASSUMPTION: Single trusted proxy hop. Rightmost = proxy's view of client
            ips = [ip.strip() for ip in forwarded_for.split(",")]
            return ips[-1] if ips else "unknown"
        
        # Fall back to X-Real-IP if X-Forwarded-For not present
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
    
    # Direct connection - use remote address
    return request.client.host if request.client else "unknown"


router = APIRouter(prefix="/evidence", tags=["evidence"])
limiter = Limiter(key_func=get_client_ip)


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


class EvidenceSignedUrlResponse(BaseModel):
    signed_url: str
    expires_at: str


# ── Evidence Endpoints ───────────────────────────────────────────────────

@router.post("/upload", response_model=EvidenceUploadResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")  # Rate limit evidence uploads (M2 security fix)
async def upload_evidence(
    request: Request,
    file: UploadFile = File(..., description="File to upload"),
    school_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),  # Require authentication (M2 security fix)
):
    """
    Upload evidence file to Cloudinary.
    
    Security fixes (M2):
    - Requires authentication via get_current_user
    - Rate limited to prevent abuse
    - File size validation performed by service
    - File format validation restricted to safe types
    """
    # Read file data
    file_data = await file.read()
    file_name = file.filename
    content_type = file.content_type or "application/octet-stream"
    
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
    tenant_context = Depends(require_tenant_context),
):
    """
    Check if evidence is eligible for deletion per PRS §47/BR-27.
    Available to Admin and SuperAdmin roles.
    Includes tenant context verification to prevent cross-tenant access (A7 security fix).
    """
    # Require Admin or SuperAdmin role
    normalized_roles = [r.lower() if isinstance(r, str) else r for r in tenant_context.roles]
    if "admin" not in normalized_roles and "superadmin" not in normalized_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or SuperAdmin role required")
    
    # Verify observation belongs to user's tenant (A7 security fix)
    from shared.platform_models import Observation
    
    observation = await db.get(Observation, observation_id)
    if not observation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation not found")
    
    if not scoped_to_tenant(tenant_context, str(observation.school_id), str(observation.department_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this observation")
    
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


@router.get("/signed-url/{observation_id}/{public_id}", response_model=EvidenceSignedUrlResponse)
@limiter.limit("30/minute")  # Rate limit signed URL generation (security fix)
async def get_evidence_signed_url(
    request: Request,
    observation_id: UUID,
    public_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    tenant_context = Depends(require_tenant_context),
):
    """
    Generate a signed URL for evidence access (A7 security fix).
    Required because evidence is uploaded with type='authenticated' for security.
    Includes tenant context verification to prevent cross-tenant access.
    Rate limited to prevent abuse (30/minute).
    """
    # Verify observation belongs to user's tenant (A7 security fix)
    from shared.platform_models import Observation
    
    observation = await db.get(Observation, observation_id)
    if not observation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation not found")
    
    if not scoped_to_tenant(tenant_context, str(observation.school_id), str(observation.department_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this observation")
    
    # Verify evidence belongs to this observation
    if observation.evidence:
        evidence_found = any(e.get("public_id") == public_id for e in observation.evidence if isinstance(e, dict))
        if not evidence_found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found in this observation")
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No evidence on this observation")
    
    # Generate signed URL with 1-hour expiry
    expires_at = datetime.utcnow() + timedelta(hours=1)
    signed_url = cloudinary.utils.cloudinary_url(
        public_id,
        resource_type="auto",
        type="authenticated",
        sign_url=True,
        expires_at=int(expires_at.timestamp())
    )
    
    return EvidenceSignedUrlResponse(
        signed_url=signed_url,
        expires_at=expires_at.isoformat()
    )


@router.post("/delete", response_model=EvidenceDeletionResponse)
async def delete_evidence(
    request: EvidenceDeletionRequest,
    school_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    tenant_context = Depends(require_tenant_context),
):
    """
    Delete evidence with explicit Admin/SuperAdmin action and audit logging per PRS §47/BR-27, FR-271–274.
    
    Enforces:
    - Retention period must have elapsed (rejects deletion even for SuperAdmin)
    - Actor must be Admin or SuperAdmin
    - Deletion is logged to Audit Log with actor identity and timestamp
    - Tenant context verification to prevent cross-tenant access (A7 security fix)
    """
    # Require Admin or SuperAdmin role
    normalized_roles = [r.lower() if isinstance(r, str) else r for r in tenant_context.roles]
    if "admin" not in normalized_roles and "superadmin" not in normalized_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or SuperAdmin role required")
    
    # Verify observation belongs to user's tenant (A7 security fix)
    from shared.platform_models import Observation
    from shared.middleware.tenancy import scoped_to_tenant
    
    observation = await db.get(Observation, request.observation_id)
    if not observation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation not found")
    
    if not scoped_to_tenant(tenant_context, str(observation.school_id), str(observation.department_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this observation")
    
    service = EvidenceService(db)
    try:
        result = await service.delete_evidence_with_audit(
            observation_id=request.observation_id,
            public_id=request.public_id,
            actor_id=current_user.user_id,
            school_id=school_id,
            reason=request.reason,
        )
        return EvidenceDeletionResponse(**result)
    except ServiceBusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
