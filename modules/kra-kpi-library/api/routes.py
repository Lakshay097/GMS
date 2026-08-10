"""
KRA/KPI API endpoints — API-Spec §7, PRS §22-23.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.kra_kpi_library.schemas import (
    KraCreateRequest,
    KraResponse,
    KraUpdateRequest,
    KpiCreateRequest,
    KpiImportRequest,
    KpiResponse,
    KpiUpdateRequest,
    ObservationSubmitRequest,
)
from modules.kra_kpi_library.services.kpi_service import KpiService
from modules.kra_kpi_library.services.kra_service import KraService
from shared.database import get_db
from shared.errors import AuthorizationError, BusinessRuleError
from shared.middleware.tenancy import TenantContext, require_tenant_context
from shared.middleware.permissions import PermissionChecker, Module, Action
from shared.models import UserRole

router = APIRouter(tags=["kra-kpi-library"])


def _require_superadmin(tenant: TenantContext) -> None:
    if UserRole.SUPERADMIN.value not in tenant.roles:
        raise AuthorizationError("Only SuperAdmin can manage the Global KPI Library (R-43)")


@router.post("/kras", response_model=KraResponse, status_code=status.HTTP_201_CREATED)
async def create_kra(
    body: KraCreateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    _require_superadmin(tenant)
    service = KraService(db)
    kra = await service.create_kra(name=body.name, description=body.description)
    return KraResponse.model_validate(kra)


@router.get("/kras", response_model=list[KraResponse])
async def list_kras(
    include_deprecated: bool = False,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await PermissionChecker.require_permission(Module.GLOBAL_KPI_LIBRARY, Action.READ, tenant, db)
    service = KraService(db)
    kras = await service.list_kras(include_deprecated=include_deprecated)
    return [KraResponse.model_validate(kra) for kra in kras]


@router.patch("/kras/{kra_id}", response_model=KraResponse)
async def update_kra(
    kra_id: UUID,
    body: KraUpdateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    _require_superadmin(tenant)
    service = KraService(db)
    kra = await service.update_kra(
        kra_id,
        name=body.name,
        description=body.description,
        status=body.status,
    )
    return KraResponse.model_validate(kra)


@router.post("/kpis", response_model=KpiResponse, status_code=status.HTTP_201_CREATED)
async def create_kpi(
    body: KpiCreateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    _require_superadmin(tenant)
    service = KpiService(db)
    kpi = await service.create_kpi(
        kra_id=body.kra_id,
        title=body.title,
        target_value=body.target_value,
        comparator=body.comparator,
        unit_of_measure=body.unit_of_measure,
        frequency_code=body.frequency_code,
        created_by=tenant.user_id,
        capture_type=body.capture_type,
        category_code=body.category_code,
        is_sensitive=body.is_sensitive,
        amber_tolerance_band=body.amber_tolerance_band,
        working_days=body.working_days,
        non_working_day_policy=body.non_working_day_policy,
        event_time_points=[point.model_dump() for point in body.event_time_points],
    )
    return KpiResponse.model_validate(kpi)


@router.get("/kpis", response_model=list[KpiResponse])
async def list_kpis(
    kra_id: Optional[UUID] = None,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await PermissionChecker.require_permission(Module.GLOBAL_KPI_LIBRARY, Action.READ, tenant, db)
    service = KpiService(db)
    kpis = await service.list_current_kpis(kra_id=kra_id)
    return [KpiResponse.model_validate(kpi) for kpi in kpis]


@router.get("/kpis/{kpi_id}", response_model=KpiResponse)
async def get_kpi(
    kpi_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await PermissionChecker.require_permission(Module.GLOBAL_KPI_LIBRARY, Action.READ, tenant, db)
    service = KpiService(db)
    kpi = await service.get_current_kpi(kpi_id)
    return KpiResponse.model_validate(kpi)


@router.get("/kpis/{kpi_id}/versions", response_model=list[KpiResponse])
async def list_kpi_versions(
    kpi_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await PermissionChecker.require_permission(Module.GLOBAL_KPI_LIBRARY, Action.READ, tenant, db)
    service = KpiService(db)
    versions = await service.list_versions(kpi_id)
    return [KpiResponse.model_validate(kpi) for kpi in versions]


@router.get("/kpis/{kpi_id}/versions/{version}", response_model=KpiResponse)
async def get_kpi_version(
    kpi_id: UUID,
    version: int,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await PermissionChecker.require_permission(Module.GLOBAL_KPI_LIBRARY, Action.READ, tenant, db)
    service = KpiService(db)
    kpi = await service.get_kpi_version(kpi_id, version)
    return KpiResponse.model_validate(kpi)


@router.patch("/kpis/{kpi_id}", response_model=KpiResponse)
async def update_kpi(
    kpi_id: UUID,
    body: KpiUpdateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    _require_superadmin(tenant)
    service = KpiService(db)
    payload = body.model_dump(exclude_unset=True)
    if "event_time_points" in payload and payload["event_time_points"] is not None:
        payload["event_time_points"] = [
            point.model_dump() if hasattr(point, "model_dump") else point
            for point in payload["event_time_points"]
        ]
    kpi = await service.update_kpi(kpi_id, updated_by=tenant.user_id, **payload)
    return KpiResponse.model_validate(kpi)


@router.post("/kpis/{kpi_id}/deprecate", response_model=KpiResponse)
async def deprecate_kpi(
    kpi_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    _require_superadmin(tenant)
    service = KpiService(db)
    kpi = await service.deprecate_kpi(kpi_id)
    return KpiResponse.model_validate(kpi)


@router.post("/kpis/import")
async def import_kpis(
    body: KpiImportRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    _require_superadmin(tenant)
    service = KpiService(db)
    return await service.import_from_seed_file(
        seed_file_path=body.seed_file_path,
        confirm_sme_review=body.confirm_sme_review,
        created_by=tenant.user_id,
    )


@router.post("/departments/{department_id}/kpi-assignments", status_code=status.HTTP_201_CREATED)
async def assign_kpi_to_department(
    department_id: UUID,
    kpi_id: UUID,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await PermissionChecker.require_permission(Module.KPI_ASSIGNMENT, Action.ASSIGN, tenant, db)
    service = KpiService(db)
    assignment = await service.assign_to_department(
        department_id=department_id,
        kpi_id=kpi_id,
        assigned_by=tenant.user_id,
    )
    return {"id": assignment.id, "department_id": assignment.department_id, "kpi_id": assignment.kpi_id}


@router.post("/observations", status_code=status.HTTP_201_CREATED)
async def submit_observation(
    body: ObservationSubmitRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await PermissionChecker.require_permission(Module.OBSERVATION, Action.CREATE, tenant, db)
    service = KpiService(db)
    try:
        observation = await service.submit_observation(
            kpi_id=body.kpi_id,
            kpi_version=body.kpi_version,
            checker_id=tenant.user_id,
            department_id=tenant.department_id,
            school_id=tenant.school_id,
            value_numeric=body.value_numeric,
            value_text=body.value_text,
            is_late=body.is_late,
            submission_token=body.submission_token,
        )
    except BusinessRuleError:
        raise
    return {
        "id": observation.id,
        "kpi_id": observation.kpi_id,
        "kpi_version": observation.kpi_version,
        "auto_result": observation.auto_result.value,
        "rag_status": observation.rag_status.value,
    }
