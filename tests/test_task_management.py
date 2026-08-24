"""
PRS §27 Task Management — acceptance tests.

Verified behaviours
-------------------
T1  A 4th ETA extension request is auto-converted to an escalation (never granted).
T2  Task completion_rule is immutable — update attempt returns a structured rejection.
T3  Creating a task with an ETA in the past is rejected (ValidationError).
T4  Escalation timers fire via the scheduled job; verified with a fast-forwarded clock.
T5  Escalation timers do NOT fire before the SLA threshold elapses.
T6  A second escalation at the same level is NOT duplicated.

All tests run against an in-memory SQLite database (no real-time waits).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database import Base
from shared.platform_models import (
    EscalationRule,
    Task,
    TaskCompletionRule,
    TaskEscalationStatus,
    TaskEtaExtension,
    TaskStatus,
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _utc(dt: datetime) -> datetime:
    """Strip tzinfo to get a naive UTC datetime (matches column storage)."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _future(hours: float = 48.0) -> datetime:
    return _now_naive() + timedelta(hours=hours)


def _past(hours: float = 1.0) -> datetime:
    return _now_naive() - timedelta(hours=hours)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session():
    """
    In-memory SQLite async session with all platform models.

    FK enforcement is intentionally left OFF so tests can insert tasks without
    scaffolding a full school/user/department graph. Business-rule enforcement
    (the FK's actual purpose for tests) is validated by the service layer.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()

# Minimal stub notification service so tests never touch a real queue.
class _StubNotificationService:
    def __init__(self):
        self.dispatched: list[dict] = []

    async def dispatch(self, payload) -> uuid.UUID:
        self.dispatched.append(
            {"user_id": payload.user_id, "category": payload.category, "title": payload.title}
        )
        return uuid.uuid4()


@pytest_asyncio.fixture
async def stub_notifications():
    return _StubNotificationService()


@pytest_asyncio.fixture
async def task_service(db_session, stub_notifications):
    from modules.task_management.services.task_service import TaskService
    return TaskService(db_session, notification_service=stub_notifications)


@pytest_asyncio.fixture
async def escalation_scheduler(db_session, stub_notifications):
    from modules.task_management.services.escalation_scheduler import TaskEscalationScheduler
    from shared.task_queue import InMemoryQueue
    return TaskEscalationScheduler(
        db_session,
        notification_service=stub_notifications,
        queue=InMemoryQueue(),
    )


# Shared UUIDs used across tests
SCHOOL_ID = uuid.uuid4()
DEPT_ID = uuid.uuid4()
USER_A = uuid.uuid4()
USER_B = uuid.uuid4()
CREATOR = uuid.uuid4()


# ── helper: create a minimal task ─────────────────────────────────────────────

async def _make_task(
    service,
    *,
    owners=None,
    completion_rule=TaskCompletionRule.ANY_OWNER,
    eta_hours: float = 48.0,
) -> Task:
    return await service.create_task(
        title="Test Task",
        owner_ids=owners or [USER_A],
        completion_rule=completion_rule,
        eta=_future(eta_hours),
        school_id=SCHOOL_ID,
        created_by=CREATOR,
        department_id=DEPT_ID,
    )


# ══════════════════════════════════════════════════════════════════════════════
# T3 — ETA in the past is rejected at creation
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_task_past_eta_rejected(task_service):
    """R-32/PRS §52: ETA in the past must be rejected with ValidationError."""
    from shared.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await task_service.create_task(
            title="Past ETA Task",
            owner_ids=[USER_A],
            completion_rule=TaskCompletionRule.ANY_OWNER,
            eta=_past(hours=1),           # clearly in the past
            school_id=SCHOOL_ID,
            created_by=CREATOR,
        )

    err = exc_info.value
    assert err.field == "eta"
    assert "future" in err.message.lower()


# ══════════════════════════════════════════════════════════════════════════════
# T2 — completion_rule is immutable after creation
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_completion_rule_is_immutable(task_service):
    """R-31/BR-09/PRS §52: updating completion_rule must return a structured rejection."""
    from shared.errors import BusinessRuleError

    task = await _make_task(task_service, completion_rule=TaskCompletionRule.ANY_OWNER)

    with pytest.raises(BusinessRuleError) as exc_info:
        await task_service.update_completion_rule(task.id, TaskCompletionRule.ALL_OWNERS)

    err = exc_info.value
    assert "immutable" in err.message.lower()
    # structured rejection must carry both current and requested values
    assert err.details["current_rule"] == TaskCompletionRule.ANY_OWNER.value
    assert err.details["requested_rule"] == TaskCompletionRule.ALL_OWNERS.value


# ══════════════════════════════════════════════════════════════════════════════
# T1 — 4th ETA extension is auto-converted to an escalation
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fourth_eta_extension_auto_escalated(task_service, db_session):
    """
    R-33/BR-10/C8/R-42:
      - Extensions 1, 2, 3 are granted; ETA advances each time.
      - Extension 4 is NOT granted; instead an escalation is created with
        trigger="fourth_extension_request" and outcome="auto_escalated".
      - After the 4th attempt the task status becomes ESCALATED.
    """
    from sqlalchemy import select
    from shared.errors import BusinessRuleError
    from shared.platform_models import TaskEscalation

    task = await _make_task(task_service)

    base_eta = task.eta

    # ── grant extensions 1, 2, 3 ─────────────────────────────────────────────
    for i in range(1, 4):
        current_eta = task.eta
        new_eta = current_eta + timedelta(days=i)
        task = await task_service.request_eta_extension(
            task.id,
            requested_by=USER_A,
            new_eta=new_eta,
            justification=f"extension {i}",
        )
        assert task.eta_extension_count == i, f"Expected count={i} after extension {i}"
        assert task.eta > base_eta, "ETA must advance on each granted extension"
        assert task.status == TaskStatus.OPEN, "Task must stay OPEN on granted extensions"

    assert task.eta_extension_count == 3

    # ── 4th attempt — must be auto-escalated ──────────────────────────────────
    task_after_4th = await task_service.request_eta_extension(
        task.id,
        requested_by=USER_A,
        new_eta=task.eta + timedelta(days=7),
        justification="please one more time",
    )

    # ETA must NOT change
    assert task_after_4th.eta == task.eta, "ETA must not change on 4th attempt"

    # extension_count must still be 3 (not incremented for auto-escalated)
    assert task_after_4th.eta_extension_count == 3

    # Task must be ESCALATED
    assert task_after_4th.status == TaskStatus.ESCALATED

    # Verify TaskEtaExtension row with outcome="auto_escalated"
    ext_result = await db_session.execute(
        select(TaskEtaExtension)
        .where(TaskEtaExtension.task_id == task_after_4th.id)
        .order_by(TaskEtaExtension.requested_at.desc())
        .limit(1)
    )
    latest_ext = ext_result.scalar_one()
    assert latest_ext.outcome == "auto_escalated"

    # Verify TaskEscalation record
    esc_result = await db_session.execute(
        select(TaskEscalation).where(TaskEscalation.task_id == task_after_4th.id)
    )
    escalations = esc_result.scalars().all()
    assert len(escalations) == 1
    assert escalations[0].trigger == "fourth_extension_request"
    assert escalations[0].status == TaskEscalationStatus.OPEN


# ══════════════════════════════════════════════════════════════════════════════
# T4 — Escalation timers fire via the scheduled job (fast-forwarded clock)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_escalation_timer_fires_via_scheduled_job(
    task_service, escalation_scheduler, db_session
):
    """
    The escalation scheduler fires when the task's ETA has elapsed by ≥ sla_hours.
    Uses a fast-forwarded 'clock_now' — no real-time wait.
    """
    from sqlalchemy import select
    from shared.platform_models import TaskEscalation

    # Create a task with ETA 2 hours in the future
    task = await _make_task(task_service, eta_hours=2.0)

    # Seed an escalation rule: level 1 triggers after 1 hour of overdue time
    await task_service.upsert_escalation_rule(
        escalation_level=1,
        sla_hours=1,          # 1 h after ETA
        school_id=SCHOOL_ID,
        department_id=DEPT_ID,
    )

    # Fast-forward clock to 4 hours after the task ETA
    fast_forward = task.eta + timedelta(hours=4)

    summary = await escalation_scheduler.run_check(clock_now=fast_forward)

    assert summary["escalations_fired"] == 1
    assert summary["tasks_checked"] >= 1
    assert summary["errors"] == []

    # Verify the escalation record
    result = await db_session.execute(
        select(TaskEscalation).where(TaskEscalation.task_id == task.id)
    )
    escalations = result.scalars().all()
    assert len(escalations) == 1
    assert escalations[0].trigger == "overdue_sla"
    assert escalations[0].escalation_level == 1
    assert escalations[0].status == TaskEscalationStatus.OPEN

    # Task must now be ESCALATED
    await db_session.refresh(task)
    assert task.status == TaskStatus.ESCALATED


# ══════════════════════════════════════════════════════════════════════════════
# T5 — Escalation timer does NOT fire before the SLA threshold
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_escalation_timer_does_not_fire_before_sla(
    task_service, escalation_scheduler, db_session
):
    """
    When the task is overdue but SLA hours haven't elapsed, no escalation fires.
    """
    task = await _make_task(task_service, eta_hours=2.0)

    # SLA: escalate after 6 hours overdue
    await task_service.upsert_escalation_rule(
        escalation_level=1,
        sla_hours=6,
        school_id=SCHOOL_ID,
        department_id=DEPT_ID,
    )

    # Fast-forward to only 3 hours AFTER ETA — SLA (6 h) not yet breached
    fast_forward = task.eta + timedelta(hours=3)
    summary = await escalation_scheduler.run_check(clock_now=fast_forward)

    assert summary["escalations_fired"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# T6 — Duplicate escalation at the same level is NOT created
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_escalation_not_duplicated_at_same_level(
    task_service, escalation_scheduler, db_session
):
    """Running the scheduler twice does not create a second escalation at level 1."""
    from sqlalchemy import select
    from shared.platform_models import TaskEscalation

    task = await _make_task(task_service, eta_hours=2.0)

    await task_service.upsert_escalation_rule(
        escalation_level=1,
        sla_hours=1,
        school_id=SCHOOL_ID,
        department_id=DEPT_ID,
    )

    fast_forward = task.eta + timedelta(hours=4)

    # First pass — fires escalation
    s1 = await escalation_scheduler.run_check(clock_now=fast_forward)
    assert s1["escalations_fired"] == 1

    # Second pass — same clock, should NOT fire again
    s2 = await escalation_scheduler.run_check(clock_now=fast_forward)
    assert s2["escalations_fired"] == 0

    result = await db_session.execute(
        select(TaskEscalation).where(TaskEscalation.task_id == task.id)
    )
    assert len(result.scalars().all()) == 1   # still exactly one


# ══════════════════════════════════════════════════════════════════════════════
# Additional edge-case tests
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_task_requires_at_least_one_owner(task_service):
    """R-30/BR-09: empty owner list must be rejected."""
    from shared.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await task_service.create_task(
            title="No Owners",
            owner_ids=[],
            completion_rule=TaskCompletionRule.ANY_OWNER,
            eta=_future(),
            school_id=SCHOOL_ID,
            created_by=CREATOR,
        )

    assert exc_info.value.field == "owner_ids"


@pytest.mark.asyncio
async def test_all_owners_completion_rule(task_service):
    """
    ALL_OWNERS rule: task is not closed until every owner has recorded completion.
    """
    task = await _make_task(
        task_service,
        owners=[USER_A, USER_B],
        completion_rule=TaskCompletionRule.ALL_OWNERS,
    )

    # First owner completes — task must remain open
    task = await task_service.complete_task(task.id, completed_by=USER_A)
    assert task.status == TaskStatus.OPEN

    # Second (last) owner completes — task closes
    task = await task_service.complete_task(task.id, completed_by=USER_B)
    assert task.status == TaskStatus.COMPLETED
    assert task.completed_at is not None


@pytest.mark.asyncio
async def test_any_owner_completion_rule(task_service):
    """ANY_OWNER rule: first completion closes the task immediately."""
    task = await _make_task(
        task_service,
        owners=[USER_A, USER_B],
        completion_rule=TaskCompletionRule.ANY_OWNER,
    )

    task = await task_service.complete_task(task.id, completed_by=USER_B)
    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_post_approval_completion_rule(task_service):
    """POST_APPROVAL rule: all owners done → PENDING_APPROVAL (not COMPLETED)."""
    task = await _make_task(
        task_service,
        owners=[USER_A],
        completion_rule=TaskCompletionRule.POST_APPROVAL,
    )

    task = await task_service.complete_task(task.id, completed_by=USER_A)
    assert task.status == TaskStatus.PENDING_APPROVAL


@pytest.mark.asyncio
async def test_multi_level_escalation_only_fires_breached_levels(
    task_service, escalation_scheduler, db_session
):
    """
    With two escalation levels (1h and 6h), running at +3h should fire level 1
    only — level 2 (6h) has not elapsed yet.
    """
    from sqlalchemy import select
    from shared.platform_models import TaskEscalation

    task = await _make_task(task_service, eta_hours=2.0)

    await task_service.upsert_escalation_rule(
        escalation_level=1, sla_hours=1,
        school_id=SCHOOL_ID, department_id=DEPT_ID,
    )
    await task_service.upsert_escalation_rule(
        escalation_level=2, sla_hours=6,
        school_id=SCHOOL_ID, department_id=DEPT_ID,
    )

    fast_forward = task.eta + timedelta(hours=3)
    summary = await escalation_scheduler.run_check(clock_now=fast_forward)
    assert summary["escalations_fired"] == 1   # only level 1

    result = await db_session.execute(
        select(TaskEscalation).where(TaskEscalation.task_id == task.id)
    )
    fired = result.scalars().all()
    assert len(fired) == 1
    assert fired[0].escalation_level == 1

    # Advance clock past level 2 threshold
    fast_forward2 = task.eta + timedelta(hours=8)
    summary2 = await escalation_scheduler.run_check(clock_now=fast_forward2)
    assert summary2["escalations_fired"] == 1   # level 2 now fires

    result2 = await db_session.execute(
        select(TaskEscalation).where(TaskEscalation.task_id == task.id)
    )
    all_fired = result2.scalars().all()
    assert len(all_fired) == 2
    levels = {e.escalation_level for e in all_fired}
    assert levels == {1, 2}


@pytest.mark.asyncio
async def test_task_update_excludes_completion_rule(task_service):
    """
    Test that task update endpoint allows updating other fields but not completion_rule.
    This addresses the C2 issue where PATCH was returning 422 because the frontend
    was trying to update completion_rule which is immutable.
    """
    task = await _make_task(task_service, completion_rule=TaskCompletionRule.ANY_OWNER)
    original_rule = task.completion_rule
    original_updated_at = task.updated_at
    
    # Update task fields (excluding completion_rule)
    updated_task = await task_service.update_task(
        task_id=task.id,
        title="Updated Title",
        description="Updated description",
        department_id=DEPT_ID,
    )
    
    assert updated_task.title == "Updated Title"
    assert updated_task.description == "Updated description"
    assert updated_task.completion_rule == original_rule  # Must remain unchanged
    assert updated_task.updated_at >= original_updated_at  # Timestamp should not go backwards


@pytest.mark.asyncio
async def test_task_update_rejects_past_eta(task_service):
    """
    Test that task update rejects ETA in the past, similar to creation validation.
    """
    from shared.errors import ValidationError
    
    task = await _make_task(task_service)
    
    with pytest.raises(ValidationError) as exc_info:
        await task_service.update_task(
            task_id=task.id,
            eta=_past(hours=1),  # Past ETA should be rejected
        )
    
    assert exc_info.value.field == "eta"
    assert "future" in exc_info.value.message.lower()
