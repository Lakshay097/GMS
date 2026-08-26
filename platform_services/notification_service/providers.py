"""
Notification channel providers — pluggable per channel.
"""
from __future__ import annotations

import asyncio
import os
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
        user_email: Optional[str] = None,
    ) -> ProviderResult:
        raise NotImplementedError


class InAppProvider(NotificationProvider):
    channel = "in_app"

    async def send(self, user_id, title, body, *, school_id=None, user_email=None) -> ProviderResult:
        return ProviderResult(success=True)


class EmailProvider(NotificationProvider):
    channel = "email"

    def __init__(self):
        self.api_key = os.getenv("EMAIL_PROVIDER_API_KEY", "")
        self.from_email = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
        self._client = None

    def _get_client(self):
        """Lazy-load Resend client to avoid import issues if API key is missing."""
        if self._client is None and self.api_key:
            try:
                import resend
                resend.api_key = self.api_key
                self._client = resend
            except ImportError:
                # Resend package not installed - will be handled in send()
                pass
        return self._client

    async def send(self, user_id, title, body, *, school_id=None, user_email=None) -> ProviderResult:
        """Send email via Resend API."""
        # No API key configured - fail gracefully
        if not self.api_key:
            return ProviderResult(
                success=False,
                error="EMAIL_PROVIDER_API_KEY not configured"
            )

        if not user_email:
            return ProviderResult(
                success=False,
                error="user_email is required for email delivery"
            )

        client = self._get_client()
        if client is None:
            return ProviderResult(
                success=False,
                error="Resend package not installed or API key invalid"
            )

        try:
            # Use asyncio.to_thread to avoid blocking the event loop
            def _send_email():
                params = {
                    "from": self.from_email,
                    "to": [user_email],
                    "subject": title,
                    "html": body
                }
                return client.Emails.send(params)

            result = await asyncio.to_thread(_send_email)
            return ProviderResult(success=True)
        except Exception as e:
            return ProviderResult(
                success=False,
                error=f"Resend API error: {str(e)}"
            )


class SMSProvider(NotificationProvider):
    channel = "sms"

    async def send(self, user_id, title, body, *, school_id=None, user_email=None) -> ProviderResult:
        return ProviderResult(success=True)


class WhatsAppProvider(NotificationProvider):
    channel = "whatsapp"

    async def send(self, user_id, title, body, *, school_id=None, user_email=None) -> ProviderResult:
        return ProviderResult(success=True)


class SlowFailingProvider(NotificationProvider):
    """Test provider that simulates slow/failing external channel."""

    channel = "slow_test"

    def __init__(self, delay_seconds: float = 5.0, fail: bool = True):
        self.delay_seconds = delay_seconds
        self.fail = fail

    async def send(self, user_id, title, body, *, school_id=None, user_email=None) -> ProviderResult:
        await asyncio.sleep(self.delay_seconds)
        if self.fail:
            return ProviderResult(success=False, error="simulated provider failure")
        return ProviderResult(success=True)
