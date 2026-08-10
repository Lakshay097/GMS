"""Notification Service — Architecture §5.4."""

from platform_services.notification_service.service import (
    MANDATORY_CATEGORIES,
    NotificationDispatchJob,
    NotificationPayload,
    NotificationService,
)

__all__ = [
    "MANDATORY_CATEGORIES",
    "NotificationDispatchJob",
    "NotificationPayload",
    "NotificationService",
]
