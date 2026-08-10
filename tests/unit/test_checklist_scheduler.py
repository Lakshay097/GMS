"""Unit tests for Checklist Scheduler — Architecture §5.7, R-55."""
import uuid
from datetime import datetime

import pytest
from sqlalchemy import func, select

from platform_services.checklist_scheduler.service import ChecklistScheduler
from shared.datetime_utils import utc_now
from shared.platform_models import ChecklistInstance, ChecklistTemplate, ChecklistTemplateStatus


@pytest.mark.asyncio
async def test_R55_checklist_scheduler_idempotent_double_run(db, school, department):
    """R-55: double-run produces zero duplicate instances."""
    template = ChecklistTemplate(
        template_id=uuid.uuid4(),
        version=1,
        title="Daily Cleanliness",
        school_id=school.id,
        department_id=department.id,
        frequency_code="daily",
        status=ChecklistTemplateStatus.ACTIVE,
        created_at=utc_now(),
    )
    db.add(template)
    await db.commit()

    scheduler = ChecklistScheduler(db)
    as_of = datetime(2026, 8, 7, 10, 0, 0)

    results_1 = await scheduler.run_for_school(school.id, as_of=as_of)
    results_2 = await scheduler.run_for_school(school.id, as_of=as_of)

    created_first = sum(1 for r in results_1 if r.created)
    created_second = sum(1 for r in results_2 if r.created)

    assert created_first == 1
    assert created_second == 0

    count = await db.scalar(select(func.count()).select_from(ChecklistInstance))
    assert count == 1
