"""
Report query service — PRS §50 full catalogue (R-59/BR-17).

All queries use the READ replica session (get_read_db) so heavy analytical
scans cannot exhaust the write-path pool (R-61/Architecture §14).

Report slugs (18 types)
-----------------------
compliance               Compliance status across KPIs / departments
kpi_performance          KPI met/not-met counts with RAG breakdown
kpi_trend                KPI performance trend over time
school_scorecard         School-level scorecard summary
department_scorecard     Department-level scorecard summary
audit                    Audit observation detail
pending_audits           Observations awaiting audit verification
task_aging               Task age distribution and overdue analysis
open_discrepancies       Open discrepancy list
discrepancy_sla          Discrepancy resolution SLA tracking
overdue_kpi              KPIs with no recent submission (missed)
user_performance         Per-user KPI submission and task completion rates
user_productivity        Observation count and quality per user per period
school_comparison        Cross-school KPI/compliance comparison
department_comparison    Cross-department KPI/compliance comparison
escalation_summary       Open escalations by level and department
inventory                Asset inventory listing (Active/Retired)
vendor                   Vendor/supplier ledger (placeholder — future phase)
compliance_dashboard     Compliance Dashboard export (aggregated view)
trend_analysis           Multi-period trend analysis across selected KPIs
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.dashboards_reports_search.schemas import ReportFilter, ReportResponse
from shared.errors import NotFoundError, ValidationError
from shared.middleware.tenancy import TenantContext


# ── Catalogue metadata ────────────────────────────────────────────────────────

REPORT_CATALOGUE: List[Dict[str, Any]] = [
    {"slug": "compliance",           "title": "Compliance Report",
     "description": "KPI submission compliance status across departments and periods.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor", "viewer"]},
    {"slug": "kpi_performance",      "title": "KPI Performance Report",
     "description": "Met/not-met counts with RAG breakdown per KPI.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor", "viewer"]},
    {"slug": "kpi_trend",            "title": "KPI Trend Report",
     "description": "KPI performance trend over consecutive periods.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor", "viewer"]},
    {"slug": "school_scorecard",     "title": "School Scorecard",
     "description": "School-level scorecard summary with RAG roll-up.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "viewer"]},
    {"slug": "department_scorecard", "title": "Department Scorecard",
     "description": "Department-level scorecard with KPI breakdown.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor", "viewer"]},
    {"slug": "audit",                "title": "Audit Report",
     "description": "Audit observation detail with verification outcomes.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor"]},
    {"slug": "pending_audits",       "title": "Pending Audits",
     "description": "Observations awaiting audit verification.",
     "available_formats": ["excel", "csv", "api"],
     "required_roles": ["superadmin", "admin", "auditor"]},
    {"slug": "task_aging",           "title": "Task Aging Report",
     "description": "Task age distribution and overdue analysis.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor", "viewer"]},
    {"slug": "open_discrepancies",   "title": "Open Discrepancies",
     "description": "All open discrepancy records with current state.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor"]},
    {"slug": "discrepancy_sla",      "title": "Discrepancy Resolution SLA",
     "description": "SLA compliance for discrepancy resolution lifecycle.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor"]},
    {"slug": "overdue_kpi",          "title": "Overdue KPI Report",
     "description": "KPIs with no recent submission within the expected window.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor", "viewer"]},
    {"slug": "user_performance",     "title": "User Performance Report",
     "description": "Per-user KPI submission rate and task completion.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin"]},
    {"slug": "user_productivity",    "title": "User Productivity Report",
     "description": "Observation count and quality metrics per user per period.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin"]},
    {"slug": "school_comparison",    "title": "School Comparison",
     "description": "Cross-school KPI and compliance comparison.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin"]},
    {"slug": "department_comparison","title": "Department Comparison",
     "description": "Cross-department KPI and compliance comparison within a school.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "viewer"]},
    {"slug": "escalation_summary",   "title": "Escalation Summary",
     "description": "Open escalations by level, department, and age.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor"]},
    {"slug": "inventory",            "title": "Inventory Report",
     "description": "Asset inventory listing (Active/Retired) with category.",
     "available_formats": ["excel", "csv", "api"],
     "required_roles": ["superadmin", "admin"]},
    {"slug": "vendor",               "title": "Vendor Report",
     "description": "Vendor/supplier ledger (Phase 2 — placeholder).",
     "available_formats": ["excel", "csv", "api"],
     "required_roles": ["superadmin", "admin"]},
    {"slug": "compliance_dashboard", "title": "Compliance Dashboard Export",
     "description": "Aggregated compliance dashboard as a downloadable snapshot.",
     "available_formats": ["excel", "pdf"],
     "required_roles": ["superadmin", "admin", "auditor", "viewer"]},
    {"slug": "trend_analysis",       "title": "Trend Analysis",
     "description": "Multi-period trend analysis across selected KPIs.",
     "available_formats": ["excel", "csv", "pdf", "api"],
     "required_roles": ["superadmin", "admin", "auditor", "viewer"]},
]

_SLUG_SET = {r["slug"] for r in REPORT_CATALOGUE}


# ── Tenant scope helper ───────────────────────────────────────────────────────

def _school_clause(tenant: TenantContext, alias: str = "") -> tuple[str, Dict[str, Any]]:
    """Return (WHERE fragment, params) for school-level scoping."""
    col = f"{alias}.school_id" if alias else "school_id"
    role_lower = [r.lower() for r in tenant.roles]
    if "superadmin" in role_lower:
        return "", {}
    if "viewer" in role_lower and tenant.accessible_school_ids:
        return (
            f"{col} = ANY(:school_ids)",
            {"school_ids": tenant.accessible_school_ids},
        )
    if tenant.school_id:
        return f"{col} = :school_id", {"school_id": tenant.school_id}
    return "1=0", {}   # no scope — return nothing


def _dept_clause(tenant: TenantContext, alias: str = "") -> tuple[str, Dict[str, Any]]:
    """Optional department filter when the tenant has a specific department."""
    if tenant.department_id:
        col = f"{alias}.department_id" if alias else "department_id"
        return f"{col} = :dept_id", {"dept_id": tenant.department_id}
    return "", {}


def _date_clause(
    flt: ReportFilter,
    col: str,
) -> tuple[str, Dict[str, Any]]:
    parts: List[str] = []
    params: Dict[str, Any] = {}
    if flt.date_from:
        parts.append(f"{col} >= :date_from")
        params["date_from"] = flt.date_from
    if flt.date_to:
        parts.append(f"{col} <= :date_to")
        params["date_to"] = flt.date_to
    return " AND ".join(parts), params


def _build_where(clauses: List[str]) -> str:
    active = [c for c in clauses if c.strip()]
    return ("WHERE " + " AND ".join(f"({c})" for c in active)) if active else ""


def _offset_limit(flt: ReportFilter) -> tuple[int, int]:
    return (flt.page - 1) * flt.page_size, flt.page_size


# ── Report service ────────────────────────────────────────────────────────────

class ReportService:
    """
    Executes analytical queries against the READ replica session.
    Never touches the write-path engine.
    """

    def __init__(self, db: AsyncSession) -> None:
        # db MUST be the read-replica session (injected via Depends(get_read_db))
        self.db = db

    async def run(
        self,
        report_type: str,
        flt: ReportFilter,
        tenant: TenantContext,
    ) -> ReportResponse:
        if report_type not in _SLUG_SET:
            raise ValidationError(f"Unknown report type: {report_type}")
        handler = getattr(self, f"_report_{report_type.replace('-', '_')}", None)
        if handler is None:
            raise ValidationError(f"Report '{report_type}' not yet implemented")
        rows, total = await handler(flt, tenant)
        return ReportResponse(
            report_type=report_type,
            generated_at=datetime.now(timezone.utc),
            total_rows=total,
            page=flt.page,
            page_size=flt.page_size,
            rows=rows,
        )

    # ── 1. Compliance ─────────────────────────────────────────────────────────
    async def _report_compliance(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "co")
        dc, dp = _date_clause(flt, "co.due_at")
        offset, limit = _offset_limit(flt)
        params: Dict[str, Any] = {**sp, **dp, "limit": limit, "offset": offset}
        where = _build_where([sc, dc])
        sql = f"""
            SELECT
                co.id,
                co.kpi_id,
                k.title          AS kpi_title,
                k.frequency_code,
                co.school_id,
                s.name           AS school_name,
                co.department_id,
                d.name           AS department_name,
                co.compliance_status,
                co.due_at,
                co.submitted_at
            FROM compliance_observations co
            LEFT JOIN kpis k ON k.kpi_id = co.kpi_id AND k.version = co.kpi_version
            LEFT JOIN schools s ON s.id = co.school_id
            LEFT JOIN departments d ON d.id = co.department_id
            {where}
            ORDER BY co.due_at DESC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM compliance_observations co {where}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 2. KPI Performance ────────────────────────────────────────────────────
    async def _report_kpi_performance(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "o")
        dc, dp = _date_clause(flt, "o.submitted_at")
        offset, limit = _offset_limit(flt)
        params: Dict[str, Any] = {**sp, **dp, "limit": limit, "offset": offset}
        where = _build_where([sc, dc])
        sql = f"""
            SELECT
                o.kpi_id,
                k.title           AS kpi_title,
                k.category_code,
                o.school_id,
                s.name            AS school_name,
                COUNT(*)          AS total_obs,
                SUM(CASE WHEN o.auto_result = 'met'     THEN 1 ELSE 0 END) AS met,
                SUM(CASE WHEN o.auto_result = 'not_met' THEN 1 ELSE 0 END) AS not_met,
                SUM(CASE WHEN o.rag_status  = 'green'   THEN 1 ELSE 0 END) AS green,
                SUM(CASE WHEN o.rag_status  = 'amber'   THEN 1 ELSE 0 END) AS amber,
                SUM(CASE WHEN o.rag_status  = 'red'     THEN 1 ELSE 0 END) AS red,
                ROUND(
                    100.0 * SUM(CASE WHEN o.auto_result = 'met' THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2
                )                 AS pct_met
            FROM observations o
            LEFT JOIN kpis k ON k.kpi_id = o.kpi_id AND k.version = o.kpi_version
            LEFT JOIN schools s ON s.id = o.school_id
            {where}
            GROUP BY o.kpi_id, k.title, k.category_code, o.school_id, s.name
            ORDER BY pct_met ASC NULLS LAST
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"""
            SELECT COUNT(DISTINCT (o.kpi_id, o.school_id))
            FROM observations o {where}
        """
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total or 0)

    # ── 3. KPI Trend ──────────────────────────────────────────────────────────
    async def _report_kpi_trend(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "o")
        dc, dp = _date_clause(flt, "o.submitted_at")
        kpi_clause = "AND o.kpi_id = :kpi_id" if flt.kpi_id else ""
        if flt.kpi_id:
            sp["kpi_id"] = str(flt.kpi_id)
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        where = _build_where([sc, dc])
        sql = f"""
            SELECT
                DATE_TRUNC('week', o.submitted_at) AS period_start,
                o.kpi_id,
                k.title   AS kpi_title,
                o.school_id,
                ROUND(
                    100.0 * SUM(CASE WHEN o.auto_result = 'met' THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2
                )         AS pct_met,
                COUNT(*)  AS obs_count
            FROM observations o
            LEFT JOIN kpis k ON k.kpi_id = o.kpi_id AND k.version = o.kpi_version
            {where} {kpi_clause}
            GROUP BY DATE_TRUNC('week', o.submitted_at), o.kpi_id, k.title, o.school_id
            ORDER BY period_start, o.kpi_id
            LIMIT :limit OFFSET :offset
        """
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        return [dict(r) for r in rows], len(rows)


    # ── 4. School Scorecard ───────────────────────────────────────────────────
    async def _report_school_scorecard(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "sc")
        dc, dp = _date_clause(flt, "sc.cycle_start")
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        where = _build_where([sc, dc, "sc.subject_type = 'school'"])
        sql = f"""
            SELECT
                sc.id,
                sc.subject_id  AS school_id,
                s.name         AS school_name,
                sc.cycle_start,
                sc.cycle_end,
                sc.version,
                sc.rag_status,
                sc.pct_kpis_met,
                sc.pct_tasks_on_time,
                sc.open_discrepancy_count,
                sc.generated_at
            FROM scorecards sc
            LEFT JOIN schools s ON s.id = sc.subject_id
            {where}
            ORDER BY sc.cycle_start DESC, sc.version DESC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM scorecards sc {where}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 5. Department Scorecard ───────────────────────────────────────────────
    async def _report_department_scorecard(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "d")
        dc, dp = _date_clause(flt, "sc.cycle_start")
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        dept_extra = "AND sc.subject_id = :dept_id" if flt.department_id else ""
        if flt.department_id:
            params["dept_id"] = str(flt.department_id)
        where = _build_where([sc, dc, "sc.subject_type = 'department'"])
        sql = f"""
            SELECT
                sc.id,
                sc.subject_id  AS department_id,
                d.name         AS department_name,
                d.school_id,
                s.name         AS school_name,
                sc.cycle_start,
                sc.cycle_end,
                sc.version,
                sc.rag_status,
                sc.pct_kpis_met,
                sc.pct_tasks_on_time,
                sc.open_discrepancy_count,
                sc.kpi_breakdown,
                sc.generated_at
            FROM scorecards sc
            JOIN departments d ON d.id = sc.subject_id
            LEFT JOIN schools s ON s.id = d.school_id
            {where} {dept_extra}
            ORDER BY sc.cycle_start DESC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"""
            SELECT COUNT(*) FROM scorecards sc
            JOIN departments d ON d.id = sc.subject_id
            {where} {dept_extra}
        """
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 6. Audit ──────────────────────────────────────────────────────────────
    async def _report_audit(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "o")
        dc, dp = _date_clause(flt, "o.submitted_at")
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        where = _build_where([sc, dc])
        sql = f"""
            SELECT
                o.id,
                o.kpi_id,
                k.title          AS kpi_title,
                o.school_id,
                s.name           AS school_name,
                o.department_id,
                d.name           AS department_name,
                o.checker_id,
                u.full_name      AS checker_name,
                o.auto_result,
                o.rag_status,
                o.value_numeric,
                o.value_text,
                o.is_late,
                o.submitted_at
            FROM observations o
            LEFT JOIN kpis k ON k.kpi_id = o.kpi_id AND k.version = o.kpi_version
            LEFT JOIN schools s ON s.id = o.school_id
            LEFT JOIN departments d ON d.id = o.department_id
            LEFT JOIN users u ON u.id = o.checker_id
            {where}
            ORDER BY o.submitted_at DESC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM observations o {where}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 7. Pending Audits ─────────────────────────────────────────────────────
    async def _report_pending_audits(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "co")
        dc, dp = _date_clause(flt, "co.due_at")
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        where = _build_where([sc, dc, "co.compliance_status = 'submitted'"])
        sql = f"""
            SELECT
                co.id,
                co.kpi_id,
                k.title  AS kpi_title,
                co.school_id,
                co.department_id,
                d.name   AS department_name,
                co.due_at,
                co.submitted_at
            FROM compliance_observations co
            LEFT JOIN kpis k ON k.kpi_id = co.kpi_id AND k.version = co.kpi_version
            LEFT JOIN departments d ON d.id = co.department_id
            {where}
            ORDER BY co.due_at ASC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM compliance_observations co {where}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)


    # ── 8. Task Aging ─────────────────────────────────────────────────────────
    async def _report_task_aging(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "t")
        dc, dp = _date_clause(flt, "t.created_at")
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        where = _build_where([sc, dc])
        sql = f"""
            SELECT
                t.id,
                t.title,
                t.school_id,
                s.name        AS school_name,
                t.department_id,
                d.name        AS department_name,
                t.status,
                t.eta,
                t.created_at,
                EXTRACT(EPOCH FROM (NOW() - t.created_at)) / 86400 AS age_days,
                CASE WHEN t.eta < NOW() AND t.status NOT IN ('completed','cancelled')
                     THEN TRUE ELSE FALSE END AS is_overdue,
                t.eta_extension_count
            FROM tasks t
            LEFT JOIN schools s ON s.id = t.school_id
            LEFT JOIN departments d ON d.id = t.department_id
            {where}
            ORDER BY age_days DESC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM tasks t {where}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 9. Open Discrepancies ─────────────────────────────────────────────────
    async def _report_open_discrepancies(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "disc")
        offset, limit = _offset_limit(flt)
        params = {**sp, "limit": limit, "offset": offset}
        open_states = "('raised','under_investigation','pending_approval')"
        where = _build_where([sc, f"disc.state IN {open_states}"])
        sql = f"""
            SELECT
                disc.id,
                disc.school_id,
                s.name    AS school_name,
                disc.department_id,
                d.name    AS department_name,
                dc.name   AS category_name,
                disc.state,
                disc.raised_at,
                EXTRACT(EPOCH FROM (NOW() - disc.raised_at)) / 86400 AS age_days
            FROM discrepancies disc
            LEFT JOIN schools s ON s.id = disc.school_id
            LEFT JOIN departments d ON d.id = disc.department_id
            LEFT JOIN discrepancy_categories dc ON dc.id = disc.category_id
            {where}
            ORDER BY disc.raised_at ASC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM discrepancies disc {where}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 10. Discrepancy Resolution SLA ────────────────────────────────────────
    async def _report_discrepancy_sla(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "disc")
        dc, dp = _date_clause(flt, "disc.raised_at")
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        where = _build_where([sc, dc])
        sql = f"""
            SELECT
                disc.id,
                disc.school_id,
                s.name     AS school_name,
                dc.name    AS category_name,
                disc.state,
                disc.raised_at,
                disc.closed_at,
                EXTRACT(EPOCH FROM (COALESCE(disc.closed_at, NOW()) - disc.raised_at))
                    / 3600   AS resolution_hours,
                CASE WHEN disc.closed_at IS NOT NULL
                         AND EXTRACT(EPOCH FROM (disc.closed_at - disc.raised_at)) / 3600 > 72
                     THEN TRUE
                     WHEN disc.closed_at IS NULL
                         AND EXTRACT(EPOCH FROM (NOW() - disc.raised_at)) / 3600 > 72
                     THEN TRUE
                     ELSE FALSE END AS sla_breached
            FROM discrepancies disc
            LEFT JOIN schools s ON s.id = disc.school_id
            LEFT JOIN discrepancy_categories dc ON dc.id = disc.category_id
            {where}
            ORDER BY sla_breached DESC, disc.raised_at ASC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM discrepancies disc {where}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 11. Overdue KPI ───────────────────────────────────────────────────────
    async def _report_overdue_kpi(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "co")
        offset, limit = _offset_limit(flt)
        params = {**sp, "limit": limit, "offset": offset}
        where = _build_where([sc, "co.compliance_status IN ('closed_missed','open')"])
        sql = f"""
            SELECT
                co.kpi_id,
                k.title   AS kpi_title,
                k.frequency_code,
                co.school_id,
                s.name    AS school_name,
                co.department_id,
                d.name    AS department_name,
                co.due_at,
                co.compliance_status,
                EXTRACT(EPOCH FROM (NOW() - co.due_at)) / 86400 AS overdue_days
            FROM compliance_observations co
            LEFT JOIN kpis k ON k.kpi_id = co.kpi_id AND k.version = co.kpi_version
            LEFT JOIN schools s ON s.id = co.school_id
            LEFT JOIN departments d ON d.id = co.department_id
            {where}
            ORDER BY overdue_days DESC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM compliance_observations co {where}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)


    # ── 12. User Performance ──────────────────────────────────────────────────
    async def _report_user_performance(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "u")
        dc, dp = _date_clause(flt, "o.submitted_at")
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        where_u = _build_where([sc])
        where_o = "AND " + dc if dc else ""
        sql = f"""
            SELECT
                u.id            AS user_id,
                u.full_name,
                u.school_id,
                s.name          AS school_name,
                COUNT(DISTINCT o.id) AS total_observations,
                SUM(CASE WHEN o.auto_result = 'met' THEN 1 ELSE 0 END)      AS obs_met,
                SUM(CASE WHEN o.is_late = TRUE THEN 1 ELSE 0 END)           AS obs_late,
                COUNT(DISTINCT CASE WHEN tow.user_id IS NOT NULL THEN tow.task_id END) AS tasks_assigned,
                COUNT(DISTINCT CASE WHEN toc.user_id IS NOT NULL THEN toc.task_id END) AS tasks_completed
            FROM users u
            LEFT JOIN schools s ON s.id = u.school_id
            LEFT JOIN observations o ON o.checker_id = u.id {where_o}
            LEFT JOIN task_owners tow ON tow.user_id = u.id
            LEFT JOIN task_owner_completions toc ON toc.user_id = u.id
            {where_u}
            GROUP BY u.id, u.full_name, u.school_id, s.name
            ORDER BY total_observations DESC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM users u {where_u}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 13. User Productivity ─────────────────────────────────────────────────
    async def _report_user_productivity(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "u")
        dc, dp = _date_clause(flt, "o.submitted_at")
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        where_u = _build_where([sc])
        where_o = "AND " + dc if dc else ""
        sql = f"""
            SELECT
                u.id            AS user_id,
                u.full_name,
                DATE_TRUNC('week', o.submitted_at) AS week_start,
                COUNT(o.id)     AS obs_count,
                SUM(CASE WHEN o.auto_result = 'met'     THEN 1 ELSE 0 END) AS met_count,
                SUM(CASE WHEN o.auto_result = 'not_met' THEN 1 ELSE 0 END) AS not_met_count,
                SUM(CASE WHEN o.is_late = TRUE           THEN 1 ELSE 0 END) AS late_count,
                ROUND(
                    100.0 * SUM(CASE WHEN o.auto_result = 'met' THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(o.id), 0), 2
                ) AS quality_pct
            FROM users u
            JOIN observations o ON o.checker_id = u.id {where_o}
            {where_u}
            GROUP BY u.id, u.full_name, DATE_TRUNC('week', o.submitted_at)
            ORDER BY week_start DESC, obs_count DESC
            LIMIT :limit OFFSET :offset
        """
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        return [dict(r) for r in rows], len(rows)

    # ── 14. School Comparison ─────────────────────────────────────────────────
    async def _report_school_comparison(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        dc, dp = _date_clause(flt, "o.submitted_at")
        offset, limit = _offset_limit(flt)
        params = {**dp, "limit": limit, "offset": offset}
        where = _build_where([dc])
        sql = f"""
            SELECT
                o.school_id,
                s.name   AS school_name,
                COUNT(*) AS total_obs,
                ROUND(100.0 * SUM(CASE WHEN o.auto_result = 'met' THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2) AS pct_met,
                SUM(CASE WHEN o.rag_status = 'red'   THEN 1 ELSE 0 END) AS red_count,
                SUM(CASE WHEN o.rag_status = 'amber' THEN 1 ELSE 0 END) AS amber_count,
                SUM(CASE WHEN o.rag_status = 'green' THEN 1 ELSE 0 END) AS green_count
            FROM observations o
            LEFT JOIN schools s ON s.id = o.school_id
            {where}
            GROUP BY o.school_id, s.name
            ORDER BY pct_met DESC
            LIMIT :limit OFFSET :offset
        """
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        return [dict(r) for r in rows], len(rows)

    # ── 15. Department Comparison ─────────────────────────────────────────────
    async def _report_department_comparison(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "o")
        dc, dp = _date_clause(flt, "o.submitted_at")
        offset, limit = _offset_limit(flt)
        params = {**sp, **dp, "limit": limit, "offset": offset}
        where = _build_where([sc, dc])
        sql = f"""
            SELECT
                o.department_id,
                d.name   AS department_name,
                o.school_id,
                s.name   AS school_name,
                COUNT(*) AS total_obs,
                ROUND(100.0 * SUM(CASE WHEN o.auto_result = 'met' THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2) AS pct_met
            FROM observations o
            LEFT JOIN departments d ON d.id = o.department_id
            LEFT JOIN schools s ON s.id = o.school_id
            {where}
            GROUP BY o.department_id, d.name, o.school_id, s.name
            ORDER BY pct_met DESC
            LIMIT :limit OFFSET :offset
        """
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        return [dict(r) for r in rows], len(rows)

    # ── 16. Escalation Summary ────────────────────────────────────────────────
    async def _report_escalation_summary(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "t")
        offset, limit = _offset_limit(flt)
        params = {**sp, "limit": limit, "offset": offset}
        where = _build_where([sc, "te.status = 'open'"])
        sql = f"""
            SELECT
                te.id,
                te.task_id,
                tsk.title  AS task_title,
                tsk.school_id,
                s.name     AS school_name,
                tsk.department_id,
                d.name     AS department_name,
                te.escalation_level,
                te.trigger,
                te.escalated_at,
                EXTRACT(EPOCH FROM (NOW() - te.escalated_at)) / 3600 AS age_hours,
                te.status
            FROM task_escalations te
            JOIN tasks tsk ON tsk.id = te.task_id
            JOIN tasks t ON t.id = te.task_id
            LEFT JOIN schools s ON s.id = tsk.school_id
            LEFT JOIN departments d ON d.id = tsk.department_id
            {where}
            ORDER BY te.escalation_level DESC, te.escalated_at ASC
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"""
            SELECT COUNT(*) FROM task_escalations te
            JOIN tasks t ON t.id = te.task_id
            {where}
        """
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 17. Inventory ─────────────────────────────────────────────────────────
    async def _report_inventory(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "a")
        offset, limit = _offset_limit(flt)
        params = {**sp, "limit": limit, "offset": offset}
        where = _build_where([sc])
        sql = f"""
            SELECT
                a.id,
                a.name,
                a.category_code,
                a.school_id,
                s.name    AS school_name,
                a.status,
                a.created_at,
                a.updated_at
            FROM assets a
            LEFT JOIN schools s ON s.id = a.school_id
            {where}
            ORDER BY a.name
            LIMIT :limit OFFSET :offset
        """
        count_sql = f"SELECT COUNT(*) FROM assets a {where}"
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        total = (await self.db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})).scalar_one()
        return [dict(r) for r in rows], int(total)

    # ── 18. Vendor (Phase 2 placeholder) ─────────────────────────────────────
    async def _report_vendor(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        return [{"message": "Vendor report is planned for Phase 2"}], 0

    # ── 19. Compliance Dashboard Export ───────────────────────────────────────
    async def _report_compliance_dashboard(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        sc, sp = _school_clause(tenant, "co")
        dc, dp = _date_clause(flt, "co.due_at")
        params = {**sp, **dp}
        where = _build_where([sc, dc])
        sql = f"""
            SELECT
                co.school_id,
                s.name                AS school_name,
                COUNT(*)              AS total_due,
                SUM(CASE WHEN co.compliance_status = 'submitted'    THEN 1 ELSE 0 END) AS submitted,
                SUM(CASE WHEN co.compliance_status = 'closed_missed' THEN 1 ELSE 0 END) AS missed,
                SUM(CASE WHEN co.compliance_status = 'open'          THEN 1 ELSE 0 END) AS open_pending,
                ROUND(
                    100.0 * SUM(CASE WHEN co.compliance_status = 'submitted' THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0), 2
                ) AS pct_compliance
            FROM compliance_observations co
            LEFT JOIN schools s ON s.id = co.school_id
            {where}
            GROUP BY co.school_id, s.name
            ORDER BY pct_compliance ASC
        """
        rows = (await self.db.execute(text(sql), params)).mappings().fetchall()
        return [dict(r) for r in rows], len(rows)

    # ── 20. Trend Analysis ────────────────────────────────────────────────────
    async def _report_trend_analysis(
        self, flt: ReportFilter, tenant: TenantContext
    ) -> tuple[List[Dict], int]:
        # Re-uses kpi_trend logic — separate entry keeps the catalogue complete
        return await self._report_kpi_trend(flt, tenant)

