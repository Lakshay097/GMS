"""
API routes for School, Department, KRA, KPI, KPI_Entry CRUD + Dashboard.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.middleware.tenancy import TenantContext, require_tenant_context
from shared.middleware.permissions import PermissionChecker, Module, Action

from ..schemas import (
    SchoolCreateRequest, SchoolUpdateRequest, SchoolResponse,
    DepartmentCreateRequest, DepartmentUpdateRequest, DepartmentResponse,
    KraCreateRequest, KraUpdateRequest, KraResponse,
    KpiCreateRequest, KpiUpdateRequest, KpiResponse,
    KpiEntryCreateRequest, KpiEntryUpdateRequest, KpiEntryResponse,
    DashboardSummary,
)
from ..services.org_service import OrgService


router = APIRouter(tags=["org-management"])


def _get_service(db: AsyncSession = Depends(get_db)) -> OrgService:
    return OrgService(db)


# ── School Routes ─────────────────────────────────────────────────────────

@router.post("/schools", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
async def create_school(
    body: SchoolCreateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    school = await svc.create_school(
        name=body.name,
        code=body.code,
        address=body.address,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        timezone_=body.timezone,
    )
    return SchoolResponse.model_validate(school)


@router.get("/schools", response_model=dict)
async def list_schools(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    schools, total = await svc.list_schools(status=status_filter, page=page, page_size=page_size)
    return {
        "data": [SchoolResponse.model_validate(s) for s in schools],
        "pagination": {"page": page, "page_size": page_size, "total_count": total},
    }


@router.get("/schools/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    school = await svc.get_school(school_id)
    return SchoolResponse.model_validate(school)


@router.patch("/schools/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: UUID,
    body: SchoolUpdateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    school = await svc.update_school(
        school_id,
        name=body.name,
        address=body.address,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        timezone=body.timezone,
    )
    return SchoolResponse.model_validate(school)


@router.post("/schools/{school_id}/deactivate", response_model=SchoolResponse)
async def deactivate_school(
    school_id: UUID,
    confirm: bool = Query(False),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to proceed")
    school = await svc.deactivate_school(school_id)
    return SchoolResponse.model_validate(school)


# ── Department Routes ─────────────────────────────────────────────────────

@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    dept = await svc.create_department(
        name=body.name,
        code=body.code,
        school_id=body.school_id,
        description=body.description,
    )
    return DepartmentResponse.model_validate(dept)


@router.get("/departments", response_model=dict)
async def list_departments(
    school_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    depts, total = await svc.list_departments(
        school_id=school_id, status=status_filter, page=page, page_size=page_size
    )
    return {
        "data": [DepartmentResponse.model_validate(d) for d in depts],
        "pagination": {"page": page, "page_size": page_size, "total_count": total},
    }


@router.get("/departments/{dept_id}", response_model=DepartmentResponse)
async def get_department(
    dept_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    dept = await svc.get_department(dept_id)
    return DepartmentResponse.model_validate(dept)


@router.patch("/departments/{dept_id}", response_model=DepartmentResponse)
async def update_department(
    dept_id: UUID,
    body: DepartmentUpdateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    dept = await svc.update_department(
        dept_id, name=body.name, code=body.code, description=body.description
    )
    return DepartmentResponse.model_validate(dept)


@router.post("/departments/{dept_id}/deactivate", response_model=DepartmentResponse)
async def deactivate_department(
    dept_id: UUID,
    confirm: bool = Query(False),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to proceed")
    dept = await svc.deactivate_department(dept_id)
    return DepartmentResponse.model_validate(dept)


# ── KRA Routes ────────────────────────────────────────────────────────────

@router.post("/kras", response_model=KraResponse, status_code=status.HTTP_201_CREATED)
async def create_kra(
    body: KraCreateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    kra = await svc.create_kra(name=body.name, description=body.description)
    return KraResponse.model_validate(kra)


@router.get("/kras", response_model=dict)
async def list_kras(
    include_deprecated: bool = False,
    page: int = 1,
    page_size: int = 50,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    kras, total = await svc.list_kras(
        include_deprecated=include_deprecated, page=page, page_size=page_size
    )
    return {
        "data": [KraResponse.model_validate(k) for k in kras],
        "pagination": {"page": page, "page_size": page_size, "total_count": total},
    }


@router.get("/kras/{kra_id}", response_model=KraResponse)
async def get_kra(
    kra_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    kra = await svc.get_kra(kra_id)
    return KraResponse.model_validate(kra)


@router.patch("/kras/{kra_id}", response_model=KraResponse)
async def update_kra(
    kra_id: UUID,
    body: KraUpdateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    kra = await svc.update_kra(kra_id, name=body.name, description=body.description, status=body.status)
    return KraResponse.model_validate(kra)


@router.post("/kras/{kra_id}/archive", response_model=KraResponse)
async def archive_kra(
    kra_id: UUID,
    confirm: bool = Query(False),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to proceed")
    kra = await svc.archive_kra(kra_id)
    return KraResponse.model_validate(kra)


# ── KPI Routes ────────────────────────────────────────────────────────────

@router.post("/kpis", response_model=KpiResponse, status_code=status.HTTP_201_CREATED)
async def create_kpi(
    body: KpiCreateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    kpi = await svc.create_kpi(
        kra_id=body.kra_id,
        title=body.title,
        description=body.description,
        owner=body.owner,
        target_value=body.target_value,
        comparator=body.comparator,
        unit_of_measure=body.unit_of_measure,
        frequency_code=body.frequency_code,
        capture_type=body.capture_type,
        category_code=body.category_code,
        is_sensitive=body.is_sensitive,
        evidence_required=body.evidence_required,
        amber_tolerance_band=body.amber_tolerance_band,
        created_by=UUID(tenant.user_id) if tenant.user_id else None,
    )
    return KpiResponse.model_validate(kpi)


@router.get("/kpis", response_model=dict)
async def list_kpis(
    kra_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    kpis, total = await svc.list_kpis(kra_id=kra_id, status=status_filter, page=page, page_size=page_size)
    return {
        "data": [KpiResponse.model_validate(k) for k in kpis],
        "pagination": {"page": page, "page_size": page_size, "total_count": total},
    }


@router.get("/kpis/{kpi_id}", response_model=KpiResponse)
async def get_kpi(
    kpi_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    kpi = await svc.get_current_kpi(kpi_id)
    return KpiResponse.model_validate(kpi)


@router.patch("/kpis/{kpi_id}", response_model=KpiResponse)
async def update_kpi(
    kpi_id: UUID,
    body: KpiUpdateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    payload = body.model_dump(exclude_unset=True)
    kpi = await svc.update_kpi(kpi_id, updated_by=UUID(tenant.user_id) if tenant.user_id else None, **payload)
    return KpiResponse.model_validate(kpi)


@router.post("/kpis/{kpi_id}/deprecate", response_model=KpiResponse)
async def deprecate_kpi(
    kpi_id: UUID,
    confirm: bool = Query(False),
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to proceed")
    kpi = await svc.deprecate_kpi(kpi_id)
    return KpiResponse.model_validate(kpi)


# ── KPI_Entry Routes ──────────────────────────────────────────────────────

@router.post("/kpi-entries", response_model=KpiEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_kpi_entry(
    body: KpiEntryCreateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    entry = await svc.create_kpi_entry(
        kpi_id=body.kpi_id,
        check_name=body.check_name,
        check_type=body.check_type,
        value=body.value,
        value_text=body.value_text,
        timestamp=body.timestamp,
        asset_id=body.asset_id,
        department_id=body.department_id,
        school_id=body.school_id,
        recorded_by=UUID(tenant.user_id) if tenant.user_id else body.recorded_by,
        notes=body.notes,
        evidence=body.evidence,
        legacy_kpi_id=body.legacy_kpi_id,
    )
    return KpiEntryResponse.model_validate(entry)


@router.get("/kpi-entries", response_model=dict)
async def list_kpi_entries(
    kpi_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
    school_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    entries, total = await svc.list_kpi_entries(
        kpi_id=kpi_id,
        department_id=department_id,
        school_id=school_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return {
        "data": [KpiEntryResponse.model_validate(e) for e in entries],
        "pagination": {"page": page, "page_size": page_size, "total_count": total},
    }


@router.get("/kpi-entries/{entry_id}", response_model=KpiEntryResponse)
async def get_kpi_entry(
    entry_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    entry = await svc.get_kpi_entry(entry_id)
    return KpiEntryResponse.model_validate(entry)


@router.patch("/kpi-entries/{entry_id}", response_model=KpiEntryResponse)
async def update_kpi_entry(
    entry_id: UUID,
    body: KpiEntryUpdateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    payload = body.model_dump(exclude_unset=True)
    entry = await svc.update_kpi_entry(entry_id, **payload)
    return KpiEntryResponse.model_validate(entry)


# ── Dashboard ─────────────────────────────────────────────────────────────

@router.get("/dashboard/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    school_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    tenant: TenantContext = Depends(require_tenant_context),
    svc: OrgService = Depends(_get_service),
):
    summary = await svc.get_dashboard_summary(
        school_id=school_id,
        department_id=department_id,
        date_from=date_from,
        date_to=date_to,
    )
    return DashboardSummary(**summary)
