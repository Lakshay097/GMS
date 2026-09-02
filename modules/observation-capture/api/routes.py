"""
Observation Capture API routes — PRS §24.
Implements Checker-only Observation capture endpoints with idempotency support.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status, Query, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from shared.utils import get_client_ip

from pydantic import BaseModel
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
from shared.middleware.permissions import PermissionChecker, Module, Action
from shared.middleware.tenancy import require_tenant_context, TenantContext
from shared.datetime_utils import utc_now

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
    # Matrix-driven permission check per R-48: Checkers capture Observations only (R-22/BR-11)
    await PermissionChecker.require_permission(Module.OBSERVATION, Action.CREATE, tenant_context, db)
    
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
    
    # Validate check/reason constraints
    if request.capture_type == 'check' and request.check_result == 'No':
        if not request.reason or not request.reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "VALIDATION_ERROR", "message": "Reason is required when Capture Type is No."}},
            )
    
    service = ObservationService(db)
    
    # Resolve checker_id and department_id from authenticated tenant context.
    # The client-supplied values are ignored for security — the server is the
    # source of truth for identity and authorization.
    checker_id = UUID(tenant_context.user_id)
    department_id = (
        UUID(tenant_context.department_id)
        if tenant_context.department_id
        else request.department_id
    )
    school_id = (
        UUID(tenant_context.school_id)
        if tenant_context.school_id
        else request.school_id
    )
    
    if not department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Department is required for observation submission."}},
        )
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "School is required for observation submission."}},
        )
    
    try:
        observation = await service.submit_observation(
            kpi_id=request.kpi_id,
            kpi_version=request.kpi_version,
            checker_id=checker_id,
            department_id=department_id,
            school_id=school_id,
            value_numeric=request.value_numeric,
            value_text=request.value_text,
            asset_id=request.asset_id,
            location_id=request.location_id,
            event_times=[et.model_dump() for et in request.event_times],
            evidence=[ev.model_dump() for ev in request.evidence],
            submission_date=request.submission_date,
            is_late=request.is_late,
            submission_token=request.submission_token,
            override_duplicate=request.override_duplicate,
            override_justification=request.override_justification,
            check_result=request.check_result,
            reason=request.reason,
            actor_id=checker_id,
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
        kpi_details: dict = {}  # kpi_id -> {target_value, unit_of_measure, comparator}
        observer_names: dict = {}
        school_names: dict = {}
        dept_names: dict = {}

        if kpi_ids:
            try:
                kpi_q = await db.execute(
                    sa_select(KPI.kpi_id, KPI.title, KPI.target_value, KPI.unit_of_measure, KPI.comparator).where(KPI.kpi_id.in_(kpi_ids))
                )
                for row in kpi_q.all():
                    kpi_titles[row[0]] = row[1]
                    kpi_details[row[0]] = {
                        "target_value": str(row[2]) if row[2] is not None else None,
                        "unit_of_measure": row[3],
                        "comparator": row[4],
                    }
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
                # Populate KPI detail fields for verification view
                kpi_info = kpi_details.get(obs.kpi_id, {})
                response_data.kpi_target_value = kpi_info.get("target_value")
                response_data.kpi_unit = kpi_info.get("unit_of_measure")
                response_data.kpi_comparator = kpi_info.get("comparator")
                response_list.append(response_data)
            except Exception:
                continue

        return response_list
    except Exception as e:
        # Return empty list instead of 500 error if table doesn't exist or other issues
        print(f"Error listing observations: {e}")
        return []


@router.get("/submissions-by-date", response_model=list[dict])
async def get_submissions_by_date(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    tenant_context = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Get submitted KPI entries for this user.

    Returns ALL submissions for the last 400 days so the frontend can compute
    frequency-based periods (daily, weekly, monthly, quarterly, annual, etc.).
    The `date` parameter is kept for backwards compatibility but the query now
    returns a wider window.
    """
    from sqlalchemy import select as sa_select
    from shared.platform_models import Observation
    from datetime import timedelta, datetime as _dt
    from shared.datetime_utils import utc_now

    try:
        _dt.fromisoformat(date)  # validate format
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Return submissions for the last 400 days so the frontend can compute
    # period-based submission status for any frequency (daily → annual).
    checker_id = UUID(tenant_context.user_id)
    since = utc_now() - timedelta(days=400)
    query = sa_select(Observation).where(
        Observation.checker_id == checker_id,
        Observation.submitted_at >= since,
    ).order_by(Observation.submitted_at.desc())

    result = await db.execute(query)
    observations = result.scalars().all()

    submissions = []
    for obs in observations:
        submissions.append({
            "observation_id": str(obs.id),
            "kpi_id": str(obs.kpi_id),
            "checker_id": str(obs.checker_id),
            "captured_at": obs.captured_at.isoformat() if obs.captured_at else None,
            "submitted_at": obs.submitted_at.isoformat() if obs.submitted_at else None,
            "check_result": obs.check_result,
            "value_numeric": str(obs.value_numeric) if obs.value_numeric is not None else None,
            "value_text": obs.value_text,
            "status": obs.status,
            "edit_count": obs.edit_count or 0,
            "reason": obs.reason,
        })

    return submissions


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
    from shared.middleware.permissions import PermissionChecker
    from shared.permissions import Module, Action
    await PermissionChecker.require_permission(
        Module.REOPEN_REQUEST, Action.REQUEST, tenant_context, db
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
    from shared.middleware.permissions import PermissionChecker
    from shared.permissions import Module, Action
    await PermissionChecker.require_permission(
        Module.REOPEN_REQUEST, Action.APPROVE, tenant_context, db
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


class ObservationEditRequest(BaseModel):
    """Request body for editing an existing observation."""
    value_numeric: Optional[float] = None
    value_text: Optional[str] = None
    check_result: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


@router.patch("/{observation_id}", response_model=ObservationResponse)
async def update_observation(
    observation_id: UUID,
    body: ObservationEditRequest = None,
    tenant_context = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Update an Observation (RESTRICTED).

    R-24/BR-12/C5: Auditors never edit Observations — they may only Verify or raise a Discrepancy.
    Access is enforced via the permission matrix (OBSERVATION.UPDATE), which denies
    Auditor and Viewer roles.

    30-minute edit window:
    - Submitter can edit within 30 minutes of captured_at.
    - After 30 minutes, only Admin, SuperAdmin, or DeptHead can edit.
    - All changes are logged in the append-only audit trail.
    """
    # Matrix-driven permission check per R-48
    await PermissionChecker.require_permission(Module.OBSERVATION, Action.UPDATE, tenant_context, db)

    # Default body values (support both query-param and JSON body)
    value_numeric = body.value_numeric if body else None
    value_text = body.value_text if body else None
    check_result = body.check_result if body else None
    reason = body.reason if body else None

    service = ObservationService(db)
    try:
        observation = await service.get_observation(observation_id)

        # 30-minute edit window enforcement
        actor_id = UUID(tenant_context.user_id)
        is_submitter = str(observation.checker_id) == str(actor_id)
        admin_roles = {"admin", "superadmin", "dept_head"}
        actor_has_admin_role = any(
            r.lower() in admin_roles for r in (tenant_context.roles or [])
        )

        within_edit_window = False
        if observation.captured_at:
            elapsed = utc_now() - observation.captured_at
            within_edit_window = elapsed.total_seconds() < 1800  # 30 minutes

        # Submitter can only edit within 30 minutes
        if is_submitter and not within_edit_window and not actor_has_admin_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "EDIT_WINDOW_EXPIRED",
                        "message": (
                            "30-minute edit window has expired. "
                            "Only Admin, SuperAdmin, or DeptHead can modify this entry."
                        ),
                    }
                },
            )

        # Capture old values for audit logging
        old_values: dict[str, str | None] = {}
        new_values: dict[str, str | None] = {}

        if value_numeric is not None:
            old_values["value_numeric"] = (
                str(observation.value_numeric) if observation.value_numeric is not None else None
            )
            observation.value_numeric = value_numeric
            new_values["value_numeric"] = str(value_numeric)

        if value_text is not None:
            old_values["value_text"] = observation.value_text
            observation.value_text = value_text
            new_values["value_text"] = value_text

        if check_result is not None:
            old_values["check_result"] = observation.check_result
            observation.check_result = check_result
            new_values["check_result"] = check_result

        if reason is not None:
            # Validate: reason is required when check_result is No
            effective_check = check_result or observation.check_result
            if effective_check == "No" and (not reason or not reason.strip()):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Reason is required when Capture Type is No.",
                        }
                    },
                )
            old_values["reason"] = observation.reason
            observation.reason = reason
            new_values["reason"] = reason

        if not old_values:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "NO_CHANGES", "message": "No fields to update."}},
            )

        # Log the update with authenticated actor
        from platform_services.audit_log_service.service import AuditLogService
        audit_log = AuditLogService(db)
        await audit_log.log_observation_update(
            observation_id=observation_id,
            actor_id=actor_id,
            old_values=old_values if old_values else None,
            new_values=new_values if new_values else None,
        )

        # Write detailed append-only audit trail records
        from shared.platform_models import ObservationAudit
        for field_name, old_val in old_values.items():
            new_val = new_values.get(field_name)
            if old_val != new_val:
                if is_submitter and within_edit_window:
                    change_type = "submitter_correction"
                elif actor_has_admin_role and "dept_head" in [r.lower() for r in (tenant_context.roles or [])]:
                    change_type = "dept_head_change"
                elif actor_has_admin_role:
                    change_type = "admin_change"
                else:
                    change_type = "unknown_change"

                audit_record = ObservationAudit(
                    observation_id=observation_id,
                    actor_id=actor_id,
                    actor_role=(tenant_context.roles[0] if tenant_context.roles else "unknown"),
                    field_name=field_name,
                    old_value=old_val,
                    new_value=new_val,
                    change_type=change_type,
                    is_within_edit_window=within_edit_window,
                )
                db.add(audit_record)

        # Update edit tracking
        observation.edited_at = utc_now()
        observation.edited_by = actor_id
        observation.edit_count = (observation.edit_count or 0) + 1

        await db.commit()
        await db.refresh(observation)

        response_data = ObservationResponse.model_validate(observation)
        response_data.is_locked = await service.is_observation_locked(observation)
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
    from shared.middleware.permissions import PermissionChecker
    from shared.permissions import Module, Action
    await PermissionChecker.require_permission(
        Module.AUDIT, Action.VERIFY, tenant_context, db
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
    from shared.middleware.permissions import PermissionChecker
    from shared.permissions import Module, Action
    await PermissionChecker.require_permission(
        Module.OBSERVATION, Action.UPDATE, tenant_context, db
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


@router.get("/{observation_id}/audit-history", response_model=list[dict])
async def get_audit_history(
    observation_id: UUID,
    tenant_context = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the audit history for an Observation.
    Returns append-only audit records showing all modifications.
    """
    from sqlalchemy import select as sa_select
    from shared.platform_models import ObservationAudit

    query = sa_select(ObservationAudit).where(
        ObservationAudit.observation_id == observation_id
    ).order_by(ObservationAudit.created_at.asc())

    result = await db.execute(query)
    records = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "observation_id": str(r.observation_id),
            "actor_id": str(r.actor_id),
            "actor_email": r.actor_email,
            "actor_role": r.actor_role,
            "field_name": r.field_name,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "change_type": r.change_type,
            "reason": r.reason,
            "is_within_edit_window": r.is_within_edit_window,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
