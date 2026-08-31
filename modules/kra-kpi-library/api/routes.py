"""
KRA/KPI API endpoints — API-Spec §7, PRS §22-23.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..schemas import (
    KraCreateRequest,
    KraResponse,
    KraUpdateRequest,
    KpiCreateRequest,
    KpiImportRequest,
    KpiResponse,
    KpiUpdateRequest,
    ObservationSubmitRequest,
)
from ..services.kpi_service import KpiService
from ..services.kra_service import KraService
from shared.database import get_db
from shared.errors import AuthorizationError, BusinessRuleError
from shared.middleware.tenancy import TenantContext, require_tenant_context
from shared.middleware.permissions import PermissionChecker, Module, Action
from shared.models import UserRole

router = APIRouter(tags=["kra-kpi-library"])


async def _require_superadmin(tenant: TenantContext, db: AsyncSession) -> None:
    """Check permission via matrix: only SuperAdmin can manage the Global KPI Library (R-43)."""
    await PermissionChecker.require_permission(
        Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, tenant, db
    )


@router.post("/kras", response_model=KraResponse, status_code=status.HTTP_201_CREATED)
async def create_kra(
    body: KraCreateRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await _require_superadmin(tenant, db)
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
    await _require_superadmin(tenant, db)
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
    await _require_superadmin(tenant, db)
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
    # NOTE: Field-level permissions exist for kpi_library module but are currently inert on this route.
    # This route is SuperAdmin-only per _require_superadmin below. Field permissions are reserved
    # for a possible future Admin-facing KPI edit endpoint with finer-grained field restrictions.
    await _require_superadmin(tenant, db)
    
    # SuperAdmin has full access - skip field-level permission checks
    # Field permissions are only enforced for non-SuperAdmin roles in future endpoints
    
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
    confirm: bool = Query(False, description="Must be true to confirm destructive action"),
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Deprecate a KPI (mark as deprecated).
    Only SuperAdmin can deprecate KPIs.
    
    SECURITY FIX (Route Hygiene): Requires explicit confirmation for destructive action.
    """
    # Require explicit confirmation (Route Hygiene security fix)
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "CONFIRMATION_REQUIRED", "message": "Destructive action requires confirmation. Set confirm=true to proceed."}}
        )
    
    await _require_superadmin(tenant, db)
    service = KpiService(db)
    kpi = await service.deprecate_kpi(kpi_id)
    return KpiResponse.model_validate(kpi)


@router.post("/kpis/import", include_in_schema=False)
async def import_kpis(
    body: KpiImportRequest,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Import KPIs from seed file.
    Only SuperAdmin can import KPIs.
    
    SECURITY FIX (Route Hygiene): Hidden from public OpenAPI docs (include_in_schema=False).
    """
    await _require_superadmin(tenant, db)
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


# POST /observations is handled by modules/observation-capture/api/routes.py
# This module previously had a duplicate route that shadowed the canonical implementation.
# Removed to ensure exactly one route handles POST /api/v1/observations with idempotency,
# duplicate detection, and evidence handling per PRS §24.


@router.get("/permissions/fields")
async def get_field_permissions(
    module: str,
    tenant: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Get OR-resolved field permissions for current user's roles.
    Global scope (not tenant-specific) - field permissions are system-wide configuration.
    """
    from shared.permissions import _get_field_permissions_for_roles
    
    # Debug logging
    print(f"DEBUG get_field_permissions: User roles = {tenant.roles}")
    print(f"DEBUG get_field_permissions: Module = {module}")
    
    # Use shared helper for single-query + in-memory OR-resolution
    field_permissions = await _get_field_permissions_for_roles(
        db, module, tenant.roles
    )
    
    print(f"DEBUG get_field_permissions: Result = {field_permissions}")
    
    return {"module": module, "permissions": field_permissions}
