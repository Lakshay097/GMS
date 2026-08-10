"""
Scorecard Service — PRS §29.

Business rules enforced here:
  R-18/BR-14/C6   Scorecards are GENERATED, never updated or deleted.
                  Recalculation always produces a new version row (v+1).
                  The prior version is retained and its superseded_by_id is set
                  to the new row's id — no existing row is mutated beyond that
                  single FK pointer write.
                  No application code path calls Session.delete() or issues an
                  UPDATE against scorecard metric columns.

  Scoring         RAG status is computed via the Rule Engine's
                  worst-status-wins strategy (Prompt 4 / Architecture §5.2).
                  Local scoring logic is explicitly forbidden — delegate only.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.rule_engine.service import RuleEngine
from platform_services.rule_engine.strategies import WorstStatusWinsStrategy
from platform_services.notification_service.service import (
    NotificationPayload,
    NotificationService,
)
from shared.datetime_utils import utc_now
from shared.errors import NotFoundError
from shared.platform_models import (
    Discrepancy,
    NotificationCategory,
    NotificationChannel,
    Observation,
    RagStatus,
    Scorecard,
    ScorecardSubjectType,
    Task,
    TaskStatus,
)
from shared.models import User, UserRole, UserStatus, Department


# ── helpers ────────────────────────────────────────────────────────────────────

# WorstStatusWinsStrategy speaks compliance vocabulary (met / amber / not_met / n_a).
# Observation.rag_status and Scorecard.rag_status use RAG vocabulary
# (green / amber / red / not_submitted). Map both directions at the scorecard boundary.
_RAG_TO_COMPLIANCE = {
    RagStatus.GREEN.value: "met",
    RagStatus.AMBER.value: "amber",
    RagStatus.RED.value: "not_met",
    RagStatus.NOT_SUBMITTED.value: "n_a",
    "met": "met",
    "amber": "amber",
    "not_met": "not_met",
    "n_a": "n_a",
}

_COMPLIANCE_TO_RAG = {
    "met": RagStatus.GREEN.value,
    "amber": RagStatus.AMBER.value,
    "not_met": RagStatus.RED.value,
    "n_a": RagStatus.NOT_SUBMITTED.value,
    RagStatus.GREEN.value: RagStatus.GREEN.value,
    RagStatus.AMBER.value: RagStatus.AMBER.value,
    RagStatus.RED.value: RagStatus.RED.value,
    RagStatus.NOT_SUBMITTED.value: RagStatus.NOT_SUBMITTED.value,
}


def _build_rule_engine() -> RuleEngine:
    """Return a RuleEngine with worst-status-wins pre-registered."""
    engine = RuleEngine()
    engine.register_strategy(WorstStatusWinsStrategy())
    return engine


_STRATEGY = "worst_status_wins"


@dataclass
class ScorecardMetrics:
    rag_status: str
    pct_kpis_met: Decimal
    pct_tasks_on_time: Decimal
    open_discrepancy_count: int
    kpi_breakdown: list[dict]


# ── service ────────────────────────────────────────────────────────────────────


class ScorecardService:
    """
    Core generation service for PRS §29 Scorecards.

    The only write path is ``generate()``.  It always INSERTs a new row.
    It never calls Session.update() / Session.delete() on scorecard rows.
    The superseded_by_id pointer on the *prior* version is the sole mutation
    performed on an existing row — it is a backward link, not a metric update.
    """

    def __init__(
        self,
        db: AsyncSession,
        rule_engine: Optional[RuleEngine] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.db = db
        self._rule_engine = rule_engine or _build_rule_engine()
        self._notification_service = notification_service or NotificationService(db)

    # ── public API ─────────────────────────────────────────────────────────────

    async def generate(
        self,
        *,
        subject_type: ScorecardSubjectType,
        subject_id: UUID,
        cycle_start: date,
        cycle_end: date,
        review_id: Optional[UUID] = None,
    ) -> Scorecard:
        """
        Generate (INSERT) a new Scorecard for the given subject and cycle.

        If a prior version already exists for this subject×cycle:
          1. The new version number = prior_max_version + 1.
          2. The prior latest version's superseded_by_id is set to the new row's id.
             This is the ONLY mutation performed on an existing row.
          3. All prior metric columns are left untouched.

        Returns the freshly inserted Scorecard row.

        R-18/BR-14/C6: this method NEVER calls db.delete() or issues an UPDATE
        on scorecard metric columns.
        """
        now = utc_now()

        # ── compute metrics via rule engine ────────────────────────────────────
        metrics = await self._compute_metrics(
            subject_type=subject_type,
            subject_id=subject_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        # ── resolve next version and prior latest row ──────────────────────────
        next_version, prior_latest = await self._resolve_version(
            subject_type=subject_type,
            subject_id=subject_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        # ── INSERT new scorecard row ───────────────────────────────────────────
        new_id = uuid.uuid4()
        new_scorecard = Scorecard(
            id=new_id,
            review_id=review_id,
            subject_type=subject_type,
            subject_id=subject_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            version=next_version,
            superseded_by_id=None,          # current (latest) version — not superseded
            rag_status=RagStatus(metrics.rag_status),
            pct_kpis_met=metrics.pct_kpis_met,
            pct_tasks_on_time=metrics.pct_tasks_on_time,
            open_discrepancy_count=metrics.open_discrepancy_count,
            kpi_breakdown=metrics.kpi_breakdown,
            generated_at=now,
        )
        self.db.add(new_scorecard)
        await self.db.flush()  # populate id before updating prior row

        # ── mark prior version as superseded ──────────────────────────────────
        # This is the ONLY column ever written on an existing scorecard row.
        # It is a backward pointer, NOT a metric mutation.
        if prior_latest is not None:
            prior_latest.superseded_by_id = new_id
            # Note: we do NOT touch any metric column on prior_latest.

        await self.db.flush()
        
        # Notify relevant users per PRS §49 Notification Matrix
        # Category 7 (INFORMATIONAL) - In-App, Email channels
        # Notify the subject (user) and Admins.
        # Role membership is filtered in Python so SQLite E2E (no JSONB @>)
        # and Postgres both work; roles are stored as JSON string lists.
        from sqlalchemy import select

        async def _active_user_ids_with_role(
            *,
            role: str,
            school_id: Optional[UUID] = None,
        ) -> list[UUID]:
            # Select only id/roles to avoid SQLEnum name/value mismatches on
            # SQLite when hydrating full User rows (status stored as "active").
            query = select(User.id, User.roles).where(
                User.status.in_(["active", UserStatus.ACTIVE])
            )
            if school_id is not None:
                query = query.where(User.school_id == school_id)
            result = await self.db.execute(query)
            return [
                row.id
                for row in result.all()
                if role in (row.roles or [])
            ]
        
        if subject_type == ScorecardSubjectType.USER:
            # Notify the user themselves
            await self._notification_service.dispatch(
                NotificationPayload(
                    user_id=subject_id,
                    category=NotificationCategory.INFORMATIONAL.value,
                    title="Scorecard Generated",
                    body=f"Your performance scorecard for {cycle_start} to {cycle_end} has been generated",
                    channel=NotificationChannel.IN_APP,
                    entity_type="scorecard",
                    entity_id=new_scorecard.id,
                )
            )
            
            # Notify school admins
            user = await self.db.get(User, subject_id)
            if user and user.school_id:
                for admin_id in await _active_user_ids_with_role(
                    role=UserRole.ADMIN.value,
                    school_id=user.school_id,
                ):
                    await self._notification_service.dispatch(
                        NotificationPayload(
                            user_id=admin_id,
                            category=NotificationCategory.INFORMATIONAL.value,
                            title="Scorecard Generated",
                            body=f"Performance scorecard has been generated for user {user.full_name}",
                            channel=NotificationChannel.EMAIL,
                            school_id=user.school_id,
                            entity_type="scorecard",
                            entity_id=new_scorecard.id,
                        )
                    )
        elif subject_type == ScorecardSubjectType.DEPARTMENT:
            # Notify school admins for department scorecards
            dept = await self.db.get(Department, subject_id)
            if dept and dept.school_id:
                for admin_id in await _active_user_ids_with_role(
                    role=UserRole.ADMIN.value,
                    school_id=dept.school_id,
                ):
                    await self._notification_service.dispatch(
                        NotificationPayload(
                            user_id=admin_id,
                            category=NotificationCategory.INFORMATIONAL.value,
                            title="Department Scorecard Generated",
                            body=f"Department scorecard for {dept.name} has been generated",
                            channel=NotificationChannel.EMAIL,
                            school_id=dept.school_id,
                            entity_type="scorecard",
                            entity_id=new_scorecard.id,
                        )
                    )
        
        return new_scorecard

    async def get_scorecard(self, scorecard_id: UUID) -> Scorecard:
        """Fetch a single scorecard by primary key."""
        row = await self.db.get(Scorecard, scorecard_id)
        if row is None:
            raise NotFoundError(f"Scorecard {scorecard_id} not found.")
        return row

    async def list_versions(
        self,
        *,
        subject_type: ScorecardSubjectType,
        subject_id: UUID,
        cycle_start: date,
        cycle_end: date,
    ) -> list[Scorecard]:
        """
        Return all scorecard versions for a subject×cycle, ordered v1 → vN.
        The latest (active) version is the one where superseded_by_id IS NULL.
        """
        result = await self.db.execute(
            select(Scorecard)
            .where(
                and_(
                    Scorecard.subject_type == subject_type,
                    Scorecard.subject_id == subject_id,
                    Scorecard.cycle_start == cycle_start,
                    Scorecard.cycle_end == cycle_end,
                )
            )
            .order_by(Scorecard.version.asc())
        )
        return list(result.scalars().all())

    async def list_for_review(self, review_id: UUID) -> list[Scorecard]:
        """Return all scorecards generated under a specific review."""
        result = await self.db.execute(
            select(Scorecard)
            .where(Scorecard.review_id == review_id)
            .order_by(Scorecard.subject_type, Scorecard.subject_id, Scorecard.version)
        )
        return list(result.scalars().all())

    # ── internal helpers ───────────────────────────────────────────────────────

    async def _resolve_version(
        self,
        *,
        subject_type: ScorecardSubjectType,
        subject_id: UUID,
        cycle_start: date,
        cycle_end: date,
    ) -> tuple[int, Optional[Scorecard]]:
        """
        Return (next_version_number, prior_latest_scorecard_or_None).

        prior_latest is the row with the highest version and superseded_by_id IS NULL.
        """
        result = await self.db.execute(
            select(Scorecard)
            .where(
                and_(
                    Scorecard.subject_type == subject_type,
                    Scorecard.subject_id == subject_id,
                    Scorecard.cycle_start == cycle_start,
                    Scorecard.cycle_end == cycle_end,
                    Scorecard.superseded_by_id.is_(None),
                )
            )
            .order_by(Scorecard.version.desc())
            .limit(1)
        )
        prior_latest: Optional[Scorecard] = result.scalar_one_or_none()

        if prior_latest is None:
            return 1, None

        return prior_latest.version + 1, prior_latest

    async def _compute_metrics(
        self,
        *,
        subject_type: ScorecardSubjectType,
        subject_id: UUID,
        cycle_start: date,
        cycle_end: date,
    ) -> ScorecardMetrics:
        """
        Pull raw KPI/task/discrepancy data for the cycle window and delegate
        aggregation to the Rule Engine's worst-status-wins strategy.

        No scoring logic lives here — we only query data and call the engine.
        """
        kpi_breakdown, rag_status, pct_kpis_met = await self._aggregate_kpis(
            subject_type=subject_type,
            subject_id=subject_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        pct_tasks_on_time = await self._pct_tasks_on_time(
            subject_type=subject_type,
            subject_id=subject_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        open_discrepancy_count = await self._open_discrepancy_count(
            subject_type=subject_type,
            subject_id=subject_id,
            cycle_end=cycle_end,
        )

        return ScorecardMetrics(
            rag_status=rag_status,
            pct_kpis_met=pct_kpis_met,
            pct_tasks_on_time=pct_tasks_on_time,
            open_discrepancy_count=open_discrepancy_count,
            kpi_breakdown=kpi_breakdown,
        )

    async def _aggregate_kpis(
        self,
        *,
        subject_type: ScorecardSubjectType,
        subject_id: UUID,
        cycle_start: date,
        cycle_end: date,
    ) -> tuple[list[dict], str, Decimal]:
        """
        Query observations in the cycle window, build a per-KPI status list,
        then delegate to WorstStatusWins via the Rule Engine.

        Returns (kpi_breakdown, rag_status_str, pct_kpis_met).
        """
        # Build filter predicate based on subject type
        obs_filter = self._obs_filter(
            subject_type=subject_type,
            subject_id=subject_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        result = await self.db.execute(
            select(
                Observation.kpi_id,
                Observation.auto_result,
                Observation.rag_status,
            ).where(obs_filter)
        )
        rows = result.all()

        if not rows:
            # No observations → no data → aggregate to "not_submitted"
            return [], RagStatus.NOT_SUBMITTED.value, Decimal("0.00")

        # Group by kpi_id — take worst status per KPI across the window.
        # Normalise Observation RAG colours into compliance vocabulary before
        # delegating to WorstStatusWins (engine output is met/amber/not_met/n_a).
        kpi_statuses: dict[UUID, str] = {}
        for kpi_id, auto_result, rag_status in rows:
            current_worst = kpi_statuses.get(kpi_id)
            raw = rag_status.value if hasattr(rag_status, "value") else str(rag_status)
            incoming = _RAG_TO_COMPLIANCE.get(raw, raw)
            if current_worst is None:
                kpi_statuses[kpi_id] = incoming
            else:
                # Delegate worst-picks to the engine (handles n_a neutral correctly)
                kpi_statuses[kpi_id] = self._rule_engine.aggregate(
                    _STRATEGY, [current_worst, incoming]
                )

        # Final roll-up across all KPIs via the Rule Engine
        all_statuses = list(kpi_statuses.values())
        aggregate_compliance = self._rule_engine.aggregate(_STRATEGY, all_statuses)
        aggregate_rag = _COMPLIANCE_TO_RAG.get(aggregate_compliance, aggregate_compliance)

        # pct_kpis_met = fraction of distinct KPIs whose worst-status is "met"
        met_count = sum(1 for s in kpi_statuses.values() if s == "met")
        total_count = len(kpi_statuses)
        pct_met = Decimal(str(round(met_count / total_count * 100, 2))) if total_count else Decimal("0.00")

        breakdown = [
            {
                "kpi_id": str(kpi_id),
                "rag_status": _COMPLIANCE_TO_RAG.get(status, status),
            }
            for kpi_id, status in kpi_statuses.items()
        ]

        return breakdown, aggregate_rag, pct_met

    async def _pct_tasks_on_time(
        self,
        *,
        subject_type: ScorecardSubjectType,
        subject_id: UUID,
        cycle_start: date,
        cycle_end: date,
    ) -> Decimal:
        """Percentage of tasks that completed on or before their ETA."""
        # Convert dates to datetime for comparison with DateTime columns
        from datetime import datetime

        start_dt = datetime(cycle_start.year, cycle_start.month, cycle_start.day)
        end_dt = datetime(cycle_end.year, cycle_end.month, cycle_end.day, 23, 59, 59)

        base_filter = and_(
            Task.created_at >= start_dt,
            Task.created_at <= end_dt,
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at.is_not(None),
        )

        if subject_type == ScorecardSubjectType.DEPARTMENT:
            base_filter = and_(base_filter, Task.department_id == subject_id)
        else:
            # For user subject type: tasks where the user was an owner
            # Simplified: filter by school tasks (full owner join is done in
            # _tasks_for_user if needed — kept simple for Phase 1)
            base_filter = and_(base_filter, Task.school_id == subject_id)

        result = await self.db.execute(
            select(
                func.count(Task.id).label("total"),
                func.sum(
                    # 1 if completed on time, 0 otherwise
                    func.cast(Task.completed_at <= Task.eta, sa_Integer())
                ).label("on_time"),
            ).where(base_filter)
        )
        row = result.one()
        total = row.total or 0
        on_time = row.on_time or 0

        if total == 0:
            return Decimal("100.00")  # no tasks → no missed tasks

        return Decimal(str(round(on_time / total * 100, 2)))

    async def _open_discrepancy_count(
        self,
        *,
        subject_type: ScorecardSubjectType,
        subject_id: UUID,
        cycle_end: date,
    ) -> int:
        """Count of discrepancies not yet closed as of cycle_end."""
        from datetime import datetime

        end_dt = datetime(cycle_end.year, cycle_end.month, cycle_end.day, 23, 59, 59)

        base_filter = and_(
            Discrepancy.raised_at <= end_dt,
            Discrepancy.closed_at.is_(None),  # still open at cycle_end
        )

        if subject_type == ScorecardSubjectType.DEPARTMENT:
            base_filter = and_(base_filter, Discrepancy.department_id == subject_id)
        else:
            base_filter = and_(base_filter, Discrepancy.school_id == subject_id)

        result = await self.db.execute(
            select(func.count(Discrepancy.id)).where(base_filter)
        )
        return result.scalar_one() or 0

    def _obs_filter(
        self,
        *,
        subject_type: ScorecardSubjectType,
        subject_id: UUID,
        cycle_start: date,
        cycle_end: date,
    ):
        """Build the SQLAlchemy WHERE clause for observation queries."""
        from datetime import datetime
        from sqlalchemy import and_

        start_dt = datetime(cycle_start.year, cycle_start.month, cycle_start.day)
        end_dt = datetime(cycle_end.year, cycle_end.month, cycle_end.day, 23, 59, 59)

        time_filter = and_(
            Observation.submitted_at >= start_dt,
            Observation.submitted_at <= end_dt,
        )

        if subject_type == ScorecardSubjectType.DEPARTMENT:
            return and_(time_filter, Observation.department_id == subject_id)
        else:
            # USER subject — observations submitted by this user (checker_id)
            return and_(time_filter, Observation.checker_id == subject_id)


# SQLAlchemy Integer cast helper used in the on-time computation
from sqlalchemy import Integer as sa_Integer  # noqa: E402 — placed after class body
