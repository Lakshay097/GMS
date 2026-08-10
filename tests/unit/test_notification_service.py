"""Unit tests for Notification Service — Architecture §5.4, R-38/R-39/R-40."""
import asyncio
import time
import uuid

import pytest

from platform_services.notification_service.providers import SlowFailingProvider
from platform_services.notification_service.service import (
    MANDATORY_CATEGORIES,
    NotificationPayload,
    NotificationService,
)
from shared.errors import BusinessRuleError
from shared.platform_models import NotificationCategory, NotificationChannel
from shared.task_queue import InMemoryQueue


@pytest.mark.asyncio
async def test_R39_mandatory_categories_cannot_be_muted(db, user):
    service = NotificationService(db, queue=InMemoryQueue())

    with pytest.raises(BusinessRuleError, match="cannot be muted"):
        await service.dispatch(
            NotificationPayload(
                user_id=user.id,
                category=NotificationCategory.ESCALATION.value,
                title="Escalation",
                body="Task escalated",
                muted_categories={NotificationCategory.ESCALATION.value},
            )
        )


@pytest.mark.asyncio
async def test_R40_slow_provider_does_not_block_request(db, user):
    """
    R-40/ADR-05: dispatch returns immediately; slow provider runs via queue.
  """
    slow_provider = SlowFailingProvider(delay_seconds=2.0, fail=True)
    queue = InMemoryQueue()
    service = NotificationService(
        db,
        providers={"in_app": slow_provider},
        queue=queue,
    )

    start = time.monotonic()
    notification_id = await service.dispatch(
        NotificationPayload(
            user_id=user.id,
            category=NotificationCategory.INFORMATIONAL.value,
            title="Test",
            body="Non-blocking dispatch",
            channel=NotificationChannel.IN_APP,
        )
    )
    elapsed = time.monotonic() - start

    assert notification_id is not None
    assert elapsed < 1.0, "Dispatch must not block on slow provider"

    messages = await queue.dequeue("notifications")
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_notification_priority_categories_ordered():
    """R-38/BR-15: fixed priority order 1-7."""
    assert NotificationCategory.ESCALATION.value == 1
    assert NotificationCategory.AUDIT_FAILURE.value == 2
    assert NotificationCategory.INFORMATIONAL.value == 7
    assert MANDATORY_CATEGORIES == frozenset({1, 2})
