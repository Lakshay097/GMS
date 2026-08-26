"""
Task Management API routes — PRS §27.

POST   /tasks                           create a task
GET    /tasks/{task_id}                 fetch a task
POST   /tasks/{task_id}/complete        record owner completion
PATCH  /tasks/{task_id}/completion-rule always returns 422 (immutable — R-31)
POST   /tasks/{task_id}/eta-extension   extend ETA (4th → auto-escalate — R-33)
POST   /escalation-rules                upsert per-dept escalation rule
POST   /tasks/escalation-check          admin: trigger an ad-hoc check
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.task_management.services.escalation_scheduler import TaskEscalationScheduler
from modules.task_management.services.task_service import TaskService
from shared.database import get_db
from shared.middleware.tenancy import require_tenant_context, apply_tenant_filter
from shared.platform_models import TaskCompletionRule

router = APIRouter(prefix="/tasks", tags=["task-management"])
escalation_rules_router = APIRouter(prefix="/escalation-rules", tags=["task-management"])


# ── schemas ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    owner_ids: List[UUID] = Field(..., min_length=1)
    completion_rule: TaskCompletionRule
    eta: datetime
    school_id: UUID
    created_by: UUID
    department_id: Optional[UUID] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None


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
    new_eta: datetime
    justification: Optional[str] = None


class EtaExtensionResponse(BaseModel):
    task: TaskOut
    outcome: str
    message: str


class EscalationRuleCreate(BaseModel):
    escalation_level: int = Field(..., ge=1)
    sla_hours: int = Field(..., ge=1)
    school_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    escalate_to_role_id: Optional[str] = None  # Role name string (e.g., 'admin') or UUID


class EscalationRuleResponse(BaseModel):
    message: str


class EscalationCheckResponse(BaseModel):
    tasks_checked: int
    escalations_fired: int
    errors: List[str]


# ── DI ────────────────────────────────────────────────────────────────────────

def get_task_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    return TaskService(db)


def get_escalation_scheduler(db: AsyncSession = Depends(get_db)) -> TaskEscalationScheduler:
    return TaskEscalationScheduler(db)


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/escalation-check", response_model=EscalationCheckResponse)
async def run_escalation_check(
    tenant_context = Depends(require_tenant_context),
    scheduler: TaskEscalationScheduler = Depends(get_escalation_scheduler),
) -> EscalationCheckResponse:
    """Admin-only endpoint. In production, triggered by the async queue."""
    from shared.models import UserRole
    user_roles_lower = [r.lower() if isinstance(r, str) else r for r in tenant_context.roles]
    if UserRole.SUPERADMIN.value not in user_roles_lower and UserRole.ADMIN.value not in user_roles_lower:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admin or SuperAdmin can run escalation checks")
    summary = await scheduler.run_check()
    return EscalationCheckResponse(**summary)


@router.get("", response_model=List[TaskOut])
async def list_tasks(
    tenant_context = Depends(require_tenant_context),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page (max 100)"),
    service: TaskService = Depends(get_task_service),
) -> List[TaskOut]:
    """List tasks with tenant isolation and pagination (per R-02)"""
    from sqlalchemy import select as sa_select
    from shared.platform_models import Task
    
    # Build base query with tenant isolation
    query = sa_select(Task).order_by(Task.created_at.desc())
    query = apply_tenant_filter(query, tenant_context)
    
    # Apply pagination at database level using LIMIT/OFFSET
    offset = (page - 1) * page_size
    query = query.limit(page_size).offset(offset)
    
    result = await service.db.execute(query)
    tasks = result.scalars().all()
    return [TaskOut.model_validate(task) for task in tasks]


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    tenant_context = Depends(require_tenant_context),
    service: TaskService = Depends(get_task_service),
) -> TaskOut:
    # Only SuperAdmin, Admin, or Checker can create tasks
    from shared.models import UserRole
    allowed_roles = {UserRole.SUPERADMIN.value, UserRole.ADMIN.value, UserRole.CHECKER.value}
    user_roles_lower = [r.lower() if isinstance(r, str) else r for r in tenant_context.roles]
    if not any(r in allowed_roles for r in user_roles_lower):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to create tasks")
    # Enforce school_id matches tenant scope for non-superadmin
    if "superadmin" not in user_roles_lower:
        if str(body.school_id) != tenant_context.school_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create tasks for other schools")
    task = await service.create_task(
        title=body.title,
        description=body.description,
        owner_ids=body.owner_ids,
        completion_rule=body.completion_rule,
        eta=body.eta,
        school_id=body.school_id,
        created_by=UUID(tenant_context.user_id),
        department_id=body.department_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
    )
    return TaskOut.model_validate(task)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: UUID,
    tenant_context = Depends(require_tenant_context),
    service: TaskService = Depends(get_task_service),
) -> TaskOut:
    task = await service._get_task_or_404(task_id)
    # Verify task is within tenant scope
    if "superadmin" not in [r.lower() if isinstance(r, str) else r for r in tenant_context.roles]:
        if str(task.school_id) != tenant_context.school_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskOut.model_validate(task)


@router.post("/{task_id}/complete", response_model=TaskCompleteResponse)
async def complete_task(
    task_id: UUID,
    body: TaskCompleteRequest,
    tenant_context = Depends(require_tenant_context),
    service: TaskService = Depends(get_task_service),
) -> TaskCompleteResponse:
    # Verify task is within tenant scope
    task = await service._get_task_or_404(task_id)
    if "superadmin" not in [r.lower() if isinstance(r, str) else r for r in tenant_context.roles]:
        if str(task.school_id) != tenant_context.school_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task = await service.complete_task(task_id, completed_by=UUID(tenant_context.user_id), notes=body.notes)
    return TaskCompleteResponse(
        task=TaskOut.model_validate(task),
        message=f"Task status is now '{task.status.value}'.",
    )


@router.patch("/{task_id}/completion-rule", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
async def update_completion_rule(
    task_id: UUID,
    body: CompletionRulePatchRequest,
    tenant_context = Depends(require_tenant_context),
    service: TaskService = Depends(get_task_service),
) -> None:
    """Always 422 — completion_rule is immutable (R-31/BR-09/PRS §52)."""
    await service.update_completion_rule(task_id, body.completion_rule)


@router.post("/{task_id}/eta-extension", response_model=EtaExtensionResponse)
async def request_eta_extension(
    task_id: UUID,
    body: EtaExtensionRequest,
    tenant_context = Depends(require_tenant_context),
    service: TaskService = Depends(get_task_service),
) -> EtaExtensionResponse:
    # Verify task is within tenant scope
    task_check = await service._get_task_or_404(task_id)
    if "superadmin" not in [r.lower() if isinstance(r, str) else r for r in tenant_context.roles]:
        if str(task_check.school_id) != tenant_context.school_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    from sqlalchemy import select as sa_select
    from shared.platform_models import TaskEtaExtension

    task = await service.request_eta_extension(
        task_id,
        requested_by=UUID(tenant_context.user_id),
        new_eta=body.new_eta,
        justification=body.justification,
    )
    result = await service.db.execute(
        sa_select(TaskEtaExtension)
        .where(TaskEtaExtension.task_id == task_id)
        .order_by(TaskEtaExtension.requested_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    outcome = latest.outcome if latest else "granted"
    message = (
        "ETA extension granted."
        if outcome == "granted"
        else (
            "ETA extension limit reached — task has been automatically escalated "
            "(R-33/BR-10). No further extensions will be granted."
        )
    )
    return EtaExtensionResponse(task=TaskOut.model_validate(task), outcome=outcome, message=message)


@escalation_rules_router.get("", response_model=List[dict])
async def list_escalation_rules(
    tenant_context = Depends(require_tenant_context),
    service: TaskService = Depends(get_task_service),
):
    """List all escalation rules with resolved names."""
    from sqlalchemy import select as sa_select, or_
    from shared.platform_models import EscalationRule
    from shared.models import School, Department, UserRole
    
    result = await service.db.execute(
        sa_select(EscalationRule).order_by(EscalationRule.escalation_level)
    )
    rules = result.scalars().all()
    
    # Build role lookup
    role_lookup = {r.value: r.value.capitalize() for r in UserRole}
    
    # Batch-fetch schools and departments
    school_ids = [r.school_id for r in rules if r.school_id]
    dept_ids = [r.department_id for r in rules if r.department_id]
    
    school_map = {}
    if school_ids:
        schools_result = await service.db.execute(
            sa_select(School).where(School.id.in_(school_ids))
        )
        school_map = {str(s.id): s.name for s in schools_result.scalars().all()}
    
    dept_map = {}
    if dept_ids:
        dept_result = await service.db.execute(
            sa_select(Department).where(Department.id.in_(dept_ids))
        )
        dept_map = {str(d.id): d.name for d in dept_result.scalars().all()}
    
    return [
        {
            "id": str(rule.id),
            "escalation_level": rule.escalation_level,
            "sla_hours": rule.sla_hours,
            "school_id": str(rule.school_id) if rule.school_id else None,
            "school_name": school_map.get(str(rule.school_id)) if rule.school_id else None,
            "department_id": str(rule.department_id) if rule.department_id else None,
            "department_name": dept_map.get(str(rule.department_id)) if rule.department_id else None,
            "escalate_to_role_id": str(rule.escalate_to_role_id) if rule.escalate_to_role_id else None,
            "escalate_to_role_name": role_lookup.get(str(rule.escalate_to_role_id)) if rule.escalate_to_role_id else None,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
        }
        for rule in rules
    ]


@escalation_rules_router.post("", response_model=EscalationRuleResponse, status_code=status.HTTP_201_CREATED)
async def upsert_escalation_rule(
    body: EscalationRuleCreate,
    tenant_context = Depends(require_tenant_context),
    service: TaskService = Depends(get_task_service),
) -> EscalationRuleResponse:
    # Only SuperAdmin or Admin can manage escalation rules
    from shared.models import UserRole
    user_roles_lower = [r.lower() if isinstance(r, str) else r for r in tenant_context.roles]
    if UserRole.SUPERADMIN.value not in user_roles_lower and UserRole.ADMIN.value not in user_roles_lower:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admin or SuperAdmin can manage escalation rules")
    # SECURITY: Validate school_id matches tenant scope for non-SuperAdmin (prevent cross-tenant escalation rules)
    is_superadmin = UserRole.SUPERADMIN.value in user_roles_lower
    if not is_superadmin and body.school_id and str(body.school_id) != tenant_context.school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create escalation rule for another school")
    await service.upsert_escalation_rule(
        escalation_level=body.escalation_level,
        sla_hours=body.sla_hours,
        school_id=body.school_id,
        department_id=body.department_id,
        escalate_to_role_id=body.escalate_to_role_id,
    )
    return EscalationRuleResponse(message="Escalation rule saved.")
