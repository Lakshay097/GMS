"""
Task Management API routes — PRS §27.

Endpoints
---------
POST   /tasks                             create a task
GET    /tasks/{task_id}                   fetch a task
POST   /tasks/{task_id}/complete          record owner completion
PATCH  /tasks/{task_id}/completion-rule   always returns 422 (immutable)
POST   /tasks/{task_id}/eta-extension     request ETA extension (4th auto-escalates)
POST   /escalation-rules                  upsert a per-dept escalation rule
POST   /tasks/escalation-check            trigger an ad-hoc escalation check (admin)
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.task_management.services.escalation_scheduler import TaskEscalationScheduler
from modules.task_management.services.task_service import TaskService
from shared.database import get_db
from shared.platform_models import TaskCompletionRule

router = APIRouter(prefix="/tasks", tags=["task-management"])
escalation_rules_router = APIRouter(prefix="/escalation-rules", tags=["task-management"])


# ── request / response schemas ────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    owner_ids: List[UUID] = Field(..., min_length=1, description="≥1 Primary Owner required (R-30)")
    completion_rule: TaskCompletionRule = Field(
        ...,
        description="Immutable after creation (R-31/BR-09/PRS §52)",
    )
    eta: datetime = Field(..., description="Must be in the future at creation (R-32)")
    school_id: UUID
    created_by: UUID
    department_id: Optional[UUID] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None


class TaskOwnerOut(BaseModel):
    id: UUID
    user_id: UUID
    assigned_at: datetime


class TaskOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    school_id: UUID
    department_id: Optional[UUID]
    created_by: UUID
    completion_rule: TaskCompletionRule
    eta: datetime
    eta_extension_count: int
    status: str
    entity_type: Optional[str]
    entity_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskCompleteRequest(BaseModel):
    completed_by: UUID
    notes: Optional[str] = None


class TaskCompleteResponse(BaseModel):
    task: TaskOut
    message: str


class CompletionRulePatchRequest(BaseModel):
    completion_rule: TaskCompletionRule


class EtaExtensionRequest(BaseModel):
    requested_by: UUID
    new_eta: datetime = Field(..., description="Must be later than current ETA and in the future")
    justification: Optional[str] = None


class EtaExtensionResponse(BaseModel):
    task: TaskOut
    outcome: str  # "granted" or "auto_escalated"
    message: str


class EscalationRuleCreate(BaseModel):
    escalation_level: int = Field(..., ge=1)
    sla_hours: int = Field(..., ge=1, description="Hours after ETA before this level fires")
    school_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    escalate_to_role_id: Optional[UUID] = None


class EscalationRuleResponse(BaseModel):
    message: str


class EscalationCheckResponse(BaseModel):
    tasks_checked: int
    escalations_fired: int
    errors: List[str]


# ── dependency injection ──────────────────────────────────────────────────────

def get_task_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    return TaskService(db)


def get_escalation_scheduler(db: AsyncSession = Depends(get_db)) -> TaskEscalationScheduler:
    return TaskEscalationScheduler(db)


# ── task endpoints ────────────────────────────────────────────────────────────

@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    service: TaskService = Depends(get_task_service),
) -> TaskOut:
    task = await service.create_task(
        title=body.title,
        description=body.description,
        owner_ids=body.owner_ids,
        completion_rule=body.completion_rule,
        eta=body.eta,
        school_id=body.school_id,
        created_by=body.created_by,
        department_id=body.department_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
    )
    return TaskOut.model_validate(task)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: UUID,
    service: TaskService = Depends(get_task_service),
) -> TaskOut:
    task = await service._get_task_or_404(task_id)
    return TaskOut.model_validate(task)


@router.post("/{task_id}/complete", response_model=TaskCompleteResponse)
async def complete_task(
    task_id: UUID,
    body: TaskCompleteRequest,
    service: TaskService = Depends(get_task_service),
) -> TaskCompleteResponse:
    task = await service.complete_task(
        task_id,
        completed_by=body.completed_by,
        notes=body.notes,
    )
    return TaskCompleteResponse(
        task=TaskOut.model_validate(task),
        message=f"Task status is now '{task.status.value}'.",
    )


@router.patch("/{task_id}/completion-rule", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
async def update_completion_rule(
    task_id: UUID,
    body: CompletionRulePatchRequest,
    service: TaskService = Depends(get_task_service),
) -> None:
    """
    Always returns 422 — completion_rule is immutable after creation (R-31/BR-09/PRS §52).
    Intentionally exposed so API consumers receive a structured rejection rather than a 404.
    """
    await service.update_completion_rule(task_id, body.completion_rule)


@router.post("/{task_id}/eta-extension", response_model=EtaExtensionResponse)
async def request_eta_extension(
    task_id: UUID,
    body: EtaExtensionRequest,
    service: TaskService = Depends(get_task_service),
) -> EtaExtensionResponse:
    """
    Request an ETA extension (R-33/BR-10).
    Extensions 1–3 are granted; a 4th request is auto-converted to an escalation.
    """
    task = await service.request_eta_extension(
        task_id,
        requested_by=body.requested_by,
        new_eta=body.new_eta,
        justification=body.justification,
    )

    # Determine outcome from the most recent extension record
    from sqlalchemy import select as sa_select
    from shared.platform_models import TaskEtaExtension
    result = await service.db.execute(
        sa_select(TaskEtaExtension)
        .where(TaskEtaExtension.task_id == task_id)
        .order_by(TaskEtaExtension.requested_at.desc())
        .limit(1)
    )
    latest_ext = result.scalar_one_or_none()
    outcome = latest_ext.outcome if latest_ext else "granted"

    message = (
        "ETA extension granted."
        if outcome == "granted"
        else (
            "ETA extension limit reached — task has been automatically escalated "
            "(R-33/BR-10). No further extensions will be granted."
        )
    )
    return EtaExtensionResponse(
        task=TaskOut.model_validate(task),
        outcome=outcome,
        message=message,
    )


# ── escalation-rules endpoint ─────────────────────────────────────────────────

@escalation_rules_router.post(
    "",
    response_model=EscalationRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_escalation_rule(
    body: EscalationRuleCreate,
    service: TaskService = Depends(get_task_service),
) -> EscalationRuleResponse:
    await service.upsert_escalation_rule(
        escalation_level=body.escalation_level,
        sla_hours=body.sla_hours,
        school_id=body.school_id,
        department_id=body.department_id,
        escalate_to_role_id=body.escalate_to_role_id,
    )
    return EscalationRuleResponse(message="Escalation rule saved.")


# ── admin: ad-hoc escalation check ───────────────────────────────────────────

@router.post("/escalation-check", response_model=EscalationCheckResponse)
async def run_escalation_check(
    scheduler: TaskEscalationScheduler = Depends(get_escalation_scheduler),
) -> EscalationCheckResponse:
    """
    Trigger an immediate escalation check (admin / cron endpoint).
    In production this job is triggered by the async queue scheduler, not here.
    """
    summary = await scheduler.run_check()
    return EscalationCheckResponse(**summary)
