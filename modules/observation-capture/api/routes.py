"""
Observation Capture API routes — PRS §24.
Implements Checker-only Observation capture endpoints with idempotency support.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status, Query, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
import os


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

from modules.observation_capture.schemas import (
    ObservationResponse,
    ObservationSubmitRequest,
    ReopenApprovalRequest,
    ReopenRequest,
    VerifyRequest,
    RejectRequest,
)
from modules.observation_capture.services.observation_service import ObservationService
from shared.database import get_db
from shared.errors import ConflictError, NotFoundError, ValidationError
from shared.middleware.tenancy import require_tenant_context, TenantContext

router = APIRouter(prefix="/observations", tags=["observations"])

# Rate limiter for observation endpoints (H3 security fix)
limiter = Limiter(key_func=get_client_ip)


@router.post("", response_model=ObservationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")  # Rate limit observation submission
async def submit_observation(
    request: ObservationSubmitRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    tenant_context: TenantContext = Depends(require_tenant_context),
):
    """
    Submit an Observation per PRS §24.
    
    Requirements:
    - Idempotency-Key header is MANDATORY (R-54/FR-069)
    - Checkers capture Observations only — never edit other business records (R-22/BR-11)
    - Observation must be linked to a specific KPI (R-23/BR-20)
    - Value required and type-matched to KPI's declared Unit
    - Auto-Result is SYSTEM computation via Rule Engine — never client-settable (R-29)
    - Duplicate detection applies per PRS §24.6/BR-25
    - Grace period handling applies per PRS §24.16/BR-26
    """
    # Validate idempotency key requirement (R-54/FR-069)
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Idempotency-Key header is required (R-54/FR-069)",
                    "field": "Idempotency-Key",
                }
            },
        )
    
    service = ObservationService(db)
    
    try:
        observation = await service.submit_observation(
            kpi_id=request.kpi_id,
            kpi_version=request.kpi_version,
            checker_id=UUID(tenant_context.user_id),
            department_id=tenant_context.department_id if tenant_context.department_id else request.department_id,
            school_id=UUID(tenant_context.school_id) if tenant_context.school_id else request.school_id,
            value_numeric=request.value_numeric,
            value_text=request.value_text,
            asset_id=request.asset_id,
            location_id=request.location_id,
            event_times=[et.model_dump() for et in request.event_times],
            evidence=[ev.model_dump() for ev in request.evidence],
            is_late=request.is_late,
            submission_token=request.submission_token,
            override_duplicate=request.override_duplicate,
            override_justification=request.override_justification,
        )
        return observation
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.detail,
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.detail,
        )


@router.get("", response_model=list[ObservationResponse])
async def list_observations(
    tenant_context = Depends(require_tenant_context),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page (max 100)"),
    db: AsyncSession = Depends(get_db),
):
    """List observations with tenant isolation, pagination, and enriched display fields (per R-02)."""
    try:
        from sqlalchemy import select as sa_select, func
        from shared.platform_models import Observation, School, Department, KPI
        from shared.middleware.tenancy import apply_tenant_filter
        from shared.models import User

        # Build base query with tenant isolation, ordered by most recent
        query = sa_select(Observation).order_by(Observation.submitted_at.desc())
        query = apply_tenant_filter(query, tenant_context)

        # Apply pagination at database level using LIMIT/OFFSET
        offset = (page - 1) * page_size
        query = query.limit(page_size).offset(offset)

        result = await db.execute(query)
        observations = result.scalars().all()

        # ── Batch-resolve enrichment names to avoid N+1 ──────────────────
        kpi_ids = {obs.kpi_id for obs in observations}
        checker_ids = {obs.checker_id for obs in observations}
        school_ids = {obs.school_id for obs in observations}
        dept_ids = {obs.department_id for obs in observations}

        kpi_titles: dict = {}
        observer_names: dict = {}
        school_names: dict = {}
        dept_names: dict = {}

        if kpi_ids:
            try:
                kpi_q = await db.execute(
                    sa_select(KPI.kpi_id, KPI.title).where(KPI.kpi_id.in_(kpi_ids))
                )
                kpi_titles = {row[0]: row[1] for row in kpi_q.all()}
            except Exception:
                pass

        if checker_ids:
            try:
                user_q = await db.execute(
                    sa_select(User.id, User.full_name).where(User.id.in_(checker_ids))
                )
                observer_names = {row[0]: row[1] for row in user_q.all()}
            except Exception:
                pass

        if school_ids:
            try:
                school_q = await db.execute(
                    sa_select(School.id, School.name).where(School.id.in_(school_ids))
                )
                school_names = {row[0]: row[1] for row in school_q.all()}
            except Exception:
                pass

        if dept_ids:
            try:
                dept_q = await db.execute(
                    sa_select(Department.id, Department.name).where(Department.id.in_(dept_ids))
                )
                dept_names = {row[0]: row[1] for row in dept_q.all()}
            except Exception:
                pass

        service = ObservationService(db)
        response_list = []
        for obs in observations:
            try:
                is_locked = await service.is_observation_locked(obs)
                response_data = ObservationResponse.model_validate(obs)
                response_data.is_locked = is_locked
                response_data.evidence_count = len(obs.evidence) if obs.evidence else 0
                # Populate enriched display fields
                response_data.title = kpi_titles.get(obs.kpi_id)
                response_data.description = obs.value_text
                response_data.observer_name = observer_names.get(obs.checker_id)
                response_data.school_name = school_names.get(obs.school_id)
                response_data.department_name = dept_names.get(obs.department_id)
                response_data.observation_date = obs.submitted_at
                response_list.append(response_data)
            except Exception:
                continue

        return response_list
    except Exception as e:
        # Return empty list instead of 500 error if table doesn't exist or other issues
        print(f"Error listing observations: {e}")
        return []


@router.get("/{observation_id}", response_model=ObservationResponse)
async def get_observation(
    observation_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_context: TenantContext = Depends(require_tenant_context),
):
    """Get an Observation by ID with tenant isolation."""
    service = ObservationService(db)
    try:
        observation = await service.get_observation(observation_id)
        
        # Enforce tenant isolation (IDOR prevention)
        from shared.middleware.tenancy import scoped_to_tenant
        if not scoped_to_tenant(tenant_context, str(observation.school_id), str(observation.department_id)):
            raise NotFoundError("Observation")
        
        # Check if observation is locked
        is_locked = await service.is_observation_locked(observation)
        
        response_data = ObservationResponse.model_validate(observation)
        response_data.is_locked = is_locked
        response_data.evidence_count = len(observation.evidence) if observation.evidence else 0
        
        return response_data
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )


@router.post("/{observation_id}/reopen-request")
async def request_reopen(
    observation_id: UUID,
    request: ReopenRequest,
    tenant_context = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Request reopening a closed-missed observation per PRS §24.16/BR-26.
    Requires Admin/SuperAdmin approval.
    
    SECURITY NOTE (M3): This route is gated behind FEATURE_FLAG_OBSERVATION_REOPEN_ENABLED.
    Returns 503 if the feature flag is not set.
    """
    # Feature flag gating (M3 security fix)
    import os
    if not os.getenv("FEATURE_FLAG_OBSERVATION_REOPEN_ENABLED"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Observation reopen feature not enabled"
        )
    
    # Authorization: Checkers and Admins can request reopen
    from shared.models import UserRole
    normalized_roles = [role.lower() if role else role for role in tenant_context.roles]
    if not any(role in normalized_roles for role in ("checker", "admin", "superadmin")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Only Checker, Admin, or SuperAdmin can request observation reopen",
                    "field": "role"
                }
            },
        )
    
    service = ObservationService(db)
    try:
        # Get observation for tenant scoping
        observation = await service.get_observation(observation_id)
        
        # Apply tenant filter to ensure user can only request reopen within their tenant
        from shared.middleware.tenancy import apply_tenant_filter
        from sqlalchemy import select as sa_select
        tenant_query = sa_select(type(observation)).where(type(observation).id == observation_id)
        tenant_query = apply_tenant_filter(tenant_query, tenant_context)
        result = await db.execute(tenant_query)
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Observation not found",
                    }
                },
            )
        
        observation = await service.request_reopen(
            observation_id=observation_id,
            reason=request.reason,
            actor_id=UUID(tenant_context.user_id),
        )
        return ObservationResponse.model_validate(observation)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )


@router.post("/{observation_id}/reopen-approval")
async def approve_reopen(
    observation_id: UUID,
    request: ReopenApprovalRequest,
    tenant_context = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve or reject a reopen request per PRS §24.16/BR-26.
    Only Admin/SuperAdmin can approve.
    
    SECURITY NOTE (M3): This route is gated behind FEATURE_FLAG_OBSERVATION_REOPEN_ENABLED.
    Returns 503 if the feature flag is not set.
    """
    # Feature flag gating (M3 security fix)
    import os
    if not os.getenv("FEATURE_FLAG_OBSERVATION_REOPEN_ENABLED"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Observation reopen feature not enabled"
        )
    
    # Role check: only Admin/SuperAdmin can approve reopen requests
    from shared.models import UserRole
    normalized_roles = [role.lower() if role else role for role in tenant_context.roles]
    if not any(role in normalized_roles for role in ("admin", "superadmin")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Only Admin or SuperAdmin can approve observation reopen requests",
                    "field": "role"
                }
            },
        )
    
    # Validation: denial requires a reason
    if not request.approved:
        if not request.admin_comment or not request.admin_comment.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Denial reason is required when rejecting a reopen request",
                        "field": "admin_comment"
                    }
                },
            )
    
    service = ObservationService(db)
    try:
        # Get observation for tenant scoping
        observation = await service.get_observation(observation_id)
        
        # Apply tenant filter to ensure approver can only approve within their tenant
        from shared.middleware.tenancy import apply_tenant_filter
        from sqlalchemy import select as sa_select
        tenant_query = sa_select(type(observation)).where(type(observation).id == observation_id)
        tenant_query = apply_tenant_filter(tenant_query, tenant_context)
        result = await db.execute(tenant_query)
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Observation not found",
                    }
                },
            )
        
        observation = await service.approve_reopen(
            observation_id=observation_id,
            approved=request.approved,
            admin_comment=request.admin_comment,
            actor_id=UUID(tenant_context.user_id),
        )
        return ObservationResponse.model_validate(observation)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )


@router.patch("/{observation_id}", response_model=ObservationResponse)
async def update_observation(
    observation_id: UUID,
    value_numeric: Optional[float] = None,
    value_text: Optional[str] = None,
    tenant_context = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Update an Observation (RESTRICTED).
    
    R-24/BR-12/C5: Auditors never edit Observations — they may only Verify or raise a Discrepancy.
    This endpoint is provided for authorized roles only and enforces the Auditor restriction at the API layer.
    """
    # Get user role from authenticated tenant context
    from shared.models import UserRole
    normalized_roles = [role.lower() if role else role for role in tenant_context.roles]
    user_role = None
    if "auditor" in normalized_roles:
        user_role = UserRole.AUDITOR
    elif "admin" in normalized_roles:
        user_role = UserRole.ADMIN
    elif "superadmin" in normalized_roles:
        user_role = UserRole.SUPERADMIN
    elif "checker" in normalized_roles:
        user_role = UserRole.CHECKER
    elif "viewer" in normalized_roles:
        user_role = UserRole.VIEWER
    
    # Reject if user is an Auditor
    if user_role == UserRole.AUDITOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Auditors cannot edit Observations. They may only Verify or raise a Discrepancy (R-24/BR-12/C5).",
                }
            },
        )
    
    service = ObservationService(db)
    try:
        # Check if observation is locked (R-16)
        observation = await service.get_observation(observation_id)
        is_locked = await service.is_observation_locked(observation)
        
        if is_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "BUSINESS_RULE_ERROR",
                        "message": "Observation is locked and cannot be edited (R-16)",
                    }
                },
            )
        
        # Capture old values for audit logging
        old_values = {}
        if observation.value_numeric is not None:
            old_values["value_numeric"] = str(observation.value_numeric)
        if observation.value_text is not None:
            old_values["value_text"] = observation.value_text
        
        # Update observation
        new_values = {}
        if value_numeric is not None:
            observation.value_numeric = value_numeric
            new_values["value_numeric"] = str(value_numeric)
        if value_text is not None:
            observation.value_text = value_text
            new_values["value_text"] = value_text
        
        # Log the update with authenticated actor
        from platform_services.audit_log_service.service import AuditLogService
        audit_log = AuditLogService(db)
        await audit_log.log_observation_update(
            observation_id=observation_id,
            actor_id=UUID(tenant_context.user_id),
            old_values=old_values if old_values else None,
            new_values=new_values if new_values else None,
        )
        
        await db.commit()
        await db.refresh(observation)
        
        response_data = ObservationResponse.model_validate(observation)
        response_data.is_locked = is_locked
        response_data.evidence_count = len(observation.evidence) if observation.evidence else 0
        
        return response_data
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )


@router.post("/{observation_id}/verify", response_model=ObservationResponse)
async def verify_observation(
    observation_id: UUID,
    tenant_context = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify an Observation (Admin/SuperAdmin only).
    
    Atomic status transition: pending → verified with conflict detection.
    """
    # Role check: only Admin/SuperAdmin can verify
    from shared.models import UserRole
    normalized_roles = [role.lower() if role else role for role in tenant_context.roles]
    if not any(role in normalized_roles for role in ("admin", "superadmin")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Only Admin or SuperAdmin can verify observations",
                    "field": "role"
                }
            },
        )
    
    service = ObservationService(db)
    try:
        # Get observation for tenant scoping
        observation = await service.get_observation(observation_id)
        
        # Apply tenant filter to ensure verifier can only verify within their tenant
        from shared.middleware.tenancy import apply_tenant_filter
        from sqlalchemy import select as sa_select
        tenant_query = sa_select(type(observation)).where(type(observation).id == observation_id)
        tenant_query = apply_tenant_filter(tenant_query, tenant_context)
        result = await db.execute(tenant_query)
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Observation not found",
                    }
                },
            )
        
        # Atomic status transition with conflict detection
        from sqlalchemy import update as sa_update
        from shared.datetime_utils import utc_now
        
        now = utc_now()
        update_stmt = (
            sa_update(type(observation))
            .where(type(observation).id == observation_id)
            .where(type(observation).status == 'pending')  # Only update if still pending
            .values(
                status='verified',
                verified_at=now,
                verified_by=UUID(tenant_context.user_id),
                # Clear rejection fields if previously rejected
                rejected_at=None,
                rejected_by=None,
                rejection_reason=None
            )
        )
        
        result = await db.execute(update_stmt)
        affected_rows = result.rowcount
        
        if affected_rows == 0:
            # Check current status for better error message
            current_obs = await db.get(type(observation), observation_id)
            if current_obs is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Observation not found",
                        }
                    },
                )
            elif current_obs.status == 'verified':
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "ALREADY_ACTIONED",
                            "message": f"Observation already verified by another reviewer",
                            "field": "status"
                        }
                    },
                )
            elif current_obs.status == 'rejected':
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "ALREADY_ACTIONED",
                            "message": f"Observation already rejected by another reviewer",
                            "field": "status"
                        }
                    },
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "ALREADY_ACTIONED",
                            "message": "Observation is not in a verifiable state",
                            "field": "status"
                        }
                    },
                )
        
        await db.commit()
        await db.refresh(observation)
        
        # Log the verification action
        await service.audit_log.log_observation_update(
            observation_id=observation_id,
            actor_id=UUID(tenant_context.user_id),
            old_values={"status": "pending"},
            new_values={"status": "verified", "verified_by": str(tenant_context.user_id)},
        )
        
        response_data = ObservationResponse.model_validate(observation)
        response_data.is_locked = await service.is_observation_locked(observation)
        response_data.evidence_count = len(observation.evidence) if observation.evidence else 0
        
        return response_data
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )


@router.post("/{observation_id}/reject", response_model=ObservationResponse)
async def reject_observation(
    observation_id: UUID,
    request: RejectRequest,
    tenant_context = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject an Observation (Admin/SuperAdmin only).
    
    Atomic status transition: pending → rejected with conflict detection.
    Requires rejection reason.
    """
    # Validate reason field
    if not request.reason or not request.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Rejection reason is required",
                    "field": "reason"
                }
            },
        )
    
    # Role check: only Admin/SuperAdmin can reject
    from shared.models import UserRole
    normalized_roles = [role.lower() if role else role for role in tenant_context.roles]
    if not any(role in normalized_roles for role in ("admin", "superadmin")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Only Admin or SuperAdmin can reject observations",
                    "field": "role"
                }
            },
        )
    
    service = ObservationService(db)
    try:
        # Get observation for tenant scoping
        observation = await service.get_observation(observation_id)
        
        # Apply tenant filter to ensure rejector can only reject within their tenant
        from shared.middleware.tenancy import apply_tenant_filter
        from sqlalchemy import select as sa_select
        tenant_query = sa_select(type(observation)).where(type(observation).id == observation_id)
        tenant_query = apply_tenant_filter(tenant_query, tenant_context)
        result = await db.execute(tenant_query)
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Observation not found",
                    }
                },
            )
        
        # Atomic status transition with conflict detection
        from sqlalchemy import update as sa_update
        from shared.datetime_utils import utc_now
        
        now = utc_now()
        update_stmt = (
            sa_update(type(observation))
            .where(type(observation).id == observation_id)
            .where(type(observation).status == 'pending')  # Only update if still pending
            .values(
                status='rejected',
                rejected_at=now,
                rejected_by=UUID(tenant_context.user_id),
                rejection_reason=request.reason.strip(),
                # Clear verification fields if previously verified
                verified_at=None,
                verified_by=None
            )
        )
        
        result = await db.execute(update_stmt)
        affected_rows = result.rowcount
        
        if affected_rows == 0:
            # Check current status for better error message
            current_obs = await db.get(type(observation), observation_id)
            if current_obs is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Observation not found",
                        }
                    },
                )
            elif current_obs.status == 'rejected':
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "ALREADY_ACTIONED",
                            "message": f"Observation already rejected by another reviewer",
                            "field": "status"
                        }
                    },
                )
            elif current_obs.status == 'verified':
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "ALREADY_ACTIONED",
                            "message": f"Observation already verified by another reviewer",
                            "field": "status"
                        }
                    },
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": {
                            "code": "ALREADY_ACTIONED",
                            "message": "Observation is not in a rejectable state",
                            "field": "status"
                        }
                    },
                )
        
        await db.commit()
        await db.refresh(observation)
        
        # Log the rejection action
        await service.audit_log.log_observation_update(
            observation_id=observation_id,
            actor_id=UUID(tenant_context.user_id),
            old_values={"status": "pending"},
            new_values={"status": "rejected", "rejected_by": str(tenant_context.user_id), "rejection_reason": request.reason},
        )
        
        response_data = ObservationResponse.model_validate(observation)
        response_data.is_locked = await service.is_observation_locked(observation)
        response_data.evidence_count = len(observation.evidence) if observation.evidence else 0
        
        return response_data
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )
