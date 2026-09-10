"""
Filterable dashboard summary — PRS §30.

GET /dashboard/summary?period=today|week|month|custom&date_from&date_to&school_id&department_id

One aggregate response that powers the redesigned dashboard:
  - KPI library totals (KRAs, KPIs, assigned/unassigned)
  - Entry rates: entered / missing / follow-up (cadence-based expectation)
  - Task pipeline: assigned, pending approval, completed, overdue, escalated
  - Trend buckets (daily for windows ≤ 31 days, weekly beyond)
  - Department / school breakdowns

Scoping: filters are clamped by role — a dept_head asking for another
school silently gets their own scope (echoed back in `filters`), never
cross-tenant data. The expected-entry model counts a period per assigned
KPI according to its frequency (daily = each day, weekly = each Monday,
monthly = each 1st, etc.) inside the window.
"""
from __future__ import annotations

import calendar
from datetime import date as date_type, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from modules.dashboards_reports_search.schemas import (
    DashboardSummaryMeta,
    DashboardSummaryResponse,
    DepartmentSummaryRow,
    KpiEntryRates,
    KpiLibraryTotals,
    SchoolSummaryRow,
    SummaryTrendPoint,
    TaskPipelineCounts,
)
from shared.middleware.tenancy import TenantContext

_ROLE_ORDER = ["superadmin", "admin", "dept_head", "auditor", "checker", "viewer"]

_PERIODS = ("today", "week", "month", "custom")


def _role(tenant: TenantContext) -> str:
    lower = [r.lower() for r in tenant.roles]
    for r in _ROLE_ORDER:
        if r in lower:
            return r
    return "viewer"


def _as_uuid(value: Optional[str]) -> Optional[str]:
    """Validate a UUID string; return None when absent/invalid."""
    if not value:
        return None
    try:
        import uuid
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _resolve_scope(
    tenant: TenantContext,
    school_id: Optional[str],
    department_id: Optional[str],
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Clamp requested school/department filters to what the role may see.
    Returns (school_id, department_id, applied_filter_names).
    """
    role = _role(tenant)
    applied: List[str] = []
    req_school = _as_uuid(school_id)
    req_dept = _as_uuid(department_id)

    if role == "superadmin":
        # Sees everything; explicit filters honoured.
        if req_school:
            applied.append("school")
        if req_dept:
            applied.append("department")
        return req_school, req_dept, applied

    # Everyone else is pinned to their own school (or the viewer's grants).
    own_school = tenant.school_id
    if not own_school and tenant.accessible_school_ids:
        own_school = tenant.accessible_school_ids[0]
    school = own_school
    if req_school and req_school == school:
        applied.append("school")

    dept = None
    if req_dept:
        if role in ("dept_head", "checker", "auditor"):
            # Department-scoped roles: only their own department.
            if req_dept == tenant.department_id:
                dept = req_dept
                applied.append("department")
            else:
                dept = tenant.department_id
                if tenant.department_id:
                    applied.append("department")
        else:
            dept = req_dept
            applied.append("department")
    elif role in ("dept_head", "checker") and tenant.department_id:
        dept = tenant.department_id

    return school, dept, applied


def _resolve_window(
    period: str,
    date_from: Optional[date_type],
    date_to: Optional[date_type],
) -> Tuple[date_type, date_type, str, List[str]]:
    """Resolve the selected period into an inclusive [start, end] date pair."""
    applied: List[str] = []
    today = datetime.utcnow().date()
    p = (period or "month").lower()

    if p == "today":
        return today, today, "today", applied
    if p == "week":
        start = today - timedelta(days=today.weekday())  # Monday
        return start, today, "week", applied
    if p == "custom" and date_from and date_to:
        applied += ["date_from", "date_to"]
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        return date_from, date_to, "custom", applied
    # Default: current calendar month.
    return today.replace(day=1), today, "month", applied


def _periods_in_window(freq: str, start: date_type, end: date_type) -> int:
    """How many submission slots a KPI of this frequency has in [start, end]."""
    days = (end - start).days + 1
    if days <= 0:
        return 0
    if freq == "daily":
        return days
    if freq == "weekly":
        # Number of Mondays in the window.
        return len([d for d in range(days) if (start + timedelta(days=d)).weekday() == 0])
    if freq == "monthly":
        # Number of 1st-of-month days in the window.
        count, d = 0, start
        while d <= end:
            if d.day == 1:
                count += 1
                # jump to next month's 1st
                if d.month == 12:
                    d = d.replace(year=d.year + 1, month=1, day=1)
                else:
                    d = d.replace(month=d.month + 1, day=1)
            else:
                d = d.replace(day=1)
                if d < start:
                    d = d.replace(day=calendar.monthrange(d.year, d.month)[1]) + timedelta(days=1)
        return count
    if freq == "quarterly":
        count, d = 0, start
        while d <= end:
            if d.day == 1 and d.month in (1, 4, 7, 10):
                count += 1
            d = _next_month_start(d)
        return count
    if freq == "half_yearly":
        count, d = 0, start
        while d <= end:
            if d.day == 1 and d.month in (1, 7):
                count += 1
            d = _next_month_start(d)
        return count
    if freq == "annual":
        count, d = 0, start
        while d <= end:
            if d.day == 1 and d.month == 1:
                count += 1
            d = d.replace(year=d.year + 1, month=1, day=1)
        return count
    return 0  # unknown frequency contributes no expectation


def _next_month_start(d: date_type) -> date_type:
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1)
    return d.replace(month=d.month + 1, day=1)


def _bucket_size(days: int) -> str:
    return "day" if days <= 31 else "week"


def _iter_buckets(start: date_type, end: date_type, size: str) -> List[Tuple[date_type, date_type]]:
    buckets: List[Tuple[date_type, date_type]] = []
    if size == "day":
        d = start
        while d <= end:
            buckets.append((d, d))
            d += timedelta(days=1)
    else:
        d = start
        while d <= end:
            bucket_end = min(d + timedelta(days=6), end)
            buckets.append((d, bucket_end))
            d = bucket_end + timedelta(days=1)
    return buckets


class DashboardSummaryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_summary(
        self,
        tenant: TenantContext,
        period: Optional[str],
        date_from: Optional[date_type],
        date_to: Optional[date_type],
        school_id: Optional[str],
        department_id: Optional[str],
    ) -> DashboardSummaryResponse:
        role = _role(tenant)
        eff_school, eff_dept, filters_applied = _resolve_scope(tenant, school_id, department_id)
        win_start, win_end, eff_period, p_applied = _resolve_window(period, date_from, date_to)
        filters_applied = p_applied + filters_applied

        window_days = (win_end - win_start).days + 1
        start_ts = datetime(win_start.year, win_start.month, win_start.day)
        end_ts = datetime(win_end.year, win_end.month, win_end.day) + timedelta(days=1)

        # ── Fire every independent read group concurrently ───────────────────
        # Each await is a ~1s cloud-DB round trip; sequential issue multiplied
        # latency by query count. One AsyncSession cannot run concurrent
        # queries, so each branch gets its own short-lived session.
        async def _branch(coro_factory):
            from shared.database import ReadReplicaSessionLocal
            async with ReadReplicaSessionLocal() as branch_db:
                return await coro_factory(branch_db)

        (assignments, kpi_library, obs, tasks,
         obs_trend, task_trend, by_department, by_school) = await asyncio.gather(
            _branch(lambda db: self._assignments(eff_school, eff_dept, db=db)),
            _branch(lambda db: self._kpi_library(db=db)),
            _branch(lambda db: self._entry_counts(eff_school, eff_dept, start_ts, end_ts, db=db)),
            _branch(lambda db: self._task_counts(eff_school, eff_dept, start_ts, end_ts, db=db)),
            _branch(lambda db: self._trend_counts("observations", "submitted_at", eff_school, eff_dept, start_ts, end_ts, db=db)),
            _branch(lambda db: self._trend_counts("tasks", "completed_at", eff_school, eff_dept, start_ts, end_ts, db=db)),
            _branch(lambda db: self._by_department(eff_school, eff_dept, win_start, win_end, start_ts, end_ts, role, db=db)),
            (_branch(lambda db: self._by_school(win_start, win_end, start_ts, end_ts, db=db))
             if role == "superadmin" and not eff_school else self._noop()),
        )

        # ── Entry rates ─────────────────────────────────────────────────────
        expected = 0
        for a in assignments:
            expected += _periods_in_window(a["frequency"], win_start, win_end)
        entered = obs["entered"]
        missing = max(expected - entered, 0)
        entry_rates = KpiEntryRates(
            expected_entries=expected,
            entered=entered,
            missing=missing,
            late=obs["late"],
            follow_up=obs["follow_up"],
            entered_rate=self._pct(entered, expected),
            missing_rate=self._pct(missing, expected),
            follow_up_rate=self._pct(obs["follow_up"], entered),
        )

        # ── Trend (data fetched in the gather above) ─────────────────────────
        size = _bucket_size(window_days)
        trend = self._build_trend(
            win_start, win_end, size, obs_trend, task_trend, assignments)

        return DashboardSummaryResponse(
            role=role,
            generated_at=datetime.utcnow(),
            filters=DashboardSummaryMeta(
                period=eff_period,
                date_from=win_start,
                date_to=win_end,
                school_id=_as_uuid(eff_school),
                department_id=_as_uuid(eff_dept),
                filters_applied=filters_applied,
            ),
            kpi_library=kpi_library,
            entries=entry_rates,
            tasks=TaskPipelineCounts(**tasks),
            trend=trend,
            by_department=by_department if by_department else None,
            by_school=by_school,
        )

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    async def _noop() -> None:
        """Gather placeholder for an optional breakdown that doesn't apply."""

    @staticmethod
    def _pct(part: int, whole: int) -> float:
        if whole <= 0:
            return 0.0
        return round(min(100.0, 100.0 * part / whole), 1)

    async def _assignments(self, school: Optional[str], dept: Optional[str], *, db: Optional[AsyncSession] = None) -> List[Dict[str, Any]]:
        db = db or self.db
        """Active KPI assignments (dept, school, frequency) within scope."""
        params: Dict[str, Any] = {}
        where = ["k.status = 'active'", "d.status = 'active'"]
        if dept:
            where.append("a.department_id = :dept")
            params["dept"] = dept
        elif school:
            where.append("d.school_id = :school")
            params["school"] = school
        rows = await db.execute(
            text(f"""
                SELECT a.department_id, d.school_id, k.frequency_code
                FROM department_kpi_assignments a
                JOIN kpis k ON k.kpi_id = a.kpi_id
                JOIN departments d ON d.id = a.department_id
                WHERE {' AND '.join(where)}
            """),
            params,
        )
        return [
            {"department_id": str(r.department_id), "school_id": str(r.school_id),
             "frequency": r.frequency_code or "daily"}
            for r in rows.fetchall()
        ]

    async def _kpi_library(self, *, db: Optional[AsyncSession] = None) -> KpiLibraryTotals:
        db = db or self.db
        kras = (await db.execute(
            text("SELECT COUNT(*) FROM kras WHERE status = 'active'"))).scalar() or 0
        kpis = (await db.execute(
            text("SELECT COUNT(*) FROM kpis WHERE status = 'active'"))).scalar() or 0
        assigned = (await db.execute(
            text("""
                SELECT COUNT(DISTINCT a.kpi_id) FROM department_kpi_assignments a
                JOIN kpis k ON k.kpi_id = a.kpi_id AND k.status = 'active'
            """))).scalar() or 0
        total = int(kpis)
        return KpiLibraryTotals(
            total_kras=int(kras),
            total_kpis=total,
            assigned_kpis=int(assigned),
            unassigned_kpis=max(total - int(assigned), 0),
        )

    async def _entry_counts(
        self, school: Optional[str], dept: Optional[str],
        start_ts: datetime, end_ts: datetime,
        *, db: Optional[AsyncSession] = None,
    ) -> Dict[str, int]:
        db = db or self.db
        params: Dict[str, Any] = {"start": start_ts, "end": end_ts}
        where = ["o.submitted_at >= :start", "o.submitted_at < :end"]
        if dept:
            where.append("o.department_id = :dept")
            params["dept"] = dept
        elif school:
            where.append("o.school_id = :school")
            params["school"] = school
        row = (await db.execute(
            text(f"""
                SELECT COUNT(*)                                       AS entered,
                       SUM(CASE WHEN o.is_late THEN 1 ELSE 0 END)     AS late,
                       SUM(CASE WHEN o.rag_status = 'amber' THEN 1 ELSE 0 END) AS follow_up
                FROM observations o
                WHERE {' AND '.join(where)}
            """),
            params,
        )).fetchone()
        return {
            "entered": int(row.entered or 0),
            "late": int(row.late or 0),
            "follow_up": int(row.follow_up or 0),
        }

    async def _task_counts(
        self, school: Optional[str], dept: Optional[str],
        start_ts: datetime, end_ts: datetime,
        *, db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        db = db or self.db
        params: Dict[str, Any] = {"start": start_ts, "end": end_ts, "now": datetime.utcnow()}
        where = ["1=1"]
        if dept:
            where.append("t.department_id = :dept")
            params["dept"] = dept
        elif school:
            where.append("t.school_id = :school")
            params["school"] = school
        w = " AND ".join(where)
        row = (await db.execute(
            text(f"""
                SELECT
                    SUM(CASE WHEN t.status IN ('open','in_progress') THEN 1 ELSE 0 END) AS assigned_open,
                    SUM(CASE WHEN t.status = 'pending_approval' THEN 1 ELSE 0 END)      AS pending_approval,
                    SUM(CASE WHEN t.status = 'escalated' THEN 1 ELSE 0 END)             AS escalated_now,
                    SUM(CASE WHEN t.status NOT IN ('completed','cancelled')
                              AND t.eta < :now THEN 1 ELSE 0 END)                       AS overdue,
                    SUM(CASE WHEN t.status = 'completed'
                              AND t.completed_at >= :start AND t.completed_at < :end
                              THEN 1 ELSE 0 END)                                        AS completed_period,
                    SUM(CASE WHEN t.status = 'completed'
                              AND t.completed_at >= :start AND t.completed_at < :end
                              AND t.completed_at <= t.eta THEN 1 ELSE 0 END)            AS on_time
                FROM tasks t
                WHERE {w}
            """),
            params,
        )).fetchone()
        completed = int(row.completed_period or 0)
        on_time = int(row.on_time or 0)
        return {
            "assigned_open": int(row.assigned_open or 0),
            "pending_approval": int(row.pending_approval or 0),
            "completed": completed,
            "overdue": int(row.overdue or 0),
            "escalated": int(row.escalated_now or 0),
            "on_time_rate": self._pct(on_time, completed),
        }

    async def _trend_counts(
        self, table: str, ts_col: str,
        school: Optional[str], dept: Optional[str],
        start_ts: datetime, end_ts: datetime,
        *, db: Optional[AsyncSession] = None,
    ) -> Dict[str, int]:
        db = db or self.db
        assert table in ("observations", "tasks")
        assert ts_col in ("submitted_at", "completed_at")
        params: Dict[str, Any] = {"start": start_ts, "end": end_ts}
        where = [f"{ts_col} >= :start", f"{ts_col} < :end"]
        if dept:
            where.append("department_id = :dept")
            params["dept"] = dept
        elif school:
            where.append("school_id = :school")
            params["school"] = school
        rows = await db.execute(
            text(f"""
                SELECT ({ts_col})::date AS d, COUNT(*) AS c
                FROM {table}
                WHERE {' AND '.join(where)}
                GROUP BY 1 ORDER BY 1
            """),
            params,
        )
        return {str(r.d): int(r.c) for r in rows.fetchall()}

    def _build_trend(
        self,
        start: date_type, end: date_type, size: str,
        obs: Dict[str, int], tasks: Dict[str, int],
        assignments: List[Dict[str, Any]],
    ) -> List[SummaryTrendPoint]:
        points: List[SummaryTrendPoint] = []
        for b_start, b_end in _iter_buckets(start, end, size):
            days = (b_end - b_start).days + 1
            entered = 0
            d = b_start
            while d <= b_end:
                entered += obs.get(str(d), 0)
                d += timedelta(days=1)
            expected = 0
            for a in assignments:
                expected += _periods_in_window(a["frequency"], b_start, b_end)
            completed = 0
            d = b_start
            while d <= b_end:
                completed += tasks.get(str(d), 0)
                d += timedelta(days=1)
            points.append(SummaryTrendPoint(
                label=b_start.strftime("%d %b") if size == "day" else f"WK {b_start.strftime('%d %b')}",
                date=b_start,
                entered=entered,
                missing=max(expected - entered, 0),
                tasks_completed=completed,
            ))
        return points

    async def _by_department(
        self,
        school: Optional[str], dept: Optional[str],
        win_start: date_type, win_end: date_type,
        start_ts: datetime, end_ts: datetime,
        role: str,
        *, db: Optional[AsyncSession] = None,
    ) -> List[DepartmentSummaryRow]:
        db = db or self.db
        """Per-department entry performance within scope."""
        params: Dict[str, Any] = {"start": start_ts, "end": end_ts}
        where = ["d.status = 'active'"]
        if dept:
            where.append("d.id = :dept")
            params["dept"] = dept
        elif school:
            where.append("d.school_id = :school")
            params["school"] = school
        elif role != "superadmin":
            return []
        dep_rows = (await db.execute(
            text(f"""
                SELECT d.id, d.name FROM departments d
                WHERE {' AND '.join(where)}
                ORDER BY d.name
            """),
            params,
        )).fetchall()
        if not dep_rows:
            return []

        # entered per department
        entered_params: Dict[str, Any] = {"start": start_ts, "end": end_ts}
        entered_where = ["o.submitted_at >= :start", "o.submitted_at < :end"]
        if dept:
            entered_where.append("o.department_id = :dept")
            entered_params["dept"] = dept
        elif school:
            entered_where.append("o.school_id = :school")
            entered_params["school"] = school
        entered_rows = await db.execute(
            text(f"""
                SELECT o.department_id AS did, COUNT(*) AS c
                FROM observations o
                WHERE {' AND '.join(entered_where)}
                GROUP BY 1
            """),
            entered_params,
        )
        entered_map = {str(r.did): int(r.c) for r in entered_rows.fetchall()}

        # assignment counts per department (for expectation)
        assign_rows = await db.execute(
            text("""
                SELECT a.department_id AS did, k.frequency_code AS freq
                FROM department_kpi_assignments a
                JOIN kpis k ON k.kpi_id = a.kpi_id AND k.status = 'active'
                JOIN departments d ON d.id = a.department_id AND d.status = 'active'
            """)
        )
        expected_map: Dict[str, int] = {}
        assigned_map: Dict[str, int] = {}
        for r in assign_rows.fetchall():
            key = str(r.did)
            assigned_map[key] = assigned_map.get(key, 0) + 1
            expected_map[key] = expected_map.get(key, 0) + _periods_in_window(r.freq or "daily", win_start, win_end)

        result: List[DepartmentSummaryRow] = []
        for d in dep_rows:
            did = str(d.id)
            expected = expected_map.get(did, 0)
            entered = entered_map.get(did, 0)
            result.append(DepartmentSummaryRow(
                department_id=d.id,
                department_name=d.name,
                kpis_assigned=assigned_map.get(did, 0),
                entered=entered,
                missing=max(expected - entered, 0),
                pct_entered=self._pct(entered, expected),
            ))
        return result

    async def _by_school(
        self,
        win_start: date_type, win_end: date_type,
        start_ts: datetime, end_ts: datetime,
        *, db: Optional[AsyncSession] = None,
    ) -> List[SchoolSummaryRow]:
        db = db or self.db
        school_rows = (await db.execute(
            text("SELECT id, name FROM schools WHERE status = 'active' ORDER BY name")
        )).fetchall()
        entered_rows = await db.execute(
            text("""
                SELECT school_id AS sid, COUNT(*) AS c
                FROM observations
                WHERE submitted_at >= :start AND submitted_at < :end
                  AND school_id IS NOT NULL
                GROUP BY 1
            """),
            {"start": start_ts, "end": end_ts},
        )
        entered_map = {str(r.sid): int(r.c) for r in entered_rows.fetchall()}

        assign_rows = await db.execute(
            text("""
                SELECT d.school_id AS sid, k.frequency_code AS freq
                FROM department_kpi_assignments a
                JOIN kpis k ON k.kpi_id = a.kpi_id AND k.status = 'active'
                JOIN departments d ON d.id = a.department_id AND d.status = 'active'
            """)
        )
        expected_map: Dict[str, int] = {}
        assigned_map: Dict[str, int] = {}
        for r in assign_rows.fetchall():
            key = str(r.sid)
            assigned_map[key] = assigned_map.get(key, 0) + 1
            expected_map[key] = expected_map.get(key, 0) + _periods_in_window(r.freq or "daily", win_start, win_end)

        return [
            SchoolSummaryRow(
                school_id=s.id,
                school_name=s.name,
                kpis_assigned=assigned_map.get(str(s.id), 0),
                entered=entered_map.get(str(s.id), 0),
                missing=max(expected_map.get(str(s.id), 0) - entered_map.get(str(s.id), 0), 0),
                pct_entered=self._pct(entered_map.get(str(s.id), 0), expected_map.get(str(s.id), 0)),
            )
            for s in school_rows
        ]
