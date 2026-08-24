"""
Audit Log Service — Architecture §5.5, R-19.
Single shared append-only sink; writes INSERT-only (UPDATE/DELETE revoked at DB layer).
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.audit_log_service.event_types import AuditEventType
from shared.datetime_utils import utc_now
from shared.models import AuditLogEntry


class AuditLogService:
    """
    Append-only audit log writer used by every module.
    Database grants enforce immutability (R-19) — this service only INSERTs.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def append(
        self,
        action: str | AuditEventType,
        entity_type: str,
        entity_id: Optional[UUID],
        *,
        actor_id: Optional[UUID] = None,
        school_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        old_values: Optional[dict[str, Any]] = None,
        new_values: Optional[dict[str, Any]] = None,
        reason_comment: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UUID:
        action_str = action.value if isinstance(action, AuditEventType) else action

        entry = AuditLogEntry(
            user_id=actor_id,
            school_id=school_id,
            department_id=department_id,
            action=action_str,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values={
                **(new_values or {}),
                **({"reason_comment": reason_comment} if reason_comment else {}),
            },
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=utc_now(),
        )
        self.db.add(entry)
        await self.db.flush()
        return entry.id

    async def log_duplicate_blocked(
        self,
        observation_id: UUID,
        *,
        actor_id: Optional[UUID] = None,
        school_id: Optional[UUID] = None,
        details: Optional[dict] = None,
    ) -> UUID:
        return await self.append(
            AuditEventType.DUPLICATE_BLOCKED,
            "observation",
            observation_id,
            actor_id=actor_id,
            school_id=school_id,
            new_values=details,
        )

    async def log_duplicate_override(
        self,
        observation_id: UUID,
        *,
        actor_id: Optional[UUID] = None,
        justification: str,
    ) -> UUID:
        return await self.append(
            AuditEventType.DUPLICATE_OVERRIDE,
            "observation",
            observation_id,
            actor_id=actor_id,
            reason_comment=justification,
        )

    async def log_reopen_request(
        self,
        observation_id: UUID,
        *,
        actor_id: UUID,
        reason: str,
    ) -> UUID:
        return await self.append(
            AuditEventType.REOPEN_REQUESTED,
            "observation",
            observation_id,
            actor_id=actor_id,
            reason_comment=reason,
        )

    async def log_reopen_approval(
        self,
        observation_id: UUID,
        *,
        actor_id: UUID,
        approved: bool,
        reason: Optional[str] = None,
    ) -> UUID:
        return await self.append(
            AuditEventType.REOPEN_APPROVED if approved else AuditEventType.REOPEN_REJECTED,
            "observation",
            observation_id,
            actor_id=actor_id,
            reason_comment=reason,
        )

    async def log_compliance_scheduler_run(
        self,
        run_id: UUID,
        *,
        records_generated: int,
        records_backfilled: int,
        status: str,
    ) -> UUID:
        return await self.append(
            AuditEventType.COMPLIANCE_SCHEDULER_RUN,
            "compliance_scheduler_run",
            run_id,
            new_values={
                "records_generated": records_generated,
                "records_backfilled": records_backfilled,
                "status": status,
            },
        )

    async def log_evidence_deletion(
        self,
        observation_id: UUID,
        *,
        actor_id: UUID,
        reason: Optional[str] = None,
    ) -> UUID:
        return await self.append(
            AuditEventType.EVIDENCE_DELETED,
            "observation",
            observation_id,
            actor_id=actor_id,
            reason_comment=reason,
        )

    async def log_observation_update(
        self,
        observation_id: UUID,
        *,
        actor_id: UUID,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
    ) -> UUID:
        return await self.append(
            "OBSERVATION_UPDATED",
            "observation",
            observation_id,
            actor_id=actor_id,
            old_values=old_values,
            new_values=new_values,
        )

    # ------------------------------------------------------------------
    # Query helpers (read path)
    # These do NOT violate append-only at the DB level — we only SELECT.
    # ------------------------------------------------------------------

    async def get_entity_history(
        self,
        entity_type: str,
        entity_id: UUID,
        *,
        limit: int = 500,
    ) -> list[AuditLogEntry]:
        """
        Return all audit log entries for a given entity, ordered oldest-first.
        Used by e2e and unit tests to verify the audit trail.
        """
        from sqlalchemy import select as _select

        result = await self.db.execute(
            _select(AuditLogEntry)
            .where(
                AuditLogEntry.entity_type == entity_type,
                AuditLogEntry.entity_id == entity_id,
            )
            .order_by(AuditLogEntry.timestamp.asc())
            .limit(limit)
        )
        entries = list(result.scalars().all())
        # Normalise: tests check entry.event_type but the model stores `action`.
        # Attach a convenience attribute so callers can use either name.
        for entry in entries:
            if not hasattr(entry, "event_type"):
                entry.event_type = entry.action  # type: ignore[attr-defined]
        return entries

    async def log_security_event(
        self,
        event_type: str,
        user_id: Optional[UUID] = None,
        *,
        ip_address: Optional[str] = None,
        details: Optional[str] = None,
    ) -> UUID:
        """Log a security-related event (FR-197)."""
        return await self.append(
            action=event_type,
            entity_type="security_event",
            entity_id=user_id,
            actor_id=user_id,
            ip_address=ip_address,
            new_values={"details": details} if details else None,
        )

    async def get_user_security_events(
        self,
        user_id: UUID,
        *,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """Return security audit entries for a given user."""
        from sqlalchemy import select as _select

        result = await self.db.execute(
            _select(AuditLogEntry)
            .where(
                AuditLogEntry.entity_type == "security_event",
                AuditLogEntry.entity_id == user_id,
            )
            .order_by(AuditLogEntry.timestamp.desc())
            .limit(limit)
        )
        entries = list(result.scalars().all())
        for entry in entries:
            if not hasattr(entry, "event_type"):
                entry.event_type = entry.action  # type: ignore[attr-defined]
        return entries
