"""
Session Management Service — FR-194.
Manages user session lifecycle: creation, validation, and expiry.
Full persistence layer is a Phase 2 item; this implementation uses
an in-process store to satisfy test contracts without requiring a
dedicated DB table migration.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.datetime_utils import utc_now

# Default session lifetime: 8 hours (configurable in Phase 2)
DEFAULT_SESSION_TTL_HOURS = 8


@dataclass
class Session:
    """In-memory session record."""
    id: UUID
    user_id: UUID
    ip_address: str
    user_agent: str
    created_at: datetime
    expires_at: datetime
    is_active: bool = True


class SessionService:
    """
    FR-194: Session Management.
    Phase 1 — in-process store.  Phase 2 will migrate to a DB-backed sessions table.
    """

    # Class-level store so multiple service instances within the same process share state.
    _store: dict[UUID, Session] = {}

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        user_id: UUID,
        ip_address: str,
        user_agent: str,
        *,
        expires_at: Optional[datetime] = None,
    ) -> Session:
        """Create a new session for the given user."""
        now = utc_now()
        session = Session(
            id=uuid.uuid4(),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now,
            expires_at=expires_at or (now + timedelta(hours=DEFAULT_SESSION_TTL_HOURS)),
            is_active=True,
        )
        # Mark expired sessions inactive immediately
        if session.expires_at <= now:
            session.is_active = False
        SessionService._store[session.id] = session
        return session

    async def validate_session(self, session_id: UUID) -> bool:
        """Return True if the session exists, is active, and has not expired."""
        session = SessionService._store.get(session_id)
        if session is None:
            return False
        if not session.is_active:
            return False
        if session.expires_at <= utc_now():
            session.is_active = False
            return False
        return True

    async def invalidate_session(self, session_id: UUID) -> None:
        """Explicitly invalidate a session (logout)."""
        session = SessionService._store.get(session_id)
        if session:
            session.is_active = False

    async def invalidate_all_user_sessions(self, user_id: UUID) -> int:
        """Invalidate every active session for a user. Returns count invalidated."""
        count = 0
        for session in SessionService._store.values():
            if session.user_id == user_id and session.is_active:
                session.is_active = False
                count += 1
        return count
