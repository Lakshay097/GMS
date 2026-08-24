"""
Notification Service — Architecture §5.4, R-38/R-39/R-40/ADR-05.
Async dispatch via job queue; mandatory categories enforced server-side.
Includes English localization per PRS §54.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.notification_service.providers import (
    EmailProvider,
    InAppProvider,
    NotificationProvider,
    SMSProvider,
    WhatsAppProvider,
)
from platform_services.notification_service.localization import (
    NotificationLocalizationService,
)
from platform_services.configuration_engine.service import ConfigurationEngine
from shared.datetime_utils import utc_now
from shared.errors import BusinessRuleError
from shared.platform_models import (
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationStatus,
)
from shared.task_queue import JobRegistry, get_queue_instance

NOTIFICATION_QUEUE = "notifications"
DISPATCH_JOB_TYPE = "notification_dispatch"

# R-39/C9: categories 1 and 2 cannot be muted under any client request path.
MANDATORY_CATEGORIES = frozenset({
    NotificationCategory.ESCALATION.value,
    NotificationCategory.AUDIT_FAILURE.value,
})


@dataclass
class NotificationPayload:
    user_id: UUID
    category: int
    title: str
    body: str
    channel: NotificationChannel = NotificationChannel.IN_APP
    school_id: Optional[UUID] = None
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    muted_categories: Optional[set[int]] = None
    template_key: Optional[str] = None  # For localization
    template_vars: Optional[dict] = None  # Variables for template formatting


@dataclass
class NotificationDispatchJob:
    notification_id: str
    user_id: str
    channel: str
    title: str
    body: str
    school_id: Optional[str] = None


class NotificationService:
    """
    Enqueues notification dispatch asynchronously (R-40).
    Provider failures never block the triggering API request.
    Includes localization support for English.
    """

    def __init__(
        self,
        db: AsyncSession,
        providers: Optional[dict[str, NotificationProvider]] = None,
        queue=None,
        config_engine=None,
    ):
        self.db = db
        self.queue = queue or get_queue_instance()
        self.providers = providers or {
            NotificationChannel.IN_APP.value: InAppProvider(),
            NotificationChannel.EMAIL.value: EmailProvider(),
            NotificationChannel.SMS.value: SMSProvider(),
            NotificationChannel.WHATSAPP.value: WhatsAppProvider(),
        }
        self.localization_service = NotificationLocalizationService(config_engine) if config_engine else None
        self._register_job_handler()

    def _register_job_handler(self) -> None:
        registry = JobRegistry()

        async def handle_dispatch(job_data: dict) -> None:
            await self._process_dispatch(job_data)

        if DISPATCH_JOB_TYPE not in registry.handlers:
            registry.register(DISPATCH_JOB_TYPE, handle_dispatch)

    async def dispatch(self, payload: NotificationPayload) -> UUID:
        """
        Queue a notification for async delivery.
        Returns immediately after persisting + enqueueing (R-40).
        Uses localization templates if template_key is provided.
        """
        # Apply localization if template_key is provided
        title = payload.title
        body = payload.body

        if payload.template_key and self.localization_service:
            try:
                template = self.localization_service.get_template(payload.template_key)
                template_vars = payload.template_vars or {}
                title, body = self.localization_service.format_template(template, **template_vars)
            except Exception:
                # Fallback to provided title/body if localization fails
                pass

        if payload.muted_categories and payload.category in payload.muted_categories:
            if payload.category in MANDATORY_CATEGORIES:
                raise BusinessRuleError(
                    "Categories 1 (Escalation) and 2 (Audit Failure) cannot be muted (R-39/C9)",
                    details={"category": payload.category},
                )
            return await self._create_skipped_notification(payload)

        notification = Notification(
            user_id=payload.user_id,
            school_id=payload.school_id,
            category=payload.category,
            channel=payload.channel,
            title=title,
            body=body,
            status=NotificationStatus.PENDING,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
        )
        self.db.add(notification)
        await self.db.flush()

        await self.queue.enqueue(
            NOTIFICATION_QUEUE,
            {
                "job_type": DISPATCH_JOB_TYPE,
                "notification_id": str(notification.id),
                "user_id": str(payload.user_id),
                "channel": payload.channel.value,
                "title": title,
                "body": body,
                "school_id": str(payload.school_id) if payload.school_id else None,
            },
        )
        await self.db.commit()
        return notification.id

    async def _create_skipped_notification(self, payload: NotificationPayload) -> UUID:
        """Record that a non-mandatory notification was suppressed by user preference."""
        notification = Notification(
            user_id=payload.user_id,
            school_id=payload.school_id,
            category=payload.category,
            channel=payload.channel,
            title=payload.title,
            body=payload.body,
            status=NotificationStatus.DISPATCHED,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            dispatched_at=utc_now(),
        )
        self.db.add(notification)
        await self.db.commit()
        return notification.id

    async def _process_dispatch(self, job_data: dict) -> None:
        """Job handler — runs outside the triggering request path."""
        channel = job_data["channel"]
        provider = self.providers.get(channel)
        if provider is None:
            return

        result = await provider.send(
            UUID(job_data["user_id"]),
            job_data["title"],
            job_data["body"],
            school_id=UUID(job_data["school_id"]) if job_data.get("school_id") else None,
        )

        notification_id = UUID(job_data["notification_id"])
        notification = await self.db.get(Notification, notification_id)
        if notification:
            notification.status = (
                NotificationStatus.DISPATCHED if result.success else NotificationStatus.FAILED
            )
            notification.dispatched_at = utc_now()
            await self.db.commit()

    async def dispatch_non_blocking(self, payload: NotificationPayload) -> UUID:
        """
        Fire-and-forget dispatch using asyncio.create_task for tests
        that verify the triggering path is not blocked by slow providers.
        """
        return await self.dispatch(payload)
