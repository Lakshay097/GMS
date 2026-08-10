"""Unit tests for Audit Log Service — Architecture §5.5, R-19."""
import uuid

import pytest
from sqlalchemy import select

from platform_services.audit_log_service.event_types import AuditEventType
from platform_services.audit_log_service.service import AuditLogService
from shared.models import AuditLogEntry


@pytest.mark.asyncio
async def test_audit_log_append_only(db, user):
    service = AuditLogService(db)
    entry_id = await service.append(
        AuditEventType.CONFIG_CHANGED,
        "configuration",
        uuid.uuid4(),
        actor_id=user.id,
        new_values={"key": "session_timeout_minutes", "value": 30},
    )
    await db.commit()

    result = await db.execute(select(AuditLogEntry).where(AuditLogEntry.id == entry_id))
    entry = result.scalar_one()
    assert entry.action == "config_changed"
    assert entry.user_id == user.id


@pytest.mark.asyncio
async def test_v15_audit_event_types(db, user):
    """v1.5 event types: duplicate blocked, override, reopen, compliance run, evidence deletion."""
    service = AuditLogService(db)
    obs_id = uuid.uuid4()

    await service.log_duplicate_blocked(obs_id, actor_id=user.id, details={"window_minutes": 60})
    await service.log_duplicate_override(obs_id, actor_id=user.id, justification="Approved by admin")
    await service.log_reopen_request(obs_id, actor_id=user.id, reason="Missed deadline")
    await service.log_reopen_approval(obs_id, actor_id=user.id, approved=True)
    await service.log_compliance_scheduler_run(
        uuid.uuid4(), records_generated=5, records_backfilled=2, status="success"
    )
    await service.log_evidence_deletion(obs_id, actor_id=user.id, reason="Retention expired")
    await db.commit()

    result = await db.execute(select(AuditLogEntry))
    entries = result.scalars().all()
    actions = {e.action for e in entries}
    assert AuditEventType.DUPLICATE_BLOCKED.value in actions
    assert AuditEventType.DUPLICATE_OVERRIDE.value in actions
    assert AuditEventType.REOPEN_REQUESTED.value in actions
    assert AuditEventType.REOPEN_APPROVED.value in actions
    assert AuditEventType.COMPLIANCE_SCHEDULER_RUN.value in actions
    assert AuditEventType.EVIDENCE_DELETED.value in actions
