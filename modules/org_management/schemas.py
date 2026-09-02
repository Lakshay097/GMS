"""
Pydantic schemas for School, Department, KRA, KPI, KPI_Entry CRUD.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── School ────────────────────────────────────────────────────────────────

class SchoolCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    timezone: Optional[str] = None


class SchoolUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    timezone: Optional[str] = None


class SchoolResponse(BaseModel):
    id: UUID
    name: str
    code: str
    status: str
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    timezone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deactivated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Department ────────────────────────────────────────────────────────────

class DepartmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    school_id: UUID
    description: Optional[str] = None


class DepartmentUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None


class DepartmentResponse(BaseModel):
    id: UUID
    school_id: UUID
    name: str
    code: str
    status: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── KRA ───────────────────────────────────────────────────────────────────

class KraCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class KraUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None


class KraResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── KPI ───────────────────────────────────────────────────────────────────

class KpiCreateRequest(BaseModel):
    kra_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    owner: Optional[UUID] = None
    target_value: Decimal = Field(default=Decimal("100"))
    comparator: str = Field(default=">=")
    unit_of_measure: str = Field(default="percent", min_length=1, max_length=50)
    frequency_code: str = Field(default="daily")
    capture_type: str = Field(default="value_reading")
    category_code: Optional[str] = None
    is_sensitive: bool = False
    evidence_required: bool = False
    amber_tolerance_band: Optional[Decimal] = None


class KpiUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    owner: Optional[UUID] = None
    target_value: Optional[Decimal] = None
    comparator: Optional[str] = None
    unit_of_measure: Optional[str] = None
    frequency_code: Optional[str] = None
    capture_type: Optional[str] = None
    category_code: Optional[str] = None
    is_sensitive: Optional[bool] = None
    evidence_required: Optional[bool] = None
    amber_tolerance_band: Optional[Decimal] = None
    status: Optional[str] = None


class KpiResponse(BaseModel):
    kpi_id: UUID
    version: int
    kra_id: UUID
    title: str
    description: Optional[str] = None
    owner: Optional[UUID] = None
    target_value: Decimal
    comparator: str
    unit_of_measure: str
    frequency_code: str
    capture_type: str
    category_code: Optional[str] = None
    is_sensitive: bool
    evidence_required: bool
    amber_tolerance_band: Optional[Decimal] = None
    status: str
    is_immutable: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── KPI_Entry ─────────────────────────────────────────────────────────────

class KpiEntryCreateRequest(BaseModel):
    kpi_id: UUID
    check_name: Optional[str] = None
    check_type: Optional[str] = None
    value: Optional[Decimal] = None
    value_text: Optional[str] = None
    timestamp: Optional[datetime] = None  # auto-filled if omitted
    asset_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    school_id: Optional[UUID] = None
    recorded_by: Optional[UUID] = None  # auto-filled from auth
    notes: Optional[str] = None
    evidence: Optional[list[dict]] = None
    legacy_kpi_id: Optional[UUID] = None


class KpiEntryUpdateRequest(BaseModel):
    check_name: Optional[str] = None
    check_type: Optional[str] = None
    value: Optional[Decimal] = None
    value_text: Optional[str] = None
    asset_id: Optional[UUID] = None
    notes: Optional[str] = None
    evidence: Optional[list[dict]] = None
    status: Optional[str] = None  # manual override (under_review, pass, fail)


class KpiEntryResponse(BaseModel):
    id: UUID
    kpi_id: UUID
    check_name: Optional[str] = None
    check_type: Optional[str] = None
    value: Optional[Decimal] = None
    value_text: Optional[str] = None
    timestamp: datetime
    asset_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    school_id: Optional[UUID] = None
    recorded_by: Optional[UUID] = None
    status: str
    notes: Optional[str] = None
    evidence: Optional[list] = None
    legacy_kpi_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard ─────────────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total_schools: int
    total_departments: int
    total_kras: int
    total_kpis: int
    total_entries: int
    entries_by_status: dict  # {"pass": N, "fail": N, "pending": N, "under_review": N}
    entries_by_school: list[dict]  # [{"school_id": X, "school_name": "...", "pass": N, "fail": N}]
    entries_by_kpi: list[dict]  # [{"kpi_id": X, "title": "...", "pass": N, "fail": N}]
