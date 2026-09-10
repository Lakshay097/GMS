"""
Invitation code service — user-management spec §6-8.

Codes are cryptographically random, stored HASHED (sha256), bound to a
department + role at creation, expire, cap their number of uses, and can be
revoked. The signup flow derives the user's department and role EXCLUSIVELY
from the invitation record — never from client input.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import (
    generate_invitation_code,
    hash_invitation_code,
    INVITE_EXPIRY_HOURS,
    INVITE_MAX_USES_CAP,
)
from shared.models import (
    Department,
    InvitationCode,
    InvitationUse,
    User,
    UserRole,
    UserStatus,
)
from shared.errors import ValidationError, NotFoundError, AuthorizationError
from shared.datetime_utils import utc_now


class InvitationService:
    """Create, list, revoke, and consume invitation codes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Authorization helpers (role hierarchy per spec §4) ─────────────────

    @staticmethod
    def assignable_roles(actor_roles: List[str]) -> List[str]:
        """Roles the actor may bind to an invitation, per the role hierarchy."""
        from shared.permissions import ROLE_HIERARCHY

        assignable: List[str] = []
        for role in actor_roles:
            assignable.extend(ROLE_HIERARCHY.get((role or "").lower(), []))
        # de-duplicate, keep a stable sensible order
        order = ["admin", "dept_head", "auditor", "verifier", "checker", "viewer"]
        seen = set(assignable)
        return [r for r in order if r in seen]

    async def _scope_department_ids(self, actor_roles: List[str], actor_school_id: Optional[str],
                                    actor_department_id: Optional[str]) -> Optional[List[UUID]]:
        """Departments the actor may create invitations for.

        superadmin → None (any); admin → all departments of their school;
        dept_head → only their own department. Others: empty (denied upstream).
        """
        roles = [r.lower() for r in actor_roles]
        if "superadmin" in roles:
            return None
        if "admin" in roles and actor_school_id:
            result = await self.db.execute(
                select(Department.id).where(Department.school_id == UUID(actor_school_id))
            )
            return [row[0] for row in result.all()]
        if "dept_head" in roles and actor_department_id:
            return [UUID(actor_department_id)]
        return []

    # ── Create ──────────────────────────────────────────────────────────────

    async def create_invitation(
        self,
        *,
        actor_roles: List[str],
        actor_user_id: UUID,
        actor_school_id: Optional[str],
        actor_department_id: Optional[str],
        department_id: UUID,
        role: str,
        max_uses: int = 1,
        expires_in_hours: Optional[int] = None,
    ) -> Tuple[InvitationCode, str]:
        """
        Create an invitation. Returns (record, raw_code) — the raw code is
        shown to the creator exactly once and never stored.
        """
        role_value = (role or "").lower()
        try:
            UserRole(role_value)
        except ValueError:
            raise ValidationError(f"Invalid role: {role}", field="role")

        if role_value not in self.assignable_roles(actor_roles):
            raise AuthorizationError(
                f"You may not create invitations for role '{role_value}'"
            )

        allowed = await self._scope_department_ids(actor_roles, actor_school_id, actor_department_id)
        if allowed == []:
            raise AuthorizationError("You do not have permission to generate invitation codes")
        if allowed is not None and department_id not in allowed:
            raise AuthorizationError("You may only generate invitations for your own department")

        department = await self.db.get(Department, department_id)
        if not department:
            raise NotFoundError("Department not found")

        uses = int(max_uses or 1)
        if uses < 1:
            raise ValidationError("max_uses must be at least 1", field="max_uses")
        uses = min(uses, INVITE_MAX_USES_CAP)

        hours = int(expires_in_hours) if expires_in_hours else INVITE_EXPIRY_HOURS
        if hours < 1 or hours > 24 * 30:
            raise ValidationError("expires_in_hours must be between 1 and 720", field="expires_in_hours")

        # Custom expiry: regenerate with the requested window
        raw_code, code_hash, code_prefix, default_expiry = generate_invitation_code(
            prefix=(department.code or "OPS")[:3]
        )
        if expires_in_hours:
            from shared.auth import hash_invitation_code as _h
            expiry = utc_now() + timedelta(hours=hours)
        else:
            expiry = default_expiry

        record = InvitationCode(
            code_hash=code_hash,
            code_prefix=code_prefix,
            created_by=actor_user_id,
            school_id=department.school_id,
            department_id=department.id,
            role=role_value,
            expires_at=expiry,
            max_uses=uses,
            used_count=0,
            status="active",
        )
        self.db.add(record)
        await self.db.flush()
        return record, raw_code

    # ── List / revoke ───────────────────────────────────────────────────────

    async def list_invitations(
        self,
        *,
        actor_roles: List[str],
        actor_school_id: Optional[str],
        actor_department_id: Optional[str],
        include_expired: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[dict], int]:
        """List invitations within the actor's scope (never the code hash)."""
        from sqlalchemy import or_

        query = select(InvitationCode)
        roles = [r.lower() for r in actor_roles]
        if "superadmin" not in roles:
            if "admin" in roles and actor_school_id:
                query = query.where(InvitationCode.school_id == UUID(actor_school_id))
            elif "dept_head" in roles and actor_department_id:
                query = query.where(InvitationCode.department_id == UUID(actor_department_id))
            else:
                return [], 0

        if not include_expired:
            query = query.where(
                InvitationCode.status == "active",
                InvitationCode.expires_at > utc_now(),
            )

        total = (await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )).scalar() or 0

        query = query.order_by(InvitationCode.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.db.execute(query)).scalars().all()

        now = utc_now()
        items = []
        for inv in rows:
            exp = inv.expires_at if inv.expires_at.tzinfo else inv.expires_at.replace(tzinfo=timezone.utc)
            derived = "revoked" if inv.status == "revoked" else (
                "expired" if exp < now else ("exhausted" if inv.used_count >= inv.max_uses else "active")
            )
            dept = await self.db.get(Department, inv.department_id) if inv.department_id else None
            items.append({
                "id": str(inv.id),
                "code_prefix": inv.code_prefix,
                "department_id": str(inv.department_id) if inv.department_id else None,
                "department_name": dept.name if dept else None,
                "role": inv.role,
                "expires_at": exp.isoformat(),
                "max_uses": inv.max_uses,
                "used_count": inv.used_count,
                "status": derived,
                "created_at": (inv.created_at if inv.created_at.tzinfo else inv.created_at.replace(tzinfo=timezone.utc)).isoformat(),
            })
        return items, int(total)

    async def revoke_invitation(
        self,
        invitation_id: UUID,
        *,
        actor_roles: List[str],
        actor_school_id: Optional[str],
        actor_department_id: Optional[str],
    ) -> InvitationCode:
        record = await self.db.get(InvitationCode, invitation_id)
        if not record:
            raise NotFoundError("Invitation not found")

        roles = [r.lower() for r in actor_roles]
        if "superadmin" not in roles:
            if "admin" in roles:
                if actor_school_id and record.school_id and str(record.school_id) != actor_school_id:
                    raise AuthorizationError("You may only revoke invitations in your own school")
            elif "dept_head" in roles:
                if actor_department_id and str(record.department_id) != actor_department_id:
                    raise AuthorizationError("You may only revoke your own invitations")
            else:
                raise AuthorizationError("You do not have permission to revoke invitations")

        record.status = "revoked"
        record.revoked_at = utc_now()
        await self.db.commit()
        return record

    # ── Consume (signup) ────────────────────────────────────────────────────

    async def validate_code(self, raw_code: str) -> InvitationCode:
        """Validate a raw code and return its record, or raise ValidationError."""
        code_hash = hash_invitation_code(raw_code)
        result = await self.db.execute(
            select(InvitationCode).where(InvitationCode.code_hash == code_hash)
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise ValidationError("Invitation code is invalid or expired", field="invitation_code")
        if record.status == "revoked":
            raise ValidationError("This invitation has been revoked", field="invitation_code")
        # Compare in a single convention: naive-UTC (SQLite stores naive).
        exp = record.expires_at
        if exp.tzinfo:
            exp = exp.astimezone(timezone.utc).replace(tzinfo=None)
        if exp < utc_now().replace(tzinfo=None):
            raise ValidationError("Invitation code is invalid or expired", field="invitation_code")
        if record.used_count >= record.max_uses:
            raise ValidationError("This invitation has reached its usage limit", field="invitation_code")
        return record

    async def consume_code(self, raw_code: str, *, user_id: UUID) -> InvitationCode:
        """Validate + increment usage + record the consuming user (atomic)."""
        record = await self.validate_code(raw_code)
        record.used_count = (record.used_count or 0) + 1
        self.db.add(InvitationUse(invitation_id=record.id, user_id=user_id))
        await self.db.flush()
        return record
