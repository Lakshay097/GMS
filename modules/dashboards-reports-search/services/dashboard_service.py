"""
Role-based dashboard service — PRS §30-31, Permission Matrix §12.

Each role sees a different widget set:
  SuperAdmin  — all widgets, cross-school
  Admin       — all widgets, scoped to school
  Checker     — KPI summary (own dept), task summary (own), compliance summary
  Auditor     — KPI summary, audit queue, discrepancy summary, escalation summary
  Viewer      — KPI summary, compliance summary, scorecard summary (read-only)

Permissions are NOT rechecked here — the route layer already enforces
DASHBOARD.VIEW via require_permission(). The service only shapes the response.

All queries run against the read-replica session (get_read_db).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.dashboards_reports_search.schemas import (
    ComplianceSummaryWidget,
    DashboardResponse,
    DiscrepancySummaryWidget,
    EscalationSummaryWidget,
    FrequencyPeriodProgress,
    FrequencyProgressWidget,
    SchoolFrequencyRow,
    KpiSummaryWidget,
    RagDistributionWidget,
    RecentActivityItem,
    TaskSummaryWidget,
)
from shared.middleware.tenancy import TenantContext


def _role(tenant: TenantContext) -> str:
    order = ["superadmin", "admin", "dept_head", "auditor", "checker", "viewer"]
    lower = [r.lower() for r in tenant.roles]
    for r in order:
        if r in lower:
            return r
    return "viewer"


def _school_filter(tenant: TenantContext, alias: str = "") -> tuple[str, Dict]:
    col = f"{alias}.school_id" if alias else "school_id"
    r = _role(tenant)
    if r == "superadmin":
        return "TRUE", {}
    if r == "viewer" and tenant.accessible_school_ids:
        return f"{col} = ANY(:school_ids)", {"school_ids": tenant.accessible_school_ids}
    if tenant.school_id:
        return f"{col} = :school_id", {"school_id": tenant.school_id}
    return "FALSE", {}


def _dept_filter(tenant: TenantContext, alias: str = "") -> tuple[str, Dict]:
    if tenant.department_id:
        col = f"{alias}.department_id" if alias else "department_id"
        return f"{col} = :dept_id", {"dept_id": tenant.department_id}
    return "TRUE", {}


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_dashboard(self, tenant: TenantContext) -> DashboardResponse:
        print(f"DashboardService.get_dashboard called for user {tenant.user_id}")
        role = _role(tenant)
        print(f"User role: {role}")
        try:
            school_id = UUID(tenant.school_id) if tenant.school_id else None
        except (ValueError, TypeError):
            school_id = None
        try:
            dept_id = UUID(tenant.department_id) if tenant.department_id else None
        except (ValueError, TypeError):
            dept_id = None

        kpi_widget = compliance_widget = task_widget = None
        disc_widget = esc_widget = rag_widget = freq_widget = None
        recent_activity: Optional[List[RecentActivityItem]] = None
        pending_my_action: Optional[List[Dict[str, Any]]] = None

        # Try to load widgets gracefully
        try:
            if role in ("superadmin", "admin", "dept_head", "checker", "auditor", "viewer"):
                try:
                    kpi_widget = await self._kpi_summary(tenant)
                except Exception as e:
                    print(f"KPI summary failed: {e}")
                try:
                    compliance_widget = await self._compliance_summary(tenant)
                except Exception as e:
                    print(f"Compliance summary failed: {e}")

            if role in ("superadmin", "admin", "dept_head", "checker"):
                try:
                    task_widget = await self._task_summary(tenant)
                except Exception as e:
                    print(f"Task summary failed: {e}")
                try:
                    pending_my_action = await self._pending_my_action(tenant)
                except Exception as e:
                    print(f"Pending action failed: {e}")

            if role in ("superadmin", "admin", "auditor"):
                try:
                    disc_widget = await self._discrepancy_summary(tenant)
                except Exception as e:
                    print(f"Discrepancy summary failed: {e}")
                try:
                    esc_widget = await self._escalation_summary(tenant)
                except Exception as e:
                    print(f"Escalation summary failed: {e}")

            if role in ("superadmin", "admin", "viewer"):
                try:
                    rag_widget = await self._rag_distribution(tenant)
                except Exception as e:
                    print(f"RAG distribution failed: {e}")

            if role in ("superadmin", "admin", "dept_head", "checker", "auditor", "viewer"):
                try:
                    freq_widget = await self._frequency_progress(tenant)
                except Exception as e:
                    print(f"Frequency progress failed: {e}")

            if role in ("superadmin", "admin"):
                try:
                    recent_activity = await self._recent_activity(tenant)
                except Exception as e:
                    print(f"Recent activity failed: {e}")
        except Exception as e:
            print(f"General dashboard widget error: {e}")

        print(f"Dashboard response prepared for user {tenant.user_id}")
        return DashboardResponse(
            role=role,
            school_id=school_id,
            department_id=dept_id,
            generated_at=datetime.now(timezone.utc),
            kpi_summary=kpi_widget,
            compliance_summary=compliance_widget,
            task_summary=task_widget,
            discrepancy_summary=disc_widget,
            escalation_summary=esc_widget,
            rag_distribution=rag_widget,
            frequency_progress=freq_widget,
            recent_activity=recent_activity,
            pending_my_action=pending_my_action,
        )

    # ── Widgets ────────────────────────────────────────────────────────────────

    async def _kpi_summary(self, tenant: TenantContext) -> KpiSummaryWidget:
        sf, sp = _school_filter(tenant, "o")
        df, dp = _dept_filter(tenant, "o")
        params = {**sp, **dp}
        result = await self.db.execute(
            text(f"""
                SELECT
                    COUNT(*)                                                        AS total,
                    SUM(CASE WHEN o.auto_result = 'met'     THEN 1 ELSE 0 END)     AS met,
                    SUM(CASE WHEN o.auto_result = 'not_met' THEN 1 ELSE 0 END)     AS not_met,
                    SUM(CASE WHEN o.rag_status  = 'amber'   THEN 1 ELSE 0 END)     AS amber
                FROM observations o
                WHERE {sf} AND {df}
                  AND o.submitted_at >= NOW() - INTERVAL '30 days'
            """),
            params,
        )
        row = result.fetchone()
        total = int(row.total or 0)
        met = int(row.met or 0)
        return KpiSummaryWidget(
            total_kpis=total,
            met=met,
            not_met=int(row.not_met or 0),
            amber=int(row.amber or 0),
            pct_met=round(100.0 * met / max(total, 1), 2),
        )

    async def _compliance_summary(self, tenant: TenantContext) -> ComplianceSummaryWidget:
        sf, sp = _school_filter(tenant, "co")
        df, dp = _dept_filter(tenant, "co")
        params = {**sp, **dp}
        result = await self.db.execute(
            text(f"""
                SELECT
                    COUNT(*)                                                                    AS total,
                    SUM(CASE WHEN co.compliance_status = 'submitted'     THEN 1 ELSE 0 END)   AS submitted,
                    SUM(CASE WHEN co.compliance_status = 'closed_missed' THEN 1 ELSE 0 END)   AS missed,
                    SUM(CASE WHEN co.submitted_at > co.due_at            THEN 1 ELSE 0 END)   AS late
                FROM compliance_observations co
                WHERE {sf} AND {df}
                  AND co.due_at >= NOW() - INTERVAL '30 days'
            """),
            params,
        )
        row = result.fetchone()
        total = int(row.total or 0)
        submitted = int(row.submitted or 0)
        return ComplianceSummaryWidget(
            total_due=total,
            submitted=submitted,
            missed=int(row.missed or 0),
            late=int(row.late or 0),
            pct_submitted=round(100.0 * submitted / max(total, 1), 2),
        )

    async def _task_summary(self, tenant: TenantContext) -> TaskSummaryWidget:
        sf, sp = _school_filter(tenant, "t")
        df, dp = _dept_filter(tenant, "t")
        user_filter = ""
        if _role(tenant) == "checker":
            user_filter = "AND EXISTS (SELECT 1 FROM task_owners tow WHERE tow.task_id = t.id AND tow.user_id = :uid)"
            sp["uid"] = tenant.user_id
        params = {**sp, **dp}
        result = await self.db.execute(
            text(f"""
                SELECT
                    SUM(CASE WHEN t.status = 'open'       THEN 1 ELSE 0 END) AS open_tasks,
                    SUM(CASE WHEN t.eta < NOW() AND t.status NOT IN ('completed','cancelled')
                              THEN 1 ELSE 0 END)                              AS overdue,
                    SUM(CASE WHEN t.status = 'completed'
                              AND t.completed_at >= NOW() - INTERVAL '30 days'
                              THEN 1 ELSE 0 END)                              AS completed_period,
                    SUM(CASE WHEN t.status = 'completed'
                              AND t.completed_at <= t.eta
                              THEN 1 ELSE 0 END)                              AS on_time,
                    SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END)  AS total_completed
                FROM tasks t
                WHERE {sf} AND {df} {user_filter}
            """),
            params,
        )
        row = result.fetchone()
        tc = int(row.total_completed or 0)
        ot = int(row.on_time or 0)
        return TaskSummaryWidget(
            open_tasks=int(row.open_tasks or 0),
            overdue_tasks=int(row.overdue or 0),
            completed_this_period=int(row.completed_period or 0),
            pct_on_time=round(100.0 * ot / max(tc, 1), 2),
        )

    async def _discrepancy_summary(self, tenant: TenantContext) -> DiscrepancySummaryWidget:
        sf, sp = _school_filter(tenant, "disc")
        result = await self.db.execute(
            text(f"""
                SELECT
                    SUM(CASE WHEN disc.state = 'raised'               THEN 1 ELSE 0 END) AS raised,
                    SUM(CASE WHEN disc.state = 'under_investigation'   THEN 1 ELSE 0 END) AS investigating,
                    SUM(CASE WHEN disc.state LIKE 'pending_approval%%' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN disc.state = 'closed'
                              AND disc.closed_at >= NOW() - INTERVAL '30 days'
                              THEN 1 ELSE 0 END)                                          AS resolved_period,
                    SUM(CASE WHEN disc.state NOT IN ('closed')
                              AND EXTRACT(EPOCH FROM (NOW() - disc.raised_at)) / 3600 > 72
                              THEN 1 ELSE 0 END)                                          AS sla_breached
                FROM discrepancies disc
                WHERE {sf}
            """),
            sp,
        )
        row = result.fetchone()
        return DiscrepancySummaryWidget(
            open_discrepancies=int((row.raised or 0) + (row.investigating or 0) + (row.pending or 0)),
            under_investigation=int(row.investigating or 0),
            pending_approval=int(row.pending or 0),
            resolved_this_period=int(row.resolved_period or 0),
            breached_sla=int(row.sla_breached or 0),
        )

    async def _escalation_summary(self, tenant: TenantContext) -> EscalationSummaryWidget:
        sf, sp = _school_filter(tenant, "t")
        result = await self.db.execute(
            text(f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN te.acknowledged_at IS NOT NULL THEN 1 ELSE 0 END) AS acknowledged,
                    te.escalation_level,
                    COUNT(*) AS level_count
                FROM task_escalations te
                JOIN tasks t ON t.id = te.task_id
                WHERE te.status = 'open' AND {sf}
                GROUP BY te.escalation_level
            """),
            sp,
        )
        rows = result.fetchall()
        total = sum(r.level_count for r in rows)
        ack = sum(r.acknowledged for r in rows)
        by_level = [{"level": r.escalation_level, "count": r.level_count} for r in rows]
        return EscalationSummaryWidget(
            open_escalations=total,
            acknowledged=ack,
            by_level=by_level,
        )

    async def _rag_distribution(self, tenant: TenantContext) -> RagDistributionWidget:
        sf, sp = _school_filter(tenant, "o")
        result = await self.db.execute(
            text(f"""
                SELECT
                    SUM(CASE WHEN o.rag_status = 'green'         THEN 1 ELSE 0 END) AS green,
                    SUM(CASE WHEN o.rag_status = 'amber'         THEN 1 ELSE 0 END) AS amber,
                    SUM(CASE WHEN o.rag_status = 'red'           THEN 1 ELSE 0 END) AS red,
                    SUM(CASE WHEN o.rag_status = 'not_submitted' THEN 1 ELSE 0 END) AS not_submitted
                FROM observations o
                WHERE {sf}
                  AND o.submitted_at >= NOW() - INTERVAL '30 days'
            """),
            sp,
        )
        row = result.fetchone()
        return RagDistributionWidget(
            green=int(row.green or 0),
            amber=int(row.amber or 0),
            red=int(row.red or 0),
            not_submitted=int(row.not_submitted or 0),
        )

    async def _recent_activity(self, tenant: TenantContext) -> List[RecentActivityItem]:
        sf, sp = _school_filter(tenant, "ale")
        result = await self.db.execute(
            text(f"""
                SELECT
                    ale.entity_type,
                    ale.entity_id,
                    ale.action,
                    u.full_name AS actor_name,
                    ale.timestamp
                FROM audit_log_entries ale
                LEFT JOIN users u ON u.id = ale.user_id
                WHERE {sf}
                ORDER BY ale.timestamp DESC
                LIMIT 20
            """),
            sp,
        )
        return [
            RecentActivityItem(
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                action=r.action,
                actor_name=r.actor_name or "System",
                timestamp=r.timestamp,
            )
            for r in result.fetchall()
        ]

    async def _frequency_progress(self, tenant: TenantContext) -> FrequencyProgressWidget:
        """
        Frequency-aware progress: for each frequency band, count active KPIs
        and how many have been submitted in the current period.

        Period boundaries mirror DailyKpiInput.getPeriodStart():
          daily   → today
          weekly  → Monday–Sunday (ISO week)
          monthly → 1st–last of month
          quarterly → quarter start–end
          half_yearly → Jan–Jun or Jul–Dec
          annual  → Jan 1–Dec 31
        """
        from datetime import date  # local names kept for the method body

        # KPIs and KRAs carry no school_id — school scoping flows through
        # department_kpi_assignments → departments.school_id (same pattern
        # as summary_service._assignments).
        sf, sp = _school_filter(tenant, "d")
        params = dict(sp)

        is_superadmin = _role(tenant) == "superadmin"

        kpi_result = await self.db.execute(
            text(f"""
                SELECT DISTINCT k.kpi_id, k.frequency_code, kr.name AS kra_name,
                       s.id AS school_id, s.name AS school_name
                FROM kpis k
                JOIN department_kpi_assignments a ON a.kpi_id = k.kpi_id
                JOIN departments d ON d.id = a.department_id AND d.status = 'active'
                LEFT JOIN kras kr ON kr.id = k.kra_id
                JOIN schools s ON s.id = d.school_id
                WHERE k.status = 'active' AND {sf}
            """),
            params,
        )
        kpi_rows = kpi_result.fetchall()

        if not kpi_rows:
            return FrequencyProgressWidget(
                periods=[],
                overall_submitted=0,
                overall_total=0,
                overall_pct=0.0,
            )

        # 2. Group KPIs by frequency, tracking KRA names and (for superadmins)
        #    per-school membership so the widget can show a breakdown row per school.
        from collections import defaultdict
        freq_kpis: dict[str, list] = defaultdict(list)
        freq_kras: dict[str, set] = defaultdict(set)
        freq_schools: dict[str, dict[str, str]] = defaultdict(dict)  # freq -> school_id -> name
        for row in kpi_rows:
            freq = row.frequency_code or "daily"
            freq_kpis[freq].append(str(row.kpi_id))
            if row.kra_name:
                freq_kras[freq].add(row.kra_name)
            if is_superadmin and row.school_id:
                freq_schools[freq][str(row.school_id)] = row.school_name

        # 3. For each frequency, compute period boundaries and count submissions
        today = date.today()
        periods: list[FrequencyPeriodProgress] = []
        total_all = 0
        submitted_all = 0

        # Frequency ordering and labels
        freq_order = [
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("half_yearly", "Half-Yearly"),
            ("annual", "Annual"),
        ]

        for freq_code, label in freq_order:
            kpi_ids = freq_kpis.get(freq_code, [])
            if not kpi_ids:
                continue

            period_start, period_end = self._compute_period(freq_code, today)

            # Count observations submitted for these KPIs within the current period.
            # Scope must mirror the KPI totals above (_school_filter): a superadmin
            # with a school on their profile still sees system-wide KPI totals here,
            # so their submitted counts must not be quietly narrowed to that school
            # (that split-brain made the Monthly card disagree with the audit picker).
            osf, osp = _school_filter(tenant, "o")
            obs_params = {
                "kpi_ids": kpi_ids,
                "period_start": period_start,
                "period_end": period_end,
                **osp,
            }
            result = await self.db.execute(
                text(f"""
                    SELECT COUNT(DISTINCT o.kpi_id) AS submitted_count
                    FROM observations o
                    WHERE o.kpi_id = ANY(:kpi_ids)
                      AND o.submitted_at >= :period_start
                      AND o.submitted_at < :period_end
                      AND {osf}
                """),
                obs_params,
            )
            row = result.fetchone()
            submitted = int(row.submitted_count or 0)
            total = len(kpi_ids)
            pending = total - submitted
            pct = round(100.0 * submitted / max(total, 1), 2)

            # Per-school breakdown (superadmin only). Submitted counts group by
            # the observation's own school over the whole system (the band's
            # aggregate uses the same TRUE scope) so the rows reconcile with
            # `submitted` above; the school set is assignment schools ∪ schools
            # that actually submitted, so a submission is never invisible in
            # the breakdown. `total` per school = band KPIs assigned to it.
            school_rows: list[SchoolFrequencyRow] = []
            if is_superadmin and freq_schools.get(freq_code):
                srow_result = await self.db.execute(
                    text(f"""
                        SELECT o.school_id,
                               COUNT(DISTINCT o.kpi_id) AS submitted_count
                        FROM observations o
                        WHERE o.kpi_id = ANY(:kpi_ids)
                          AND o.submitted_at >= :period_start
                          AND o.submitted_at < :period_end
                        GROUP BY o.school_id
                    """),
                    {
                        "kpi_ids": kpi_ids,
                        "period_start": period_start,
                        "period_end": period_end,
                    },
                )
                submitted_by_school: dict[str, int] = {
                    str(r.school_id): int(r.submitted_count or 0)
                    for r in srow_result.fetchall()
                }
                all_school_ids = set(freq_schools[freq_code]) | set(submitted_by_school)
                # Resolve names for schools known only through submissions.
                unnamed = all_school_ids - set(freq_schools[freq_code])
                if unnamed:
                    name_res = await self.db.execute(
                        text("SELECT s.id, s.name FROM schools s WHERE s.id = ANY(:sids)"),
                        {"sids": list(unnamed)},
                    )
                    for r in name_res.fetchall():
                        freq_schools[freq_code][str(r.id)] = r.name
                band_kpi_rows = [r for r in kpi_rows if (r.frequency_code or "daily") == freq_code]
                for sid in sorted(all_school_ids):
                    s_name = freq_schools[freq_code].get(sid)
                    if s_name is None:
                        # Submission from a school with no band assignments —
                        # keep the row so the breakdown sums to the aggregate.
                        s_name = f"School {sid[:8]}"
                    s_total = sum(1 for r in band_kpi_rows if str(r.school_id) == sid)
                    s_submitted = submitted_by_school.get(sid, 0)
                    school_rows.append(SchoolFrequencyRow(
                        school_id=UUID(sid),
                        school_name=s_name,
                        total_kpis=s_total,
                        submitted=s_submitted,
                        pct_complete=round(100.0 * s_submitted / max(s_total, 1), 2),
                    ))

            periods.append(FrequencyPeriodProgress(
                frequency=freq_code,
                label=label,
                total_kpis=total,
                submitted=submitted,
                pending=pending,
                pct_complete=pct,
                period_start=period_start.isoformat(),
                period_end=period_end.isoformat(),
                kra_names=sorted(freq_kras.get(freq_code, set())),
                schools=school_rows,
            ))
            total_all += total
            submitted_all += submitted

        return FrequencyProgressWidget(
            periods=periods,
            overall_submitted=submitted_all,
            overall_total=total_all,
            overall_pct=round(100.0 * submitted_all / max(total_all, 1), 2),
        )

    @staticmethod
    def _compute_period(freq_code: str, today: date) -> tuple[date, date]:
        """Compute (period_start, period_end) for the current frequency band."""
        if freq_code == "daily":
            return today, today + timedelta(days=1)

        if freq_code == "weekly":
            # Monday to Sunday (ISO week)
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=7)
            return monday, sunday

        if freq_code == "monthly":
            month_start = today.replace(day=1)
            if today.month == 12:
                month_end = today.replace(year=today.year + 1, month=1, day=1)
            else:
                month_end = today.replace(month=today.month + 1, day=1)
            return month_start, month_end

        if freq_code == "quarterly":
            quarter = (today.month - 1) // 3
            q_start_month = quarter * 3 + 1
            q_start = today.replace(month=q_start_month, day=1)
            # Add 3 months manually
            q_end_month = q_start_month + 3
            q_end_year = q_start.year
            if q_end_month > 12:
                q_end_month -= 12
                q_end_year += 1
            q_end = q_start.replace(year=q_end_year, month=q_end_month, day=1)
            return q_start, q_end

        if freq_code == "half_yearly":
            if today.month <= 6:
                return today.replace(month=1, day=1), today.replace(month=7, day=1)
            else:
                return today.replace(month=7, day=1), today.replace(year=today.year + 1, month=1, day=1)

        if freq_code == "annual":
            return today.replace(month=1, day=1), today.replace(year=today.year + 1, month=1, day=1)

        # Fallback: daily
        return today, today + timedelta(days=1)

    async def _pending_my_action(self, tenant: TenantContext) -> List[Dict[str, Any]]:
        """Tasks where the user is an owner and status is open."""
        result = await self.db.execute(
            text("""
                SELECT t.id, t.title, t.status, t.eta, t.school_id
                FROM tasks t
                JOIN task_owners tow ON tow.task_id = t.id
                WHERE tow.user_id = :uid AND t.status = 'open'
                ORDER BY t.eta ASC
                LIMIT 10
            """),
            {"uid": tenant.user_id},
        )
        return [
            {"task_id": str(r.id), "title": r.title,
             "status": r.status, "eta": r.eta.isoformat() if r.eta else None}
            for r in result.fetchall()
        ]
