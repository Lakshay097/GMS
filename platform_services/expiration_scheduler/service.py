"""
Expiration Scheduler — Daily cron job that:
1. Transitions ACTIVE → EXPIRING_SOON when within lead_days
2. Transitions EXPIRING_SOON → EXPIRED when past expires_at
3. Creates in-app notifications for expiring and newly expired records
4. Follows the same pattern as ComplianceScheduler/TaskEscalationScheduler
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.platform_models import (
    ExpirationRecord,
    ExpirationStatus,
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationStatus,
)
from shared.datetime_utils import utc_now


@dataclass
class ExpirationRunResult:
    statuses_updated: int = 0
    notifications_created: int = 0
    errors: list[str] = field(default_factory=list)


class ExpirationScheduler:
    """
    Daily scheduler for expiration reminders.
    Run via Cloud Scheduler POST to /internal/scheduler/expiration-check
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_check(self) -> dict:
        now = utc_now()
        result = ExpirationRunResult()

        try:
            # 1. Transition ACTIVE → EXPIRING_SOON (within lead_days)
            result.statuses_updated += await self._transition_to_expiring_soon(now)

            # 2. Transition EXPIRING_SOON → EXPIRED (past expires_at)
            result.statuses_updated += await self._transition_to_expired(now)

            # 3. Create notifications for expiring-soon records (no notification sent yet today)
            result.notifications_created += await self._create_reminder_notifications(now)

            # 4. Create notifications for newly expired records
            result.notifications_created += await self._create_expiry_notifications(now)

            await self.db.commit()

        except Exception as exc:
            result.errors.append(str(exc))

        return {
            "statuses_updated": result.statuses_updated,
            "notifications_created": result.notifications_created,
            "errors": result.errors,
        }

    async def _transition_to_expiring_soon(self, now) -> int:
        """ACTIVE records where expires_at - now <= reminder_lead_days → EXPIRING_SOON"""
        result = await self.db.execute(
            update(ExpirationRecord)
            .where(
                ExpirationRecord.status == ExpirationStatus.ACTIVE,
                ExpirationRecord.expires_at.is_not(None),
            )
            .values(status=ExpirationStatus.EXPIRING_SOON)
            .execution_options(synchronize_session="fetch")
        )
        # Post-filter: only those truly within lead_days window
        # (SQLAlchemy update can't easily do expires_at - now <= lead_days)
        select_result = await self.db.execute(
            select(ExpirationRecord).where(
                ExpirationRecord.status == ExpirationStatus.EXPIRING_SOON,
                ExpirationRecord.expires_at > now,
            )
        )
        records = select_result.scalars().all()
        reverted = 0
        for rec in records:
            lead_cutoff = rec.expires_at - timedelta(days=rec.reminder_lead_days)
            if now < lead_cutoff:
                rec.status = ExpirationStatus.ACTIVE
                reverted += 1

        return max(0, result.rowcount - reverted)

    async def _transition_to_expired(self, now) -> int:
        """EXPIRING_SOON records past expires_at → EXPIRED"""
        result = await self.db.execute(
            update(ExpirationRecord)
            .where(
                ExpirationRecord.status == ExpirationStatus.EXPIRING_SOON,
                ExpirationRecord.expires_at <= now,
            )
            .values(status=ExpirationStatus.EXPIRED)
        )
        return result.rowcount

    async def _create_reminder_notifications(self, now) -> int:
        """
        For each expiring-soon record that hasn't had a reminder sent today,
        create an in-app notification for the school's admins.
        """
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(ExpirationRecord).where(
                ExpirationRecord.status == ExpirationStatus.EXPIRING_SOON,
                # Either never reminded, or last reminder was before today
                (
                    (ExpirationRecord.reminder_sent_at.is_(None))
                    | (ExpirationRecord.reminder_sent_at < today_start)
                ),
            )
        )
        records = result.scalars().all()
        count = 0

        for rec in records:
            days_left = (rec.expires_at - now).days
            notification = Notification(
                user_id=rec.created_by or rec.school_id,  # fallback to school_id if no creator
                school_id=rec.school_id,
                category=NotificationCategory.INFORMATIONAL.value,
                channel=NotificationChannel.IN_APP,
                title=f"⚠️ {rec.title} expires in {days_left} days",
                body=(
                    f"Your {rec.entity_type.value if hasattr(rec.entity_type, 'value') else rec.entity_type} "
                    f"'{rec.title}' expires on {rec.expires_at.strftime('%d %b %Y')}. "
                    f"{'Please renew before the deadline.' if rec.renew_by_at else 'Please take action.'}"
                ),
                status=NotificationStatus.PENDING,
                entity_type="expiration_record",
                entity_id=rec.id,
            )
            self.db.add(notification)
            rec.reminder_sent_at = now
            count += 1

        return count

    async def _create_expiry_notifications(self, now) -> int:
        """
        For each EXPIRED record that hasn't been acknowledged,
        create a high-priority notification.
        """
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(ExpirationRecord).where(
                ExpirationRecord.status == ExpirationStatus.EXPIRED,
                ExpirationRecord.is_acknowledged == False,
                ExpirationRecord.reminder_sent_at < today_start,
            )
        )
        records = result.scalars().all()
        count = 0

        for rec in records:
            notification = Notification(
                user_id=rec.created_by or rec.school_id,
                school_id=rec.school_id,
                category=NotificationCategory.AUDIT_FAILURE.value,  # High priority
                channel=NotificationChannel.IN_APP,
                title=f"🔴 EXPIRED: {rec.title}",
                body=(
                    f"Your {rec.entity_type.value if hasattr(rec.entity_type, 'value') else rec.entity_type} "
                    f"'{rec.title}' expired on {rec.expires_at.strftime('%d %b %Y')}. "
                    f"Immediate action required."
                ),
                status=NotificationStatus.PENDING,
                entity_type="expiration_record",
                entity_id=rec.id,
            )
            self.db.add(notification)
            rec.reminder_sent_at = now
            count += 1

        return count
