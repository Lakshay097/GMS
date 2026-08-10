"""
Notification channel providers — pluggable per channel.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class ProviderResult:
    success: bool
    error: Optional[str] = None


class NotificationProvider(ABC):
    """Channel-specific dispatch provider."""

    channel: str

    @abstractmethod
    async def send(
        self,
        user_id: UUID,
        title: str,
        body: str,
        *,
        school_id: Optional[UUID] = None,
    ) -> ProviderResult:
        raise NotImplementedError


class InAppProvider(NotificationProvider):
    channel = "in_app"

    async def send(self, user_id, title, body, *, school_id=None) -> ProviderResult:
        return ProviderResult(success=True)


class EmailProvider(NotificationProvider):
    channel = "email"

    async def send(self, user_id, title, body, *, school_id=None) -> ProviderResult:
        return ProviderResult(success=True)


class SMSProvider(NotificationProvider):
    channel = "sms"

    async def send(self, user_id, title, body, *, school_id=None) -> ProviderResult:
        return ProviderResult(success=True)


class WhatsAppProvider(NotificationProvider):
    channel = "whatsapp"

    async def send(self, user_id, title, body, *, school_id=None) -> ProviderResult:
        return ProviderResult(success=True)


class SlowFailingProvider(NotificationProvider):
    """Test provider that simulates slow/failing external channel."""

    channel = "slow_test"

    def __init__(self, delay_seconds: float = 5.0, fail: bool = True):
        self.delay_seconds = delay_seconds
        self.fail = fail

    async def send(self, user_id, title, body, *, school_id=None) -> ProviderResult:
        await asyncio.sleep(self.delay_seconds)
        if self.fail:
            return ProviderResult(success=False, error="simulated provider failure")
        return ProviderResult(success=True)
