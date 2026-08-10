"""
Checklist Scheduler — Architecture §5.7, R-55.
Idempotent ChecklistInstance generation via uniqueness constraint.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.datetime_utils import utc_now
from shared.platform_models import (
    ChecklistInstance,
    ChecklistInstanceStatus,
    ChecklistTemplate,
    ChecklistTemplateStatus,
)


@dataclass
class GenerationResult:
    template_id: UUID
    school_id: UUID
    department_id: UUID
    period_start: datetime
    created: bool
    instance_id: Optional[UUID] = None


class ChecklistScheduler:
    """
    Materializes ChecklistInstance rows from active templates.
    Re-running is a no-op — enforced by ux_checklist_instances_generation_key (R-55).
    """

    FREQUENCY_DELTAS = {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),
        "quarterly": timedelta(days=91),
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_for_school(
        self,
        school_id: UUID,
        *,
        as_of: Optional[datetime] = None,
    ) -> list[GenerationResult]:
        as_of = as_of or utc_now()
        results: list[GenerationResult] = []

        templates = await self._get_active_templates(school_id)
        for template in templates:
            period_start, period_end = self._compute_period(template.frequency_code, as_of)
            if template.department_id is None:
                continue
            result = await self._generate_instance(
                template=template,
                school_id=school_id,
                department_id=template.department_id,
                period_start=period_start,
                period_end=period_end,
            )
            results.append(result)
        await self.db.commit()
        return results

    async def _get_active_templates(self, school_id: UUID) -> list[ChecklistTemplate]:
        result = await self.db.execute(
            select(ChecklistTemplate).where(
                ChecklistTemplate.status == ChecklistTemplateStatus.ACTIVE,
                (ChecklistTemplate.school_id == school_id)
                | (ChecklistTemplate.school_id.is_(None)),
            )
        )
        return list(result.scalars().all())

    def _compute_period(
        self, frequency_code: str, as_of: datetime
    ) -> tuple[datetime, datetime]:
        delta = self.FREQUENCY_DELTAS.get(frequency_code, timedelta(days=1))
        period_start = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + delta
        return period_start, period_end

    async def _generate_instance(
        self,
        *,
        template: ChecklistTemplate,
        school_id: UUID,
        department_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> GenerationResult:
        existing = await self.db.execute(
            select(ChecklistInstance).where(
                ChecklistInstance.template_id == template.template_id,
                ChecklistInstance.template_version == template.version,
                ChecklistInstance.school_id == school_id,
                ChecklistInstance.department_id == department_id,
                ChecklistInstance.period_start == period_start,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            return GenerationResult(
                template_id=template.template_id,
                school_id=school_id,
                department_id=department_id,
                period_start=period_start,
                created=False,
                instance_id=row.id,
            )

        instance = ChecklistInstance(
            template_id=template.template_id,
            template_version=template.version,
            school_id=school_id,
            department_id=department_id,
            period_start=period_start,
            period_end=period_end,
            status=ChecklistInstanceStatus.GENERATED,
        )
        self.db.add(instance)
        await self.db.flush()

        return GenerationResult(
            template_id=template.template_id,
            school_id=school_id,
            department_id=department_id,
            period_start=period_start,
            created=True,
            instance_id=instance.id,
        )
