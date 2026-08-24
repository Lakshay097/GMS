"""
API routes for Dashboards (PRS §30-31), Report Catalogue (PRS §50),
Global Search (PRS §33/§51), and Export Pipeline (R-59/BR-17).

Prefixes
--------
GET  /dashboard                         Role-based dashboard
GET  /reports                           Report catalogue
GET  /reports/{report_type}             Run a report (data, paginated)
POST /reports/export                    Enqueue export job (Excel/CSV/PDF/API)
GET  /reports/export/{job_id}           Poll export job status
GET  /reports/export/{job_id}/download  Download the exported file
GET  /reports/category-restrictions     List category export restrictions
POST /reports/category-restrictions     Create restriction (SuperAdmin/Admin only)
DELETE /reports/category-restrictions/{id}   Remove restriction

GET  /search                            Global cross-entity search
POST /search/saved-filters              Create saved filter
GET  /search/saved-filters              List own saved filters
PATCH /search/saved-filters/{id}        Update saved filter
DELETE /search/saved-filters/{id}       Delete saved filter
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from modules.dashboards_reports_search.schemas import (
    CategoryRestrictionCreate,
    CategoryRestrictionResponse,
    ExportJobResponse,
    ExportRequest,
    ReportCatalogueResponse,
    ReportFilter,
    ReportResponse,
    SavedFilterCreate,
    SavedFilterResponse,
    SavedFilterUpdate,
    SearchRequest,
    SearchResponse,
)
from modules.dashboards_reports_search.schemas import DashboardResponse
from modules.dashboards_reports_search.services.dashboard_service import DashboardService
from modules.dashboards_reports_search.services.export_service import (
    ExportService,
    get_export_file,
)
from modules.dashboards_reports_search.services.report_service import (
    REPORT_CATALOGUE,
    ReportService,
)
from modules.dashboards_reports_search.services.search_service import SearchService
from shared.database import get_db, get_read_db
from shared.errors import AuthorizationError, NotFoundError, ValidationError
from shared.middleware.permissions import PermissionChecker
from shared.middleware.tenancy import TenantContext, require_tenant_context
from shared.permissions import Action, Module

router = APIRouter(tags=["dashboards-reports-search"])

# ── DI helpers ─────────────────────────────────────────────────────────────────

def _dashboard_svc(db: AsyncSession = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


def _report_svc(db: AsyncSession = Depends(get_read_db)) -> ReportService:
    return ReportService(db)


def _search_svc(db: AsyncSession = Depends(get_db)) -> SearchService:
    return SearchService(db)


def _export_svc(
    read_db: AsyncSession = Depends(get_read_db),
    write_db: AsyncSession = Depends(get_db),
) -> ExportService:
    return ExportService(read_db, write_db)


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Role-based dashboard (PRS §30-31)",
)
async def get_dashboard(
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    svc: DashboardService = Depends(_dashboard_svc),
) -> DashboardResponse:
    print(f"get_dashboard called - tenant: {tenant.user_id}, roles: {tenant.roles}, school_id: {tenant.school_id}")
    try:
        await PermissionChecker.require_permission(Module.DASHBOARD, Action.VIEW, tenant, db)
        result = await svc.get_dashboard(tenant)
        print(f"get_dashboard success for user {tenant.user_id}")
        return result
    except Exception as e:
        print(f"Error in get_dashboard: {e}")
        import traceback
        traceback.print_exc()
        raise


# ── Report Catalogue ───────────────────────────────────────────────────────────

@router.get(
    "/reports",
    response_model=ReportCatalogueResponse,
    summary="List available reports (PRS §50)",
)
async def list_reports(
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ReportCatalogueResponse:
    await PermissionChecker.require_permission(Module.REPORT, Action.READ, tenant, db)
    lower_roles = [r.lower() for r in tenant.roles]
    accessible = [
        r for r in REPORT_CATALOGUE
        if any(role in r["required_roles"] for role in lower_roles)
    ]
    return ReportCatalogueResponse(reports=accessible)  # type: ignore[arg-type]


@router.get(
    "/reports/{report_type}",
    response_model=ReportResponse,
    summary="Run a report and return paginated data (PRS §50)",
)
async def run_report(
    report_type: str,
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    school_id: Optional[UUID] = Query(None),
    department_id: Optional[UUID] = Query(None),
    kpi_id: Optional[UUID] = Query(None),
    user_id: Optional[UUID] = Query(None),
    category_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    svc: ReportService = Depends(_report_svc),
) -> ReportResponse:
    await PermissionChecker.require_permission(Module.REPORT, Action.READ, tenant, db)
    from datetime import date as date_type
    flt = ReportFilter(
        date_from=date_type.fromisoformat(date_from) if date_from else None,
        date_to=date_type.fromisoformat(date_to) if date_to else None,
        school_id=school_id,
        department_id=department_id,
        kpi_id=kpi_id,
        user_id=user_id,
        category_code=category_code,
        status=status,
        page=page,
        page_size=page_size,
    )
    return await svc.run(report_type, flt, tenant)


# ── Export ─────────────────────────────────────────────────────────────────────

@router.post(
    "/reports/export",
    response_model=ExportJobResponse,
    summary="Enqueue a report export job (R-59/BR-17)",
    status_code=202,
)
async def create_export(
    body: ExportRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    svc: ExportService = Depends(_export_svc),
) -> ExportJobResponse:
    await PermissionChecker.require_permission(Module.REPORT, Action.EXPORT, tenant, db)
    return await svc.enqueue_and_run(body, tenant)


@router.get(
    "/reports/export/{job_id}",
    response_model=ExportJobResponse,
    summary="Poll export job status",
)
async def get_export_job(
    job_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ExportService = Depends(_export_svc),
) -> ExportJobResponse:
    return await svc.get_job(job_id, tenant)


@router.get(
    "/reports/export/{job_id}/download",
    summary="Download the rendered export file",
)
async def download_export(
    job_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: ExportService = Depends(_export_svc),
) -> StreamingResponse:
    job = await svc.get_job(job_id, tenant)
    if job.status != "completed":
        raise ValidationError(f"Export job is {job.status}, not yet available for download")
    cached = get_export_file(str(job_id))
    if not cached:
        raise NotFoundError("ExportFile")
    fmt, data = cached
    media_types = {
        "csv": "text/csv",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
        "api": "application/json",
    }
    ext = {"csv": "csv", "excel": "xlsx", "pdf": "pdf", "api": "json"}.get(fmt, "bin")
    return StreamingResponse(
        iter([data]),
        media_type=media_types.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{job.report_type}.{ext}"'},
    )


# ── Category export restrictions (BR-04/BR-19/R-50) ──────────────────────────

@router.get(
    "/reports/category-restrictions",
    response_model=List[CategoryRestrictionResponse],
    summary="List KPI category export restrictions",
)
async def list_category_restrictions(
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> List[CategoryRestrictionResponse]:
    await PermissionChecker.require_permission(Module.REPORT, Action.READ, tenant, db)
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT id, category_code, restricted_role, restrict_export, restrict_view, created_at FROM kpi_category_export_restrictions ORDER BY category_code")
    )
    return [
        CategoryRestrictionResponse(
            id=r.id, category_code=r.category_code, restricted_role=r.restricted_role,
            restrict_export=r.restrict_export, restrict_view=r.restrict_view,
            created_at=r.created_at,
        )
        for r in result.fetchall()
    ]


@router.post(
    "/reports/category-restrictions",
    response_model=CategoryRestrictionResponse,
    status_code=201,
    summary="Create a KPI category export restriction (SuperAdmin/Admin)",
)
async def create_category_restriction(
    body: CategoryRestrictionCreate,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> CategoryRestrictionResponse:
    lower_roles = [r.lower() for r in tenant.roles]
    if not any(r in lower_roles for r in ("superadmin", "admin")):
        raise AuthorizationError("Only SuperAdmin or Admin can configure category restrictions")
    from sqlalchemy import text
    import uuid
    from datetime import datetime, timezone
    new_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            """
            INSERT INTO kpi_category_export_restrictions
                (id, category_code, restricted_role, restrict_export, restrict_view, created_by, created_at, updated_at)
            VALUES (:id, :cc, :role, :re, :rv, :user, :now, :now)
            ON CONFLICT (category_code, restricted_role) DO UPDATE
            SET restrict_export=EXCLUDED.restrict_export,
                restrict_view=EXCLUDED.restrict_view,
                updated_at=:now
            """
        ),
        {"id": str(new_id), "cc": body.category_code, "role": body.restricted_role,
         "re": body.restrict_export, "rv": body.restrict_view,
         "user": tenant.user_id, "now": now},
    )
    await db.commit()
    return CategoryRestrictionResponse(
        id=new_id, category_code=body.category_code, restricted_role=body.restricted_role,
        restrict_export=body.restrict_export, restrict_view=body.restrict_view,
        created_at=now,
    )


@router.delete(
    "/reports/category-restrictions/{restriction_id}",
    status_code=204,
    summary="Remove a KPI category export restriction (SuperAdmin/Admin)",
)
async def delete_category_restriction(
    restriction_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    lower_roles = [r.lower() for r in tenant.roles]
    if not any(r in lower_roles for r in ("superadmin", "admin")):
        raise AuthorizationError("Only SuperAdmin or Admin can remove category restrictions")
    from sqlalchemy import text
    result = await db.execute(
        text("DELETE FROM kpi_category_export_restrictions WHERE id = :id RETURNING id"),
        {"id": str(restriction_id)},
    )
    if not result.fetchone():
        raise NotFoundError("CategoryRestriction")
    await db.commit()


# ── Global Search ──────────────────────────────────────────────────────────────

@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Global cross-entity search (PRS §51/R-60) — permission-scoped",
)
async def global_search(
    q: str = Query(..., min_length=1, max_length=500),
    entity_types: Optional[str] = Query(None, description="Comma-separated list"),
    school_id: Optional[UUID] = Query(None),
    department_id: Optional[UUID] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    svc: SearchService = Depends(_search_svc),
) -> SearchResponse:
    await PermissionChecker.require_permission(Module.SEARCH, Action.READ, tenant, db)
    from datetime import date as date_type
    types_list = [t.strip() for t in entity_types.split(",")] if entity_types else None
    req = SearchRequest(
        q=q,
        entity_types=types_list,
        school_id=school_id,
        department_id=department_id,
        date_from=date_type.fromisoformat(date_from) if date_from else None,
        date_to=date_type.fromisoformat(date_to) if date_to else None,
        page=page,
        page_size=page_size,
    )
    return await svc.search(req, tenant)


# ── Saved Filters ──────────────────────────────────────────────────────────────

@router.post(
    "/search/saved-filters",
    response_model=SavedFilterResponse,
    status_code=201,
    summary="Create a saved search/report filter (private by default)",
)
async def create_saved_filter(
    body: SavedFilterCreate,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    svc: SearchService = Depends(_search_svc),
) -> SavedFilterResponse:
    """
    SECURITY NOTE (M3): This route is gated behind FEATURE_FLAG_SAVED_FILTERS_ENABLED.
    Returns 503 if the feature flag is not set.
    """
    # Feature flag gating (M3 security fix)
    import os
    if not os.getenv("FEATURE_FLAG_SAVED_FILTERS_ENABLED"):
        raise HTTPException(
            status_code=503,
            detail="Saved filters feature not enabled"
        )
    
    await PermissionChecker.require_permission(Module.SEARCH, Action.CREATE, tenant, db)
    return await svc.create_saved_filter(body, tenant)


@router.get(
    "/search/saved-filters",
    response_model=List[SavedFilterResponse],
    summary="List own (and public) saved filters",
)
async def list_saved_filters(
    context: Optional[str] = Query(None),
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    svc: SearchService = Depends(_search_svc),
) -> List[SavedFilterResponse]:
    """
    SECURITY NOTE (M3): This route is gated behind FEATURE_FLAG_SAVED_FILTERS_ENABLED.
    Returns 503 if the feature flag is not set.
    """
    # Feature flag gating (M3 security fix)
    import os
    if not os.getenv("FEATURE_FLAG_SAVED_FILTERS_ENABLED"):
        raise HTTPException(
            status_code=503,
            detail="Saved filters feature not enabled"
        )
    
    await PermissionChecker.require_permission(Module.SEARCH, Action.READ, tenant, db)
    return await svc.list_saved_filters(tenant, context=context)


@router.patch(
    "/search/saved-filters/{filter_id}",
    response_model=SavedFilterResponse,
    summary="Update a saved filter (owner only)",
)
async def update_saved_filter(
    filter_id: UUID,
    body: SavedFilterUpdate,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    svc: SearchService = Depends(_search_svc),
) -> SavedFilterResponse:
    """
    SECURITY NOTE (M3): This route is gated behind FEATURE_FLAG_SAVED_FILTERS_ENABLED.
    Returns 503 if the feature flag is not set.
    """
    # Feature flag gating (M3 security fix)
    import os
    if not os.getenv("FEATURE_FLAG_SAVED_FILTERS_ENABLED"):
        raise HTTPException(
            status_code=503,
            detail="Saved filters feature not enabled"
        )
    
    await PermissionChecker.require_permission(Module.SEARCH, Action.READ, tenant, db)
    return await svc.update_saved_filter(filter_id, body, tenant)


@router.delete(
    "/search/saved-filters/{filter_id}",
    status_code=204,
    summary="Delete a saved filter (owner only)",
)
async def delete_saved_filter(
    filter_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
    svc: SearchService = Depends(_search_svc),
) -> None:
    """
    SECURITY NOTE (M3): This route is gated behind FEATURE_FLAG_SAVED_FILTERS_ENABLED.
    Returns 503 if the feature flag is not set.
    """
    # Feature flag gating (M3 security fix)
    import os
    if not os.getenv("FEATURE_FLAG_SAVED_FILTERS_ENABLED"):
        raise HTTPException(
            status_code=503,
            detail="Saved filters feature not enabled"
        )
    
    await PermissionChecker.require_permission(Module.SEARCH, Action.READ, tenant, db)
    await svc.delete_saved_filter(filter_id, tenant)
