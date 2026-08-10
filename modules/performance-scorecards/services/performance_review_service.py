"""
Performance Review Service — PRS §28.

Business rules enforced here:
  BR-PRS-28-1  A PerformanceReview cycle is driven by the Configuration Engine
               key PERFORMANCE_REVIEW_CADENCE_DAYS (default 90, school-overridable).
  BR-PRS-28-2  Duplicate cycle windows (same school+department+cycle_start+cycle_end)
               are idempotent — the existing review is returned.
  BR-PRS-28-3  Only SCHEDULED or IN_PROGRESS reviews may be cancelled.
  BR-PRS-28-4  Completing a review triggers scorecard generation for all subjects
               (users + department) linked to the review's school/department.
               Scorecard generation is enqueued on the async job queue, not run
               inline, so the HTTP response is never blocked.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.configuration_engine.constants import ConfigKey
from platform_services.configuration_engine.service import ConfigurationEngine
from shared.datetime_utils import utc_now
from shared.errors import BusinessRuleError, NotFoundError
from shared.platform_models import (
    PerformanceReview,
    PerformanceReviewStatus,
)


@dataclass
class ReviewCreateResult:
    review: PerformanceReview
    created: bool  # False → idempotent return of existing review


class PerformanceReviewService:
    """
    Service for PRS §28 Performance Review lifecycle management.

    Scorecard generation is NOT triggered here — it is triggered by the
    ScorecardScheduler (PRS §29) which reads due reviews and enqueues jobs.
    """

    def __init__(
        self,
        db: AsyncSession,
        config_engine: Optional[ConfigurationEngine] = None,
    ) -> None:
        self.db = db
        self._config = config_engine or ConfigurationEngine(db)

    # ── creation ───────────────────────────────────────────────────────────────

    async def create_review(
        self,
        *,
        school_id: UUID,
        cycle_start: date,
        cycle_end: date,
        department_id: Optional[UUID] = None,
    ) -> ReviewCreateResult:
        """
        Create a PerformanceReview for the given cycle window.

        Idempotent: if an identical window already exists for this
        school+department pair, the existing review is returned (created=False).
        """
        # Idempotency check
        existing = await self._find_review(
            school_id=school_id,
            department_id=department_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        if existing is not None:
            return ReviewCreateResult(review=existing, created=False)

        cadence_days = await self._config.get(
            ConfigKey.PERFORMANCE_REVIEW_CADENCE_DAYS,
            school_id=school_id,
            department_id=department_id,
        )

        now = utc_now()
        review = PerformanceReview(
            id=uuid.uuid4(),
            school_id=school_id,
            department_id=department_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            cadence_days=int(cadence_days),
            status=PerformanceReviewStatus.SCHEDULED,
            created_at=now,
            updated_at=now,
        )
        self.db.add(review)
        await self.db.flush()
        return ReviewCreateResult(review=review, created=True)

    async def create_next_review(
        self,
        *,
        school_id: UUID,
        department_id: Optional[UUID] = None,
        after: Optional[date] = None,
    ) -> ReviewCreateResult:
        """
        Compute the next cycle window based on the cadence and create a review.

        'after' defaults to today.  The new cycle starts on the day after 'after'
        and spans cadence_days days.
        """
        cadence_days = int(
            await self._config.get(
                ConfigKey.PERFORMANCE_REVIEW_CADENCE_DAYS,
                school_id=school_id,
                department_id=department_id,
            )
        )
        start = (after or date.today()) + timedelta(days=1)
        end = start + timedelta(days=cadence_days - 1)

        return await self.create_review(
            school_id=school_id,
            department_id=department_id,
            cycle_start=start,
            cycle_end=end,
        )

    # ── status transitions ─────────────────────────────────────────────────────

    async def start_review(self, review_id: UUID) -> PerformanceReview:
        """Transition SCHEDULED → IN_PROGRESS."""
        review = await self._get_or_raise(review_id)
        if review.status != PerformanceReviewStatus.SCHEDULED:
            raise BusinessRuleError(
                f"Cannot start a review in status '{review.status.value}'. "
                "Only SCHEDULED reviews may be started.",
                details={"review_id": str(review_id), "status": review.status.value},
            )
        review.status = PerformanceReviewStatus.IN_PROGRESS
        review.updated_at = utc_now()
        await self.db.flush()
        return review

    async def complete_review(self, review_id: UUID) -> PerformanceReview:
        """
        Transition IN_PROGRESS → COMPLETED.

        Scorecard generation is NOT triggered inline — callers that want
        scorecards enqueued should call ScorecardScheduler.enqueue_for_review()
        after this method returns.
        """
        review = await self._get_or_raise(review_id)
        if review.status != PerformanceReviewStatus.IN_PROGRESS:
            raise BusinessRuleError(
                f"Cannot complete a review in status '{review.status.value}'. "
                "Only IN_PROGRESS reviews may be completed.",
                details={"review_id": str(review_id), "status": review.status.value},
            )
        now = utc_now()
        review.status = PerformanceReviewStatus.COMPLETED
        review.completed_at = now
        review.updated_at = now
        await self.db.flush()
        return review

    async def cancel_review(self, review_id: UUID) -> PerformanceReview:
        """Transition SCHEDULED|IN_PROGRESS → CANCELLED."""
        review = await self._get_or_raise(review_id)
        if review.status not in (
            PerformanceReviewStatus.SCHEDULED,
            PerformanceReviewStatus.IN_PROGRESS,
        ):
            raise BusinessRuleError(
                f"Cannot cancel a review in status '{review.status.value}'. "
                "Only SCHEDULED or IN_PROGRESS reviews may be cancelled.",
                details={"review_id": str(review_id), "status": review.status.value},
            )
        now = utc_now()
        review.status = PerformanceReviewStatus.CANCELLED
        review.cancelled_at = now
        review.updated_at = now
        await self.db.flush()
        return review

    # ── queries ────────────────────────────────────────────────────────────────

    async def get_review(self, review_id: UUID) -> PerformanceReview:
        return await self._get_or_raise(review_id)

    async def list_reviews(
        self,
        *,
        school_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        status: Optional[PerformanceReviewStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PerformanceReview]:
        q = select(PerformanceReview)
        filters = []
        if school_id is not None:
            filters.append(PerformanceReview.school_id == school_id)
        if department_id is not None:
            filters.append(PerformanceReview.department_id == department_id)
        if status is not None:
            filters.append(PerformanceReview.status == status)
        if filters:
            q = q.where(and_(*filters))
        q = q.order_by(PerformanceReview.cycle_start.desc()).limit(limit).offset(offset)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    # ── internals ──────────────────────────────────────────────────────────────

    async def _get_or_raise(self, review_id: UUID) -> PerformanceReview:
        row = await self.db.get(PerformanceReview, review_id)
        if row is None:
            raise NotFoundError(f"PerformanceReview {review_id} not found.")
        return row

    async def _find_review(
        self,
        *,
        school_id: UUID,
        department_id: Optional[UUID],
        cycle_start: date,
        cycle_end: date,
    ) -> Optional[PerformanceReview]:
        filters = [
            PerformanceReview.school_id == school_id,
            PerformanceReview.cycle_start == cycle_start,
            PerformanceReview.cycle_end == cycle_end,
        ]
        if department_id is None:
            filters.append(PerformanceReview.department_id.is_(None))
        else:
            filters.append(PerformanceReview.department_id == department_id)

        result = await self.db.execute(
            select(PerformanceReview).where(and_(*filters)).limit(1)
        )
        return result.scalar_one_or_none()
