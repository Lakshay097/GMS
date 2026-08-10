"""
Scorecard Scheduler — PRS §29 periodic generation.

Responsibilities
----------------
1. Enqueue a scorecard-generation job for a specific review onto the async
   queue (never runs inline with an HTTP request).
2. Process queued jobs: for each subject (users + department) linked to the
   review's school/department, call ScorecardService.generate().
3. Write a ScorecardRunLog row for every job execution (audit trail).

Queue/job conventions follow the escalation_scheduler.py pattern (Prompt 5).
The `clock_now` parameter in `run_generation` lets tests pin the timestamp
without patching datetime.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.performance_scorecards.services.scorecard_service import ScorecardService
from platform_services.rule_engine.service import RuleEngine
from platform_services.rule_engine.strategies import WorstStatusWinsStrategy
from shared.datetime_utils import utc_now
from shared.models import User
from shared.platform_models import (
    PerformanceReview,
    PerformanceReviewStatus,
    Scorecard,
    ScorecardRunLog,
    ScorecardSubjectType,
    SchedulerRunStatus,
)
from shared.task_queue import JobRegistry, get_queue_instance

SCORECARD_QUEUE = "scorecard_generation"
SCORECARD_JOB_TYPE = "scorecard_generate"


@dataclass
class ScorecardRunResult:
    run_log_id: UUID
    scorecards_generated: int
    scorecards_versioned: int
    status: SchedulerRunStatus
    errors: list[str]


class ScorecardScheduler:
    """
    Async job processor for periodic scorecard generation (PRS §29).

    Usage
    -----
    # Enqueue a job (from a cron / completed-review hook):
        scheduler = ScorecardScheduler(db)
        await scheduler.enqueue_for_review(review_id)

    # Process the queue (called by the worker process):
        await scheduler.run_generation(review_id=review_id)
    """

    def __init__(
        self,
        db: AsyncSession,
        rule_engine: Optional[RuleEngine] = None,
        queue=None,
    ) -> None:
        self.db = db
        self._rule_engine = rule_engine or self._default_rule_engine()
        self._queue = queue or get_queue_instance()
        self._scorecard_service = ScorecardService(db, rule_engine=self._rule_engine)
        self._register_job_handler()

    # ── public API ─────────────────────────────────────────────────────────────

    async def enqueue_for_review(
        self,
        review_id: UUID,
        delay_seconds: int = 0,
    ) -> str:
        """Put a scorecard generation job on the async queue for review_id."""
        return await self._queue.enqueue(
            SCORECARD_QUEUE,
            {"job_type": SCORECARD_JOB_TYPE, "review_id": str(review_id)},
            delay_seconds=delay_seconds,
        )

    async def run_generation(
        self,
        *,
        review_id: UUID,
        clock_now: Optional[datetime] = None,
    ) -> ScorecardRunResult:
        """
        Generate scorecards for all subjects in the given review.

        For each subject (department-level subject + every active user in that
        department / school):
          - Calls ScorecardService.generate() which always INSERTs a new row.
          - If a prior version existed for the same subject×cycle, the prior
            row's superseded_by_id is updated by ScorecardService — no other
            mutation occurs on existing scorecard rows.

        A ScorecardRunLog row is written regardless of success/failure.
        """
        now = clock_now or utc_now()
        generated = 0
        versioned = 0
        errors: list[str] = []

        run_log = ScorecardRunLog(
            id=uuid.uuid4(),
            review_id=review_id,
            started_at=now,
            status=SchedulerRunStatus.SUCCESS,
            scorecards_generated=0,
            scorecards_versioned=0,
        )
        self.db.add(run_log)
        await self.db.flush()

        try:
            review = await self.db.get(PerformanceReview, review_id)
            if review is None:
                raise ValueError(f"PerformanceReview {review_id} not found.")

            subjects = await self._collect_subjects(review)

            for subject_type, subject_id in subjects:
                try:
                    prior_count = await self._prior_version_count(
                        subject_type=subject_type,
                        subject_id=subject_id,
                        review=review,
                    )
                    await self._scorecard_service.generate(
                        subject_type=subject_type,
                        subject_id=subject_id,
                        cycle_start=review.cycle_start,
                        cycle_end=review.cycle_end,
                        review_id=review_id,
                    )
                    if prior_count > 0:
                        versioned += 1
                    else:
                        generated += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(
                        f"subject {subject_type.value}/{subject_id}: {exc}"
                    )

            # Commit all generated scorecards together
            run_log.scorecards_generated = generated
            run_log.scorecards_versioned = versioned
            run_log.finished_at = utc_now()
            run_log.status = (
                SchedulerRunStatus.PARTIAL_FAILURE
                if errors
                else SchedulerRunStatus.SUCCESS
            )

        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            run_log.status = SchedulerRunStatus.FAILED
            run_log.error_detail = "; ".join(errors)
            run_log.finished_at = utc_now()

        await self.db.commit()

        return ScorecardRunResult(
            run_log_id=run_log.id,
            scorecards_generated=generated,
            scorecards_versioned=versioned,
            status=run_log.status,
            errors=errors,
        )

    # ── internals ──────────────────────────────────────────────────────────────

    async def _collect_subjects(
        self, review: PerformanceReview
    ) -> list[tuple[ScorecardSubjectType, UUID]]:
        """
        Build the list of (subject_type, subject_id) pairs for this review.

        - If department_id is set: generate one DEPARTMENT scorecard + one USER
          scorecard per active user in that department.
        - If department_id is None (school-level review): one DEPARTMENT
          scorecard per school department + one USER scorecard per school user.
        """
        subjects: list[tuple[ScorecardSubjectType, UUID]] = []

        if review.department_id is not None:
            # Department-level scorecard
            subjects.append((ScorecardSubjectType.DEPARTMENT, review.department_id))
            # Individual user scorecards for this department
            users = await self._get_users_for_department(review.department_id)
            for user_id in users:
                subjects.append((ScorecardSubjectType.USER, user_id))
        else:
            # School-level review — cover all departments and users
            from shared.models import Department, DepartmentStatus

            dept_result = await self.db.execute(
                select(Department.id).where(
                    and_(
                        Department.school_id == review.school_id,
                        Department.status == DepartmentStatus.ACTIVE,
                    )
                )
            )
            for dept_id in dept_result.scalars().all():
                subjects.append((ScorecardSubjectType.DEPARTMENT, dept_id))
                users = await self._get_users_for_department(dept_id)
                for user_id in users:
                    subjects.append((ScorecardSubjectType.USER, user_id))

        return subjects

    async def _get_users_for_department(self, department_id: UUID) -> list[UUID]:
        from shared.models import UserStatus

        result = await self.db.execute(
            select(User.id).where(
                and_(
                    User.department_id == department_id,
                    User.status == UserStatus.ACTIVE,
                )
            )
        )
        return list(result.scalars().all())

    async def _prior_version_count(
        self,
        *,
        subject_type: ScorecardSubjectType,
        subject_id: UUID,
        review: PerformanceReview,
    ) -> int:
        """Return the number of existing scorecard rows for this subject×cycle."""
        result = await self.db.execute(
            select(Scorecard).where(
                and_(
                    Scorecard.subject_type == subject_type,
                    Scorecard.subject_id == subject_id,
                    Scorecard.cycle_start == review.cycle_start,
                    Scorecard.cycle_end == review.cycle_end,
                )
            )
        )
        return len(result.scalars().all())

    def _register_job_handler(self) -> None:
        registry = JobRegistry()

        async def _handle(job_data: dict) -> None:
            review_id = UUID(job_data["review_id"])
            await self.run_generation(review_id=review_id)

        if SCORECARD_JOB_TYPE not in registry.handlers:
            registry.register(SCORECARD_JOB_TYPE, _handle)

    @staticmethod
    def _default_rule_engine() -> RuleEngine:
        engine = RuleEngine()
        engine.register_strategy(WorstStatusWinsStrategy())
        return engine
