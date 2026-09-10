"""
Pydantic schemas for Dashboards, Reports, Search, and Export — PRS §30-31, §33, §50.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Common ─────────────────────────────────────────────────────────────────────

class DateRangeFilter(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)


# ── Dashboard schemas ──────────────────────────────────────────────────────────

class KpiSummaryWidget(BaseModel):
    total_kpis: int
    met: int
    not_met: int
    amber: int
    pct_met: float


class ComplianceSummaryWidget(BaseModel):
    total_due: int
    submitted: int
    missed: int
    late: int
    pct_submitted: float


class TaskSummaryWidget(BaseModel):
    open_tasks: int
    overdue_tasks: int
    completed_this_period: int
    pct_on_time: float


class DiscrepancySummaryWidget(BaseModel):
    open_discrepancies: int
    under_investigation: int
    pending_approval: int
    resolved_this_period: int
    breached_sla: int


class EscalationSummaryWidget(BaseModel):
    open_escalations: int
    acknowledged: int
    by_level: List[Dict[str, Any]]


class RagDistributionWidget(BaseModel):
    green: int
    amber: int
    red: int
    not_submitted: int


class SchoolFrequencyRow(BaseModel):
    """Per-school progress inside one frequency band (superadmin breakdown)."""
    school_id: UUID
    school_name: str
    total_kpis: int
    submitted: int
    pct_complete: float


class FrequencyPeriodProgress(BaseModel):
    """Per-frequency breakdown: how many KPIs exist, submitted, and pending for the current period."""
    frequency: str
    label: str
    total_kpis: int
    submitted: int
    pending: int
    pct_complete: float
    period_start: str  # ISO date string
    period_end: str    # ISO date string
    # KRA context: distinct KRA names the band's KPIs belong to
    kra_names: List[str] = []
    # Per-school breakdown (populated for superadmin scope only, else empty)
    schools: List[SchoolFrequencyRow] = []


class FrequencyProgressWidget(BaseModel):
    """Frequency-aware KPI progress across all frequency bands."""
    periods: List[FrequencyPeriodProgress]
    overall_submitted: int
    overall_total: int
    overall_pct: float


class RecentActivityItem(BaseModel):
    entity_type: str
    entity_id: UUID
    action: str
    actor_name: str
    timestamp: datetime


class DashboardResponse(BaseModel):
    role: str
    school_id: Optional[UUID]
    department_id: Optional[UUID]
    generated_at: datetime
    # Widgets — presence depends on role (None = not visible for this role)
    kpi_summary: Optional[KpiSummaryWidget] = None
    compliance_summary: Optional[ComplianceSummaryWidget] = None
    task_summary: Optional[TaskSummaryWidget] = None
    discrepancy_summary: Optional[DiscrepancySummaryWidget] = None
    escalation_summary: Optional[EscalationSummaryWidget] = None
    rag_distribution: Optional[RagDistributionWidget] = None
    frequency_progress: Optional[FrequencyProgressWidget] = None
    recent_activity: Optional[List[RecentActivityItem]] = None
    pending_my_action: Optional[List[Dict[str, Any]]] = None


# ── Filterable dashboard summary (PRS §30) ─────────────────────────────────────

class DashboardSummaryMeta(BaseModel):
    period: str
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    school_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    filters_applied: List[str] = []


class KpiLibraryTotals(BaseModel):
    total_kras: int
    total_kpis: int
    assigned_kpis: int  # KPIs assigned to at least one department
    unassigned_kpis: int


class KpiEntryRates(BaseModel):
    expected_entries: int
    entered: int
    missing: int
    late: int
    follow_up: int  # amber RAG — needs follow-up
    entered_rate: float  # percent
    missing_rate: float
    follow_up_rate: float


class TaskPipelineCounts(BaseModel):
    assigned_open: int  # open + in_progress
    pending_approval: int
    completed: int  # completed within the selected period
    overdue: int  # open/in_progress/escalated past ETA
    escalated: int  # currently in escalated state
    on_time_rate: float  # percent of completions on time in period


class SummaryTrendPoint(BaseModel):
    label: str  # day or week label
    date: date
    entered: int
    missing: int
    tasks_completed: int


class DepartmentSummaryRow(BaseModel):
    department_id: UUID
    department_name: str
    kpis_assigned: int
    entered: int
    missing: int
    pct_entered: float


class SchoolSummaryRow(BaseModel):
    school_id: UUID
    school_name: str
    kpis_assigned: int
    entered: int
    missing: int
    pct_entered: float


class DashboardSummaryResponse(BaseModel):
    role: str
    generated_at: datetime
    filters: DashboardSummaryMeta
    kpi_library: KpiLibraryTotals
    entries: KpiEntryRates
    tasks: TaskPipelineCounts
    trend: List[SummaryTrendPoint]
    by_department: Optional[List[DepartmentSummaryRow]] = None
    by_school: Optional[List[SchoolSummaryRow]] = None


# ── Report catalogue schemas ───────────────────────────────────────────────────

class ReportMeta(BaseModel):
    slug: str
    title: str
    description: str
    available_formats: List[str]
    required_roles: List[str]


class ReportCatalogueResponse(BaseModel):
    reports: List[ReportMeta]


class ReportFilter(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    school_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    kpi_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    category_code: Optional[str] = None
    status: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(100, ge=1, le=1000)


class ReportRow(BaseModel):
    """Generic key-value row — each report type returns typed rows via its own schema."""
    data: Dict[str, Any]


class ReportResponse(BaseModel):
    report_type: str
    generated_at: datetime
    total_rows: int
    page: int
    page_size: int
    rows: List[Dict[str, Any]]


# ── Export schemas ─────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    report_type: str = Field(..., description="Report slug from PRS §50 catalogue")
    format: str = Field(..., pattern="^(excel|csv|pdf|api)$")
    filters: Optional[ReportFilter] = None


class ExportJobResponse(BaseModel):
    job_id: UUID
    status: str
    report_type: str
    format: str
    enqueued_at: datetime
    result_url: Optional[str] = None
    completed_at: Optional[datetime] = None
    error_detail: Optional[str] = None
    row_count: Optional[int] = None
    file_size_bytes: Optional[int] = None


# ── Category export restriction schemas ───────────────────────────────────────

class CategoryRestrictionCreate(BaseModel):
    category_code: str
    restricted_role: str = Field(..., description="Lowercase role: viewer, checker, auditor, admin")
    restrict_export: bool = True
    restrict_view: bool = False


class CategoryRestrictionResponse(BaseModel):
    id: UUID
    category_code: str
    restricted_role: str
    restrict_export: bool
    restrict_view: bool
    created_at: datetime


# ── Global Search schemas ──────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=500)
    entity_types: Optional[List[str]] = None  # None = all accessible types
    school_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class SearchHit(BaseModel):
    entity_type: str
    entity_id: UUID
    school_id: Optional[UUID]
    department_id: Optional[UUID]
    title: str
    description: Optional[str]
    status: Optional[str]
    score: Optional[float]
    highlighted: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime]


class SearchResponse(BaseModel):
    query: str
    total_hits: int
    page: int
    page_size: int
    processing_time_ms: int
    hits: List[SearchHit]


# ── Saved filter schemas ───────────────────────────────────────────────────────

class SavedFilterCreate(BaseModel):
    context: str = Field(..., description="search | report:<slug> | dashboard")
    name: str = Field(..., min_length=1, max_length=255)
    filters: Dict[str, Any]
    is_public: bool = False


class SavedFilterUpdate(BaseModel):
    name: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None


class SavedFilterResponse(BaseModel):
    id: UUID
    context: str
    name: str
    filters: Dict[str, Any]
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
