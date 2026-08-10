"""
Performance Reviews & Scorecards API — PRS §28-29.

Endpoints
---------
POST   /performance-reviews                 create a review cycle
GET    /performance-reviews                 list reviews (filterable)
GET    /performance-reviews/{review_id}     get a single review
PATCH  /performance-reviews/{review_id}     transition status (start/complete/cancel)

GET    /scorecards                          list scorecards (filterable)
GET    /scorecards/{scorecard_id}           get a single scorecard
GET    /scorecards/{scorecard_id}/versions  all versions for the same subject×cycle
POST   /scorecards/generate                 system/admin: trigger generation job

Grant restrictions (R-18/BR-14/C6):
  No endpoint issues an UPDATE or DELETE against scorecard rows.
  POST /scorecards/generate calls ScorecardService.generate() which only INSERTs.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.performance_scorecards.services.performance_review_service import (
    PerformanceReviewService,
)
from modules.performance_scorecards.services.scorecard_service import ScorecardService
from modules.performance_scorecards.services.scorecard_scheduler import ScorecardScheduler
from shared.database import get_db
from shared.platform_models import PerformanceReviewStatus, ScorecardSubjectType

reviews_router = APIRouter(prefix="/performance-reviews", tags=["performance-reviews"])
scorecards_router = APIRouter(prefix="/scorecards", tags=["scorecards"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────


class ReviewCreate(BaseModel):
    school_id: UUID
    cycle_start: date
    cycle_end: date
    department_id: Optional[UUID] = None


class ReviewStatusPatch(BaseModel):
    action: str = Field(..., pattern="^(start|complete|cancel)$")


class ReviewOut(BaseModel):
    id: UUID
    school_id: UUID
    department_id: Optional[UUID]
    cycle_start: date
    cycle_end: date
    cadence_days: int
    status: str
    completed_at: Optional[str]
    cancelled_at: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ScorecardOut(BaseModel):
    id: UUID
    review_id: Optional[UUID]
    subject_type: str
    subject_id: UUID
    cycle_start: date
    cycle_end: date
    version: int
    superseded_by_id: Optional[UUID]
    rag_status: str
    pct_kpis_met: float
    pct_tasks_on_time: float
    open_discrepancy_count: int
    kpi_breakdown: Optional[list]
    generated_at: str

    class Config:
        from_attributes = True


class ScorecardGenerateRequest(BaseModel):
    subject_type: ScorecardSubjectType
    subject_id: UUID
    cycle_start: date
    cycle_end: date
    review_id: Optional[UUID] = None


class ScorecardGenerateResponse(BaseModel):
    scorecard_id: UUID
    version: int
    message: str


class GenerateForReviewRequest(BaseModel):
    review_id: UUID


class GenerateForReviewResponse(BaseModel):
    message: str
    job_enqueued: bool


# ── DI helpers ─────────────────────────────────────────────────────────────────


def get_review_service(db: AsyncSession = Depends(get_db)) -> PerformanceReviewService:
    return PerformanceReviewService(db)


def get_scorecard_service(db: AsyncSession = Depends(get_db)) -> ScorecardService:
    return ScorecardService(db)


def get_scheduler(db: AsyncSession = Depends(get_db)) -> ScorecardScheduler:
    return ScorecardScheduler(db)


# ── Performance Review endpoints ───────────────────────────────────────────────


@reviews_router.post(
    "",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a performance review cycle",
)
async def create_performance_review(
    body: ReviewCreate,
    svc: PerformanceReviewService = Depends(get_review_service),
) -> ReviewOut:
    result = await svc.create_review(
        school_id=body.school_id,
        department_id=body.department_id,
        cycle_start=body.cycle_start,
        cycle_end=body.cycle_end,
    )
    await svc.db.commit()
    return _review_out(result.review)


@reviews_router.get(
    "",
    response_model=List[ReviewOut],
    summary="List performance reviews",
)
async def list_performance_reviews(
    school_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
    review_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    svc: PerformanceReviewService = Depends(get_review_service),
) -> List[ReviewOut]:
    status_filter = None
    if review_status:
        try:
            status_filter = PerformanceReviewStatus(review_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status value: {review_status}",
            )
    reviews = await svc.list_reviews(
        school_id=school_id,
        department_id=department_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_review_out(r) for r in reviews]


@reviews_router.get(
    "/{review_id}",
    response_model=ReviewOut,
    summary="Get a single performance review",
)
async def get_performance_review(
    review_id: UUID,
    svc: PerformanceReviewService = Depends(get_review_service),
) -> ReviewOut:
    from shared.errors import NotFoundError

    try:
        review = await svc.get_review(review_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _review_out(review)


@reviews_router.patch(
    "/{review_id}",
    response_model=ReviewOut,
    summary="Transition a review status (start / complete / cancel)",
)
async def patch_performance_review(
    review_id: UUID,
    body: ReviewStatusPatch,
    svc: PerformanceReviewService = Depends(get_review_service),
) -> ReviewOut:
    from shared.errors import BusinessRuleError, NotFoundError

    try:
        if body.action == "start":
            review = await svc.start_review(review_id)
        elif body.action == "complete":
            review = await svc.complete_review(review_id)
        else:
            review = await svc.cancel_review(review_id)
        await svc.db.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BusinessRuleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        )
    return _review_out(review)


# ── Scorecard endpoints ────────────────────────────────────────────────────────


@scorecards_router.get(
    "",
    response_model=List[ScorecardOut],
    summary="List scorecards",
)
async def list_scorecards(
    review_id: Optional[UUID] = None,
    subject_type: Optional[ScorecardSubjectType] = None,
    subject_id: Optional[UUID] = None,
    svc: ScorecardService = Depends(get_scorecard_service),
) -> List[ScorecardOut]:
    from sqlalchemy import and_, select
    from shared.platform_models import Scorecard

    filters = []
    if review_id is not None:
        filters.append(Scorecard.review_id == review_id)
    if subject_type is not None:
        filters.append(Scorecard.subject_type == subject_type)
    if subject_id is not None:
        filters.append(Scorecard.subject_id == subject_id)

    q = select(Scorecard)
    if filters:
        q = q.where(and_(*filters))
    q = q.order_by(Scorecard.generated_at.desc())

    result = await svc.db.execute(q)
    return [_scorecard_out(sc) for sc in result.scalars().all()]


@scorecards_router.get(
    "/{scorecard_id}",
    response_model=ScorecardOut,
    summary="Get a single scorecard",
)
async def get_scorecard(
    scorecard_id: UUID,
    svc: ScorecardService = Depends(get_scorecard_service),
) -> ScorecardOut:
    from shared.errors import NotFoundError

    try:
        sc = await svc.get_scorecard(scorecard_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _scorecard_out(sc)


@scorecards_router.get(
    "/{scorecard_id}/versions",
    response_model=List[ScorecardOut],
    summary="All versions for the same subject×cycle as this scorecard",
)
async def list_scorecard_versions(
    scorecard_id: UUID,
    svc: ScorecardService = Depends(get_scorecard_service),
) -> List[ScorecardOut]:
    from shared.errors import NotFoundError

    try:
        anchor = await svc.get_scorecard(scorecard_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    versions = await svc.list_versions(
        subject_type=anchor.subject_type,
        subject_id=anchor.subject_id,
        cycle_start=anchor.cycle_start,
        cycle_end=anchor.cycle_end,
    )
    return [_scorecard_out(v) for v in versions]


@scorecards_router.post(
    "/generate",
    response_model=ScorecardGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="System/admin: generate (or regenerate) a scorecard immediately",
)
async def generate_scorecard(
    body: ScorecardGenerateRequest,
    svc: ScorecardService = Depends(get_scorecard_service),
) -> ScorecardGenerateResponse:
    """
    Triggers scorecard generation synchronously (suitable for admin use).
    For periodic cadence-driven generation use POST /scorecards/generate-for-review.

    R-18/BR-14/C6: this endpoint only calls ScorecardService.generate() which
    always INSERTs.  No UPDATE/DELETE path exists.
    """
    sc = await svc.generate(
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        cycle_start=body.cycle_start,
        cycle_end=body.cycle_end,
        review_id=body.review_id,
    )
    await svc.db.commit()
    return ScorecardGenerateResponse(
        scorecard_id=sc.id,
        version=sc.version,
        message=(
            f"Scorecard v{sc.version} generated for "
            f"{body.subject_type.value}/{body.subject_id}."
        ),
    )


@scorecards_router.post(
    "/generate-for-review",
    response_model=GenerateForReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue async scorecard generation job for all subjects in a review",
)
async def generate_for_review(
    body: GenerateForReviewRequest,
    scheduler: ScorecardScheduler = Depends(get_scheduler),
) -> GenerateForReviewResponse:
    """
    Enqueues a scorecard generation job for every subject linked to the review.
    Returns 202 immediately; generation happens asynchronously.
    """
    from shared.errors import NotFoundError

    review = await scheduler.db.get(__import__("shared.platform_models", fromlist=["PerformanceReview"]).PerformanceReview, body.review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PerformanceReview {body.review_id} not found.",
        )
    await scheduler.enqueue_for_review(body.review_id)
    return GenerateForReviewResponse(
        message=f"Scorecard generation job enqueued for review {body.review_id}.",
        job_enqueued=True,
    )


# ── serialisation helpers ──────────────────────────────────────────────────────


def _review_out(r) -> ReviewOut:
    return ReviewOut(
        id=r.id,
        school_id=r.school_id,
        department_id=r.department_id,
        cycle_start=r.cycle_start,
        cycle_end=r.cycle_end,
        cadence_days=r.cadence_days,
        status=r.status.value if hasattr(r.status, "value") else r.status,
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
        cancelled_at=r.cancelled_at.isoformat() if r.cancelled_at else None,
        created_at=r.created_at.isoformat(),
        updated_at=r.updated_at.isoformat(),
    )


def _scorecard_out(sc) -> ScorecardOut:
    return ScorecardOut(
        id=sc.id,
        review_id=sc.review_id,
        subject_type=sc.subject_type.value if hasattr(sc.subject_type, "value") else sc.subject_type,
        subject_id=sc.subject_id,
        cycle_start=sc.cycle_start,
        cycle_end=sc.cycle_end,
        version=sc.version,
        superseded_by_id=sc.superseded_by_id,
        rag_status=sc.rag_status.value if hasattr(sc.rag_status, "value") else sc.rag_status,
        pct_kpis_met=float(sc.pct_kpis_met),
        pct_tasks_on_time=float(sc.pct_tasks_on_time),
        open_discrepancy_count=sc.open_discrepancy_count,
        kpi_breakdown=sc.kpi_breakdown,
        generated_at=sc.generated_at.isoformat(),
    )
