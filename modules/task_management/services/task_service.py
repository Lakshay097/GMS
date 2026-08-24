"""
Task Service — PRS §27 Task Management.

Business rules enforced here:
  R-30/BR-09  A Task must have ≥1 Primary Owner; every owner gets notifications.
  R-31/BR-09  completion_rule is IMMUTABLE after creation.
  R-32/PRS§52 ETA must be strictly in the future at creation.
  R-33/BR-10  Maximum THREE ETA extensions per task instance.
              A 4th extension request is auto-converted to an escalation.
  R-42/C8     MAX_ETA_EXTENSIONS = 3 is fixed; not configurable.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.configuration_engine.constants import MAX_ETA_EXTENSIONS
from platform_services.notification_service.service import (
    NotificationPayload,
    NotificationService,
)
from shared.datetime_utils import utc_now
from shared.errors import BusinessRuleError, NotFoundError, ValidationError
from shared.platform_models import (
    EscalationRule,
    NotificationCategory,
    NotificationChannel,
    Task,
    TaskCompletionRule,
    TaskEscalation,
    TaskEscalationStatus,
    TaskEtaExtension,
    TaskOwner,
    TaskOwnerCompletion,
    TaskStatus,
)


class TaskService:
    """
    Core service for PRS §27 Task Management.

    Instantiate with a live AsyncSession (and optionally a pre-built
    NotificationService for dependency-injection in tests).
    """

    def __init__(
        self,
        db: AsyncSession,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.db = db
        self._notification_service = notification_service or NotificationService(db)

    # ── creation ──────────────────────────────────────────────────────────────

    async def create_task(
        self,
        *,
        title: str,
        owner_ids: list[UUID],
        completion_rule: TaskCompletionRule,
        eta: datetime,
        school_id: UUID,
        created_by: UUID,
        description: Optional[str] = None,
        department_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
    ) -> Task:
        """
        Create a new Task.

        Enforces:
          - R-30: ≥1 owner required.
          - R-32: ETA must be strictly in the future.
        """
        # R-30/BR-09 — at least one primary owner
        if not owner_ids:
            raise ValidationError(
                "A Task must have at least one Primary Owner (R-30/BR-09).",
                field="owner_ids",
            )

        # R-32/PRS§52 — ETA must be in the future
        now = utc_now()
        if eta <= now:
            raise ValidationError(
                "Task ETA must be in the future (R-32/PRS §52).",
                field="eta",
                details={"eta": eta.isoformat(), "now": now.isoformat()},
            )

        task = Task(
            id=uuid.uuid4(),
            title=title,
            description=description,
            school_id=school_id,
            department_id=department_id,
            created_by=created_by,
            completion_rule=completion_rule,
            eta=eta,
            eta_extension_count=0,
            status=TaskStatus.OPEN,
            entity_type=entity_type,
            entity_id=entity_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(task)
        await self.db.flush()

        for user_id in owner_ids:
            self.db.add(
                TaskOwner(
                    id=uuid.uuid4(),
                    task_id=task.id,
                    user_id=user_id,
                    assigned_at=now,
                    assigned_by=created_by,
                )
            )

        await self.db.flush()

        # Notify every owner — category 3 (TASK_ASSIGNMENT)
        for user_id in owner_ids:
            await self._notification_service.dispatch(
                NotificationPayload(
                    user_id=user_id,
                    category=NotificationCategory.TASK_ASSIGNMENT.value,
                    title="New Task Assigned",
                    body=f"You have been assigned to task: {title}",
                    channel=NotificationChannel.IN_APP,
                    school_id=school_id,
                    entity_type="task",
                    entity_id=task.id,
                )
            )

        await self.db.commit()
        await self.db.refresh(task)
        return task

    # ── completion ────────────────────────────────────────────────────────────

    async def complete_task(
        self,
        task_id: UUID,
        *,
        completed_by: UUID,
        notes: Optional[str] = None,
    ) -> Task:
        """
        Mark a task as completed by one owner.

        Behaviour depends on completion_rule (R-31 — rule is immutable):
          ANY_OWNER    — first completion closes the whole task immediately.
          ALL_OWNERS   — task closes only once every owner has recorded completion.
          POST_APPROVAL — records completion, moves task to PENDING_APPROVAL.
        """
        task = await self._get_task_or_404(task_id)

        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise BusinessRuleError(
                f"Task is already {task.status.value} and cannot be completed again.",
                details={"task_id": str(task_id), "status": task.status.value},
            )

        owners = await self._get_owner_ids(task_id)
        if completed_by not in owners:
            raise BusinessRuleError(
                "Only a Primary Owner may complete a task.",
                details={"task_id": str(task_id), "user_id": str(completed_by)},
            )

        now = utc_now()

        # Record per-owner completion (idempotent)
        existing = await self.db.execute(
            select(TaskOwnerCompletion).where(
                and_(
                    TaskOwnerCompletion.task_id == task_id,
                    TaskOwnerCompletion.user_id == completed_by,
                )
            )
        )
        if existing.scalar_one_or_none() is None:
            self.db.add(
                TaskOwnerCompletion(
                    id=uuid.uuid4(),
                    task_id=task_id,
                    user_id=completed_by,
                    completed_at=now,
                    notes=notes,
                )
            )
            await self.db.flush()

        if task.completion_rule == TaskCompletionRule.ANY_OWNER:
            task.status = TaskStatus.COMPLETED
            task.completed_at = now

        elif task.completion_rule == TaskCompletionRule.ALL_OWNERS:
            completed_ids = await self._get_completed_owner_ids(task_id)
            if owners <= completed_ids:
                task.status = TaskStatus.COMPLETED
                task.completed_at = now

        elif task.completion_rule == TaskCompletionRule.POST_APPROVAL:
            completed_ids = await self._get_completed_owner_ids(task_id)
            if owners <= completed_ids:
                task.status = TaskStatus.PENDING_APPROVAL

        task.updated_at = now
        await self.db.commit()
        await self.db.refresh(task)
        return task


    # ── task updates ────────────────────────────────────────────────────────────

    async def update_task(
        self,
        task_id: UUID,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        eta: Optional[datetime] = None,
        department_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
    ) -> Task:
        """
        Update task fields (excluding completion_rule which is immutable).
        For ETA changes, prefer the dedicated eta-extension endpoint.
        """
        task = await self._get_task_or_404(task_id)
        
        now = utc_now()
        
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if eta is not None:
            # Validate ETA is in the future if being changed
            if eta <= now:
                raise ValidationError(
                    "Task ETA must be in the future (R-32/PRS §52).",
                    field="eta",
                    details={"eta": eta.isoformat(), "now": now.isoformat()},
                )
            task.eta = eta
        if department_id is not None:
            task.department_id = department_id
        if entity_type is not None:
            task.entity_type = entity_type
        if entity_id is not None:
            task.entity_id = entity_id
            
        task.updated_at = now
        await self.db.commit()
        await self.db.refresh(task)
        return task

    # ── completion rule immutability ──────────────────────────────────────────

    async def update_completion_rule(self, task_id: UUID, new_rule: TaskCompletionRule) -> None:
        """
        Always raises BusinessRuleError — completion_rule is IMMUTABLE (R-31/BR-09/PRS §52).
        """
        task = await self._get_task_or_404(task_id)
        raise BusinessRuleError(
            "Task completion_rule is immutable and cannot be changed after creation "
            "(R-31/BR-09/PRS §52).",
            details={
                "task_id": str(task_id),
                "current_rule": task.completion_rule.value,
                "requested_rule": new_rule.value,
            },
        )

    # ── ETA extension ─────────────────────────────────────────────────────────

    async def request_eta_extension(
        self,
        task_id: UUID,
        *,
        requested_by: UUID,
        new_eta: datetime,
        justification: Optional[str] = None,
    ) -> Task:
        """
        Request an ETA extension.

        Extensions 1–3 are granted; a 4th request is auto-converted to escalation.
        """
        task = await self._get_task_or_404(task_id)

        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise BusinessRuleError(
                f"Cannot extend ETA of a {task.status.value} task.",
                details={"task_id": str(task_id)},
            )

        now = utc_now()

        # R-33/BR-10 — 4th attempt → auto-escalate
        if task.eta_extension_count >= MAX_ETA_EXTENSIONS:
            return await self._auto_escalate_fourth_extension(
                task=task,
                requested_by=requested_by,
                requested_eta=new_eta,
                justification=justification,
                now=now,
            )

        if new_eta <= now:
            raise ValidationError(
                "Extended ETA must be in the future.",
                field="new_eta",
                details={"new_eta": new_eta.isoformat(), "now": now.isoformat()},
            )

        if new_eta <= task.eta:
            raise ValidationError(
                "Extended ETA must be later than the current ETA.",
                field="new_eta",
                details={
                    "new_eta": new_eta.isoformat(),
                    "current_eta": task.eta.isoformat(),
                },
            )

        previous_eta = task.eta
        self.db.add(
            TaskEtaExtension(
                id=uuid.uuid4(),
                task_id=task_id,
                requested_by=requested_by,
                previous_eta=previous_eta,
                requested_eta=new_eta,
                outcome="granted",
                justification=justification,
                requested_at=now,
            )
        )

        task.eta = new_eta
        task.eta_extension_count += 1
        task.updated_at = now
        await self.db.flush()

        owners = await self._get_owner_ids(task_id)
        for user_id in owners:
            await self._notification_service.dispatch(
                NotificationPayload(
                    user_id=user_id,
                    category=NotificationCategory.TASK_ASSIGNMENT.value,
                    title="Task ETA Extended",
                    body=(
                        f"ETA for task '{task.title}' has been extended to "
                        f"{new_eta.strftime('%Y-%m-%d %H:%M')} UTC "
                        f"(extension {task.eta_extension_count}/{MAX_ETA_EXTENSIONS})."
                    ),
                    channel=NotificationChannel.IN_APP,
                    school_id=task.school_id,
                    entity_type="task",
                    entity_id=task.id,
                )
            )

        await self.db.commit()
        await self.db.refresh(task)
        return task

    # ── escalation rules CRUD ─────────────────────────────────────────────────

    async def upsert_escalation_rule(
        self,
        *,
        escalation_level: int,
        sla_hours: int,
        school_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        escalate_to_role_id: Optional[str] = None,
    ) -> None:
        """Create or replace one row in escalation_rules."""
        result = await self.db.execute(
            select(EscalationRule).where(
                and_(
                    EscalationRule.department_id == department_id,
                    EscalationRule.school_id == school_id,
                    EscalationRule.escalation_level == escalation_level,
                )
            )
        )
        row = result.scalar_one_or_none()
        now = utc_now()
        if row:
            row.sla_hours = sla_hours
            row.escalate_to_role_id = escalate_to_role_id
            row.updated_at = now
        else:
            self.db.add(
                EscalationRule(
                    id=uuid.uuid4(),
                    department_id=department_id,
                    school_id=school_id,
                    escalation_level=escalation_level,
                    sla_hours=sla_hours,
                    escalate_to_role_id=escalate_to_role_id,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        await self.db.commit()

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _get_task_or_404(self, task_id: UUID) -> Task:
        task = await self.db.get(Task, task_id)
        if task is None:
            raise NotFoundError("Task")
        return task

    async def _get_owner_ids(self, task_id: UUID) -> set[UUID]:
        result = await self.db.execute(
            select(TaskOwner.user_id).where(TaskOwner.task_id == task_id)
        )
        return {row for row in result.scalars().all()}

    async def _get_completed_owner_ids(self, task_id: UUID) -> set[UUID]:
        result = await self.db.execute(
            select(TaskOwnerCompletion.user_id).where(
                TaskOwnerCompletion.task_id == task_id
            )
        )
        return {row for row in result.scalars().all()}

    async def _auto_escalate_fourth_extension(
        self,
        *,
        task: Task,
        requested_by: UUID,
        requested_eta: datetime,
        justification: Optional[str],
        now: datetime,
    ) -> Task:
        """
        Convert a 4th ETA extension request into a TaskEscalation.
        ETA is NOT updated; outcome logged as "auto_escalated".
        Task status → ESCALATED.
        Sends mandatory cat-1 ESCALATION notification to all owners.
        """
        self.db.add(
            TaskEtaExtension(
                id=uuid.uuid4(),
                task_id=task.id,
                requested_by=requested_by,
                previous_eta=task.eta,
                requested_eta=requested_eta,
                outcome="auto_escalated",
                justification=justification,
                requested_at=now,
            )
        )

        self.db.add(
            TaskEscalation(
                id=uuid.uuid4(),
                task_id=task.id,
                trigger="fourth_extension_request",
                escalation_level=1,
                status=TaskEscalationStatus.OPEN,
                notes=(
                    f"Auto-escalated: {MAX_ETA_EXTENSIONS} ETA extensions already used. "
                    f"Requested ETA: {requested_eta.isoformat()}. "
                    f"Justification: {justification or 'none provided'}."
                ),
                escalated_at=now,
            )
        )

        task.status = TaskStatus.ESCALATED
        task.updated_at = now
        await self.db.flush()

        owners = await self._get_owner_ids(task.id)
        for user_id in owners:
            await self._notification_service.dispatch(
                NotificationPayload(
                    user_id=user_id,
                    category=NotificationCategory.ESCALATION.value,
                    title="Task Escalated — ETA Extension Limit Reached",
                    body=(
                        f"Task '{task.title}' has been escalated because the maximum "
                        f"number of ETA extensions ({MAX_ETA_EXTENSIONS}) has been reached. "
                        "No further extensions will be granted."
                    ),
                    channel=NotificationChannel.IN_APP,
                    school_id=task.school_id,
                    entity_type="task",
                    entity_id=task.id,
                )
            )

        await self.db.commit()
        await self.db.refresh(task)
        return task
