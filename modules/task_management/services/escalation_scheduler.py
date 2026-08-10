"""
Task Escalation Scheduler — PRS §27 Escalation Matrix.

Runs as a scheduled job on the async queue (Prompt 1 / AQ3).
Never called inline with any user request.

The `clock_now` parameter on `run_check` lets tests fast-forward time.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.notification_service.service import (
    NotificationPayload,
    NotificationService,
)
from shared.datetime_utils import utc_now
from shared.platform_models import (
    EscalationRule,
    NotificationCategory,
    NotificationChannel,
    Task,
    TaskEscalation,
    TaskEscalationStatus,
    TaskOwner,
    TaskStatus,
)
from shared.task_queue import JobRegistry, get_queue_instance

ESCALATION_QUEUE = "task_escalation_checks"
ESCALATION_CHECK_JOB_TYPE = "task_escalation_check"

_TERMINAL = frozenset({TaskStatus.COMPLETED, TaskStatus.CANCELLED})


class TaskEscalationScheduler:
    """
    Checks overdue tasks against their department escalation matrix and
    fires escalations for each elapsed SLA tier.
    """

    def __init__(
        self,
        db: AsyncSession,
        notification_service: Optional[NotificationService] = None,
        queue=None,
    ) -> None:
        self.db = db
        self._notification_service = notification_service or NotificationService(db)
        self._queue = queue or get_queue_instance()
        self._register_job_handler()

    async def enqueue_check(self, delay_seconds: int = 0) -> str:
        """Enqueue a single escalation-check job onto the async queue."""
        return await self._queue.enqueue(
            ESCALATION_QUEUE,
            {"job_type": ESCALATION_CHECK_JOB_TYPE},
            delay_seconds=delay_seconds,
        )

    async def run_check(self, clock_now: Optional[datetime] = None) -> dict:
        """
        Core escalation pass against all non-terminal overdue tasks.

        Returns {"tasks_checked": int, "escalations_fired": int, "errors": list[str]}.
        Pass clock_now to fast-forward the clock in tests.
        """
        now = clock_now or utc_now()
        summary: dict = {"tasks_checked": 0, "escalations_fired": 0, "errors": []}

        result = await self.db.execute(
            select(Task).where(
                and_(
                    Task.eta < now,
                    Task.status.notin_([s.value for s in _TERMINAL]),
                )
            )
        )
        overdue_tasks: list[Task] = list(result.scalars().all())
        summary["tasks_checked"] = len(overdue_tasks)

        for task in overdue_tasks:
            try:
                fired = await self._check_task(task, now)
                summary["escalations_fired"] += fired
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append(f"task {task.id}: {exc}")

        return summary

    async def _check_task(self, task: Task, now: datetime) -> int:
        rules = await self._resolve_escalation_rules(task.department_id, task.school_id)
        if not rules:
            return 0

        hours_overdue = (now - task.eta).total_seconds() / 3600
        fired = 0

        for rule in rules:
            if not rule.is_active:
                continue
            if hours_overdue < rule.sla_hours:
                continue

            # Skip if an open escalation at this level already exists
            existing = await self.db.execute(
                select(TaskEscalation).where(
                    and_(
                        TaskEscalation.task_id == task.id,
                        TaskEscalation.escalation_level == rule.escalation_level,
                        TaskEscalation.trigger == "overdue_sla",
                        TaskEscalation.status != TaskEscalationStatus.RESOLVED.value,
                    )
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            escalation = TaskEscalation(
                task_id=task.id,
                trigger="overdue_sla",
                escalation_level=rule.escalation_level,
                escalated_to_role_id=rule.escalate_to_role_id,
                status=TaskEscalationStatus.OPEN,
                notes=(
                    f"SLA breach: task overdue by {hours_overdue:.1f} h "
                    f"(SLA level {rule.escalation_level} = {rule.sla_hours} h)."
                ),
                escalated_at=now,
            )
            self.db.add(escalation)

            if task.status != TaskStatus.ESCALATED:
                task.status = TaskStatus.ESCALATED
                task.updated_at = now

            await self.db.flush()
            fired += 1

            await self._notify_owners(task, escalation, now)

        if fired:
            await self.db.commit()

        return fired

    async def _resolve_escalation_rules(
        self,
        department_id: Optional[UUID],
        school_id: Optional[UUID],
    ) -> list[EscalationRule]:
        """
        Precedence: dept-specific → school-wide → global defaults.
        Returns the first non-empty tier.
        """
        for dept_id, sch_id in [
            (department_id, school_id),
            (None, school_id),
            (None, None),
        ]:
            result = await self.db.execute(
                select(EscalationRule).where(
                    and_(
                        EscalationRule.department_id == dept_id,
                        EscalationRule.school_id == sch_id,
                        EscalationRule.is_active.is_(True),
                    )
                ).order_by(EscalationRule.escalation_level)
            )
            rows = list(result.scalars().all())
            if rows:
                return rows
        return []

    async def _notify_owners(
        self,
        task: Task,
        escalation: TaskEscalation,
        now: datetime,
    ) -> None:
        result = await self.db.execute(
            select(TaskOwner.user_id).where(TaskOwner.task_id == task.id)
        )
        for user_id in result.scalars().all():
            await self._notification_service.dispatch(
                NotificationPayload(
                    user_id=user_id,
                    category=NotificationCategory.ESCALATION.value,
                    title=f"Task Escalated — Level {escalation.escalation_level}",
                    body=(
                        f"Task '{task.title}' has breached its SLA and been escalated "
                        f"to level {escalation.escalation_level}. "
                        f"Original ETA: {task.eta.strftime('%Y-%m-%d %H:%M')} UTC."
                    ),
                    channel=NotificationChannel.IN_APP,
                    school_id=task.school_id,
                    entity_type="task",
                    entity_id=task.id,
                )
            )

    def _register_job_handler(self) -> None:
        registry = JobRegistry()

        async def _handle(job_data: dict) -> None:
            await self.run_check()

        if ESCALATION_CHECK_JOB_TYPE not in registry.handlers:
            registry.register(ESCALATION_CHECK_JOB_TYPE, _handle)
