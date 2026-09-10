"""
Expiration Reminder Service — CRUD + reminder logic for ExpirationRecord entities.
Manages creation, listing, renewal, and status transitions for expirable items.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.platform_models import (
    ExpirationRecord,
    ExpirationStatus,
    ExpirationEntityType,
)
from shared.datetime_utils import utc_now


class ExpirationService:
    """CRUD and reminder logic for ExpirationRecord."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Create ─────────────────────────────────────────────────────────────

    async def create_record(
        self,
        *,
        school_id: UUID,
        department_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
        entity_type: ExpirationEntityType,
        title: str,
        description: Optional[str] = None,
        document_reference: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        entity_link: Optional[str] = None,
        issued_at: Optional[datetime] = None,
        expires_at: datetime,
        renew_by_at: Optional[datetime] = None,
        reminder_lead_days: int = 30,
        metadata_json: Optional[dict] = None,
    ) -> ExpirationRecord:
        status = self._compute_status(expires_at, reminder_lead_days)

        record = ExpirationRecord(
            school_id=school_id,
            department_id=department_id,
            created_by=created_by,
            entity_type=entity_type,
            title=title,
            description=description,
            document_reference=document_reference,
            entity_id=entity_id,
            entity_link=entity_link,
            issued_at=issued_at,
            expires_at=expires_at,
            renew_by_at=renew_by_at,
            status=status,
            reminder_lead_days=reminder_lead_days,
            metadata_json=metadata_json,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    # ── Read ───────────────────────────────────────────────────────────────

    async def get_record(self, record_id: UUID) -> Optional[ExpirationRecord]:
        result = await self.db.execute(
            select(ExpirationRecord).where(ExpirationRecord.id == record_id)
        )
        return result.scalar_one_or_none()

    async def list_records(
        self,
        school_id: Optional[UUID],
        *,
        status: Optional[ExpirationStatus] = None,
        entity_type: Optional[ExpirationEntityType] = None,
        department_id: Optional[UUID] = None,
        expiring_within_days: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ExpirationRecord], int]:
        """
        List expiration records with filters. Returns (records, total_count).
        school_id=None → cross-school aggregate (SuperAdmin only; the route
        layer enforces who may omit the school scope).
        """
        query = select(ExpirationRecord)
        if school_id is not None:
            query = query.where(ExpirationRecord.school_id == school_id)

        if status:
            query = query.where(ExpirationRecord.status == status)
        if entity_type:
            query = query.where(ExpirationRecord.entity_type == entity_type)
        if department_id:
            query = query.where(ExpirationRecord.department_id == department_id)
        if expiring_within_days is not None:
            cutoff = utc_now() + timedelta(days=expiring_within_days)
            query = query.where(
                ExpirationRecord.expires_at <= cutoff,
                ExpirationRecord.status.in_([
                    ExpirationStatus.ACTIVE,
                    ExpirationStatus.EXPIRING_SOON,
                ]),
            )

        # Total count
        count_q = select(func.count()).select_from(
            query.subquery()
        )
        total = (await self.db.execute(count_q)).scalar() or 0

        # Paginated results
        offset = (page - 1) * page_size
        query = query.order_by(ExpirationRecord.expires_at.asc())
        query = query.limit(page_size).offset(offset)

        result = await self.db.execute(query)
        records = list(result.scalars().all())

        return records, total

    async def get_expiring_soon(
        self,
        school_id: Optional[UUID],
        *,
        days_ahead: int = 30,
    ) -> list[ExpirationRecord]:
        """Get all records expiring within N days (active + expiring_soon)."""
        cutoff = utc_now() + timedelta(days=days_ahead)
        conditions = [
            ExpirationRecord.expires_at <= cutoff,
            ExpirationRecord.status.in_([
                ExpirationStatus.ACTIVE,
                ExpirationStatus.EXPIRING_SOON,
            ]),
        ]
        if school_id is not None:
            conditions.append(ExpirationRecord.school_id == school_id)
        query = (
            select(ExpirationRecord)
            .where(*conditions)
            .order_by(ExpirationRecord.expires_at.asc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_expired(self, school_id: Optional[UUID]) -> list[ExpirationRecord]:
        """Get all records that have expired (status == EXPIRED)."""
        conditions = [ExpirationRecord.status == ExpirationStatus.EXPIRED]
        if school_id is not None:
            conditions.append(ExpirationRecord.school_id == school_id)
        query = (
            select(ExpirationRecord)
            .where(*conditions)
            .order_by(ExpirationRecord.expires_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_reminder_summary(self, school_id: Optional[UUID]) -> dict:
        """
        Summary counts for the Dashboard widget.
        Returns counts of: expiring_soon (7d), expiring_30d, expired, renewed.
        school_id=None → cross-school aggregate (SuperAdmin only).
        """
        now = utc_now()
        d7 = now + timedelta(days=7)
        d30 = now + timedelta(days=30)

        base = select(func.count())
        if school_id is not None:
            base = base.where(ExpirationRecord.school_id == school_id)

        expiring_7d = (await self.db.execute(
            base.where(
                ExpirationRecord.expires_at <= d7,
                ExpirationRecord.status.in_([
                    ExpirationStatus.ACTIVE,
                    ExpirationStatus.EXPIRING_SOON,
                ]),
            )
        )).scalar() or 0

        expiring_30d = (await self.db.execute(
            base.where(
                ExpirationRecord.expires_at <= d30,
                ExpirationRecord.expires_at > d7,
                ExpirationRecord.status.in_([
                    ExpirationStatus.ACTIVE,
                    ExpirationStatus.EXPIRING_SOON,
                ]),
            )
        )).scalar() or 0

        expired_count = (await self.db.execute(
            base.where(ExpirationRecord.status == ExpirationStatus.EXPIRED)
        )).scalar() or 0

        renewed_count = (await self.db.execute(
            base.where(ExpirationRecord.status == ExpirationStatus.RENEWED)
        )).scalar() or 0

        # select_from is required: without it, `SELECT count(*)` has no FROM
        # clause and Postgres evaluates it over a single implicit row, always
        # returning 1 for the cross-school (school_id=None) path.
        total_query = select(func.count()).select_from(ExpirationRecord)
        if school_id is not None:
            total_query = total_query.where(ExpirationRecord.school_id == school_id)
        total = (await self.db.execute(total_query)).scalar() or 0

        return {
            "total": total,
            "expiring_7d": expiring_7d,
            "expiring_30d": expiring_30d,
            "expired": expired_count,
            "renewed": renewed_count,
        }

    # ── Update / Renew ─────────────────────────────────────────────────────

    async def renew_record(
        self,
        record_id: UUID,
        *,
        new_expires_at: datetime,
        renewed_at: Optional[datetime] = None,
    ) -> ExpirationRecord:
        """Mark a record as renewed with a new expiry date."""
        record = await self.get_record(record_id)
        if record is None:
            raise ValueError("Expiration record not found")

        record.status = ExpirationStatus.ACTIVE
        record.expires_at = new_expires_at
        record.renewed_at = renewed_at or utc_now()
        record.reminder_sent_at = None
        record.is_acknowledged = False
        await self.db.flush()
        return record

    async def acknowledge_record(self, record_id: UUID) -> ExpirationRecord:
        """Mark an expiring/expired record as acknowledged (user has seen it)."""
        record = await self.get_record(record_id)
        if record is None:
            raise ValueError("Expiration record not found")
        record.is_acknowledged = True
        await self.db.flush()
        return record

    async def update_record(
        self,
        record_id: UUID,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        reminder_lead_days: Optional[int] = None,
        entity_type: Optional[ExpirationEntityType] = None,
        document_reference: Optional[str] = None,
        entity_link: Optional[str] = None,
        renew_by_at: Optional[datetime] = None,
    ) -> ExpirationRecord:
        """Update record fields."""
        record = await self.get_record(record_id)
        if record is None:
            raise ValueError("Expiration record not found")

        if title is not None:
            record.title = title
        if description is not None:
            record.description = description
        if expires_at is not None:
            record.expires_at = expires_at
        if reminder_lead_days is not None:
            record.reminder_lead_days = reminder_lead_days
        if entity_type is not None:
            record.entity_type = entity_type
        if document_reference is not None:
            record.document_reference = document_reference
        if entity_link is not None:
            record.entity_link = entity_link
        if renew_by_at is not None:
            record.renew_by_at = renew_by_at

        # Recompute status after any expiry change
        record.status = self._compute_status(
            record.expires_at, record.reminder_lead_days
        )
        await self.db.flush()
        return record

    async def delete_record(self, record_id: UUID) -> bool:
        record = await self.get_record(record_id)
        if record is None:
            return False
        await self.db.delete(record)
        await self.db.flush()
        return True

    # ── Status computation ─────────────────────────────────────────────────

    @staticmethod
    def _compute_status(
        expires_at: datetime, reminder_lead_days: int
    ) -> ExpirationStatus:
        now = utc_now()
        if now > expires_at:
            return ExpirationStatus.EXPIRED
        lead_cutoff = expires_at - timedelta(days=reminder_lead_days)
        if now >= lead_cutoff:
            return ExpirationStatus.EXPIRING_SOON
        return ExpirationStatus.ACTIVE
