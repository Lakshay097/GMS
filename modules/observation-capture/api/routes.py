"""
Observation Capture API routes — PRS §24.
Implements Checker-only Observation capture endpoints with idempotency support.
"""
from typing import Optional
from uuid import UUID
from datetime import timedelta, date

from fastapi import APIRouter, Depends, Header, HTTPException, status, Query, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from shared.utils import get_client_ip

from pydantic import BaseModel
from modules.observation_capture.schemas import (
    KpiRecordEntry,
    KpiRecordRow,
    ObservationResponse,
    ObservationSubmitRequest,
    ReopenApprovalRequest,
    ReopenRequest,
    VerifyRequest,
    RejectRequest,
)
from modules.observation_capture.services.observation_service import ObservationService
from platform_services.configuration_engine.constants import ConfigKey
from shared.datetime_utils import utc_now
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
    request: Request,
    body: ObservationSubmitRequest,
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
    if body.capture_type == 'check' and body.check_result == 'No':
        if not body.reason or not body.reason.strip():
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
        else body.department_id
    )
    school_id = (
        UUID(tenant_context.school_id)
        if tenant_context.school_id
        else body.school_id
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
            kpi_id=body.kpi_id,
            kpi_version=body.kpi_version,
            checker_id=checker_id,
            department_id=department_id,
            school_id=school_id,
            value_numeric=body.value_numeric,
            value_text=body.value_text,
            asset_id=body.asset_id,
            location_id=body.location_id,
            event_times=[et.model_dump() for et in body.event_times],
            evidence=[ev.model_dump() for ev in body.evidence],
            submission_date=body.submission_date,
            is_late=body.is_late,
            submission_token=body.submission_token,
            override_duplicate=body.override_duplicate,
            override_justification=body.override_justification,
            check_result=body.check_result,
            reason=body.reason,
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
    date_from: Optional[date] = Query(None, description="Filter: submitted on/after this date (inclusive, UTC)"),
    date_to: Optional[date] = Query(None, description="Filter: submitted on/before this date (inclusive, UTC)"),
    kra_id: Optional[UUID] = Query(None, description="Filter: observations whose KPI belongs to this KRA"),
    db: AsyncSession = Depends(get_db),
):
    """List observations with tenant isolation, pagination, and enriched display fields (per R-02).

    Scope is role-aware (R-02 / PRS §12):
    - SuperAdmin: all schools
    - Admin / Dept Head: their school (+ department for Dept Head / assigned users)
    - Checker: observations whose KPI is assigned to their department
      (department_kpi_assignments, FR-055) — i.e. the KRAs/KPIs they are
      responsible for capturing.
    """
    try:
        from sqlalchemy import select as sa_select, func
        from shared.platform_models import Observation, KPI, DepartmentKpiAssignment
        from shared.models import School, Department
        from shared.middleware.tenancy import apply_tenant_filter
        from shared.models import User

        roles = [r.lower() if isinstance(r, str) else r for r in (tenant_context.roles or [])]
        is_checker = "checker" in roles and not any(r in ("superadmin", "admin", "dept_head", "viewer") for r in roles)

        # ── Checker scope: only KPIs assigned to their department ──────────
        if is_checker and tenant_context.department_id:
            assigned_q = sa_select(DepartmentKpiAssignment.kpi_id).where(
                DepartmentKpiAssignment.department_id == UUID(tenant_context.department_id)
            )
            assigned_res = await db.execute(assigned_q)
            assigned_kpi_ids = [row[0] for row in assigned_res.all()]
            if not assigned_kpi_ids:
                return []

            # Base query filtered to the department's assigned KPIs.
            # (No join needed — the observation's kpi_id membership in the
            # assigned set is the whole constraint; KPI titles are enriched
            # separately below.)
            query = sa_select(Observation).where(
                Observation.kpi_id.in_(assigned_kpi_ids)
            ).order_by(Observation.submitted_at.desc())
            # Tenant isolation still applies on top (school/department row filter).
            query = apply_tenant_filter(query, tenant_context)
        else:
            # Build base query with tenant isolation, ordered by most recent
            query = sa_select(Observation).order_by(Observation.submitted_at.desc())
            query = apply_tenant_filter(query, tenant_context)

        # ── Optional date-range filter (inclusive, UTC) ────────────────────
        if date_from is not None:
            query = query.where(Observation.submitted_at >= date_from)
        if date_to is not None:
            # Include the whole of date_to: submitted_at < date_to + 1 day
            query = query.where(Observation.submitted_at < date_to + timedelta(days=1))

        # ── Optional KRA filter (via KPI → KRA) ────────────────────────────
        if kra_id is not None:
            kra_kpi_q = sa_select(KPI.kpi_id).where(KPI.kra_id == kra_id)
            kra_kpi_res = await db.execute(kra_kpi_q)
            kra_kpi_ids = [row[0] for row in kra_kpi_res.all()]
            if not kra_kpi_ids:
                return []
            query = query.where(Observation.kpi_id.in_(kra_kpi_ids))

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
                # Lock state without per-row config round trips: resolve once,
                # compare per row (same rule as is_observation_locked / R-16).
                lock_period_minutes = await service.config_engine.get(
                    ConfigKey.OBSERVATION_LOCK_PERIOD_MINUTES,
                    school_id=obs.school_id,
                )
                is_locked = obs.locked_at is not None or (
                    obs.submitted_at is not None
                    and utc_now() >= obs.submitted_at + timedelta(minutes=lock_period_minutes)
                )
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


@router.get("/kpi-records", response_model=list[KpiRecordRow])
async def list_kpi_records(
    date_from: Optional[date] = Query(None, description="First date to show (YYYY-MM-DD, UTC). Defaults to today."),
    date_to: Optional[date] = Query(None, description="Last date to show (YYYY-MM-DD, UTC, inclusive). Defaults to today."),
    kra_id: Optional[UUID] = Query(None, description="Narrow to KPIs under this KRA"),
    department_id: Optional[UUID] = Query(None, description="Narrow to KPIs assigned to this department"),
    kpi_id: Optional[UUID] = Query(None, description="Narrow to a single KPI"),
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Complete KPI × date matrix for the requester's scope — blanks included.

    Returns one row per KPI visible to the user with the observation entry for
    each requested date (or the period-based entry covering that date for
    weekly/monthly/quarterly/annual KPIs). A KPI with no value on a date is
    still returned — the cell is simply absent from ``entries`` — so the UI
    never silently drops un-entered KPIs.

    Scope (R-02, reusing the same rules as list_observations):
    - SuperAdmin: all KPIs
    - Admin/Viewer: KPIs assigned to departments within their school
      (department-scoped users see only their department)
    - Checker/Dept Head: KPIs assigned to their department
    All filter parameters only ever narrow this set; a filter naming a
    department outside the requester's scope yields an empty result, never
    cross-tenant data.
    """
    from sqlalchemy import select as sa_select
    from shared.platform_models import Observation, KPI, KRA, DepartmentKpiAssignment
    from shared.models import Department
    from shared.middleware.tenancy import apply_tenant_filter

    MAX_RANGE_DAYS = 62
    roles = [r.lower() if isinstance(r, str) else r for r in (tenant_context.roles or [])]
    is_superadmin = "superadmin" in roles
    is_pure_dept_role = "checker" in roles or "dept_head" in roles
    has_broad_role = any(r in ("superadmin", "admin", "viewer") for r in roles)

    # ── Resolve the requested dates (default: today only) ─────────────────
    today = utc_now().date()
    start = date_from or date_to or today
    end = date_to or date_from or today
    if end < start:
        raise HTTPException(status_code=400, detail="date_to must be on or after date_from.")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Date range cannot exceed {MAX_RANGE_DAYS} days.")

    # ── Departments the requester may see ─────────────────────────────────
    # None means "all departments" (superadmin only).
    allowed_dept_ids: Optional[set] = None
    if not is_superadmin:
        dept_q = sa_select(Department.id)
        if tenant_context.school_id:
            dept_q = dept_q.where(Department.school_id == UUID(tenant_context.school_id))
        elif tenant_context.accessible_school_ids:
            school_uuids = [UUID(s) if isinstance(s, str) else s for s in tenant_context.accessible_school_ids]
            dept_q = dept_q.where(Department.school_id.in_(school_uuids))
        else:
            return []  # no school scope → no visible departments → no rows
        if tenant_context.department_id and not has_broad_role:
            dept_q = dept_q.where(Department.id == UUID(tenant_context.department_id))
        dept_res = await db.execute(dept_q)
        allowed_dept_ids = {row[0] for row in dept_res.all()}
        if not allowed_dept_ids:
            return []

    # A department filter outside the requester's scope narrows to nothing.
    if department_id is not None:
        if allowed_dept_ids is not None and department_id not in allowed_dept_ids:
            return []
        effective_dept_ids = {department_id}
    else:
        effective_dept_ids = allowed_dept_ids  # None (superadmin) or the visible set

    # ── KPIs visible via department assignments ───────────────────────────
    assign_q = sa_select(DepartmentKpiAssignment.department_id, DepartmentKpiAssignment.kpi_id)
    if effective_dept_ids is not None:
        if not effective_dept_ids:
            return []
        assign_q = assign_q.where(DepartmentKpiAssignment.department_id.in_(effective_dept_ids))
    assign_res = await db.execute(assign_q)
    assignment_rows = assign_res.all()
    if not assignment_rows:
        return []

    kpi_dept_map: dict = {}  # kpi_id -> set of department_ids it is assigned to
    for dept_id, k in assignment_rows:
        kpi_dept_map.setdefault(k, set()).add(dept_id)
    visible_kpi_ids = set(kpi_dept_map.keys())

    # ── Optional KRA / KPI narrowing (still within the visible set) ───────
    if kra_id is not None:
        kra_kpi_res = await db.execute(sa_select(KPI.kpi_id).where(KPI.kra_id == kra_id))
        kra_kpi_ids = {row[0] for row in kra_kpi_res.all()}
        visible_kpi_ids &= kra_kpi_ids
    if kpi_id is not None:
        visible_kpi_ids &= {kpi_id}
    if not visible_kpi_ids:
        return []

    # ── KPI + KRA display metadata (latest version wins) ──────────────────
    kpi_res = await db.execute(
        sa_select(
            KPI.kpi_id, KPI.version, KPI.title, KPI.target_value, KPI.unit_of_measure,
            KPI.comparator, KPI.frequency_code, KPI.working_days, KPI.kra_id,
        ).where(KPI.kpi_id.in_(visible_kpi_ids)).order_by(KPI.kpi_id, KPI.version.desc())
    )
    kpi_meta: dict = {}
    for row in kpi_res.all():
        if row[0] not in kpi_meta:  # first row per kpi_id is the latest version
            kpi_meta[row[0]] = {
                "version": row[1], "title": row[2], "target_value": row[3],
                "unit": row[4], "comparator": row[5], "freq": (row[6] or "daily").lower(),
                "working_days": row[7], "kra_id": row[8],
            }
    kra_ids = {m["kra_id"] for m in kpi_meta.values() if m["kra_id"]}
    kra_names: dict = {}
    if kra_ids:
        kra_res = await db.execute(sa_select(KRA.id, KRA.name).where(KRA.id.in_(kra_ids)))
        kra_names = {row[0]: row[1] for row in kra_res.all()}

    dept_ids_for_names = set().union(*kpi_dept_map.values()) if kpi_dept_map else set()
    dept_names: dict = {}
    if dept_ids_for_names:
        dn_res = await db.execute(sa_select(Department.id, Department.name).where(Department.id.in_(dept_ids_for_names)))
        dept_names = {row[0]: row[1] for row in dn_res.all()}

    # ── Observation window widened to whole periods (weekly/monthly KPIs ──
    #    entered on any day of the period still cover the requested dates).
    def _period_bounds(d: date, freq: str) -> tuple:
        if freq == "weekly":
            s = d - timedelta(days=d.weekday())
            return s, s + timedelta(days=6)
        if freq == "monthly":
            s = d.replace(day=1)
            e = (s + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            return s, e
        if freq == "quarterly":
            s = date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)
            e = (s + timedelta(days=92)).replace(day=1) - timedelta(days=1)
            return s, e
        if freq in ("annual", "yearly"):
            return date(d.year, 1, 1), date(d.year, 12, 31)
        return d, d  # daily and anything unrecognised

    freqs = {m["freq"] for m in kpi_meta.values()}
    # Take the widest period bounds across all present frequencies so a
    # monthly KPI entered mid-month still covers a requested day-1 date.
    window_start = min(_period_bounds(start, f)[0] for f in freqs) if freqs else start
    window_end = max(_period_bounds(end, f)[1] for f in freqs) if freqs else end

    obs_q = (
        sa_select(Observation)
        .where(
            Observation.kpi_id.in_(visible_kpi_ids),
            Observation.submitted_at.isnot(None),
            Observation.submitted_at >= window_start,
            Observation.submitted_at < window_end + timedelta(days=1),
        )
        .order_by(Observation.submitted_at.asc())
    )
    obs_q = apply_tenant_filter(obs_q, tenant_context)
    if department_id is not None:
        obs_q = obs_q.where(Observation.department_id == department_id)
    obs_res = await db.execute(obs_q)
    observations = obs_res.scalars().all()

    # ── Bucket observations: (kpi_id, date_key) -> latest entry ───────────
    # An observation covers requested date D when its own period contains D.
    buckets: dict = {}  # (kpi_id, iso_date) -> Observation (latest wins)
    for obs in observations:
        obs_date = obs.submitted_at.date()
        freq = (kpi_meta.get(obs.kpi_id, {}).get("freq")) or "daily"
        p_start, p_end = _period_bounds(obs_date, freq)
        for d in (start + timedelta(days=i) for i in range((end - start).days + 1)):
            if p_start <= d <= p_end:
                buckets[(obs.kpi_id, d.isoformat())] = obs  # ascending order → later overwrites earlier

    # ── Assemble rows — every visible KPI appears, blanks included ────────
    rows: list = []
    for k in sorted(visible_kpi_ids, key=lambda k: kpi_meta.get(k, {}).get("title", "").lower()):
        meta = kpi_meta.get(k)
        if not meta:
            continue
        assigned_depts = kpi_dept_map.get(k, set())
        dept_label = ", ".join(
            sorted(dept_names.get(d, str(d)[:8]) for d in assigned_depts)
        )
        entries: dict = {}
        for i in range((end - start).days + 1):
            d = (start + timedelta(days=i)).isoformat()
            obs = buckets.get((k, d))
            if obs is not None:
                entries[d] = KpiRecordEntry(
                    observation_id=obs.id,
                    status=obs.status,
                    value_numeric=obs.value_numeric,
                    value_text=obs.value_text,
                    check_result=obs.check_result,
                    reason=obs.reason,
                    submitted_at=obs.submitted_at,
                )
        rows.append(KpiRecordRow(
            kpi_id=k,
            kpi_title=meta["title"],
            kpi_version=meta["version"],
            kra_id=meta["kra_id"],
            kra_name=kra_names.get(meta["kra_id"]),
            department_id=(next(iter(assigned_depts)) if len(assigned_depts) == 1 else None),
            department_name=dept_label or None,
            target_value=meta["target_value"],
            unit_of_measure=meta["unit"],
            comparator=meta["comparator"],
            frequency_code=meta["freq"],
            entries=entries,
        ))
    return rows


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
