"""Unit tests for EmailProvider with Resend integration."""
import os
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from platform_services.notification_service.providers import EmailProvider, ProviderResult


@pytest.mark.asyncio
async def test_email_provider_missing_api_key():
    """Test that EmailProvider fails gracefully when API key is not configured."""
    # Ensure no API key is set
    os.environ.pop("EMAIL_PROVIDER_API_KEY", None)
    os.environ.pop("EMAIL_FROM", None)
    
    provider = EmailProvider()
    result = await provider.send(
        user_id=uuid4(),
        title="Test",
        body="Test body",
        user_email="test@example.com"
    )
    
    assert result.success is False
    assert "EMAIL_PROVIDER_API_KEY not configured" in result.error


@pytest.mark.asyncio
async def test_email_provider_missing_user_email():
    """Test that EmailProvider fails when user_email is not provided."""
    os.environ["EMAIL_PROVIDER_API_KEY"] = "test_key"
    os.environ["EMAIL_FROM"] = "test@example.com"
    
    provider = EmailProvider()
    result = await provider.send(
        user_id=uuid4(),
        title="Test",
        body="Test body",
        user_email=None
    )
    
    assert result.success is False
    assert "user_email is required" in result.error
    
    # Clean up
    os.environ.pop("EMAIL_PROVIDER_API_KEY", None)
    os.environ.pop("EMAIL_FROM", None)


@pytest.mark.asyncio
async def test_email_provider_successful_send():
    """Test successful email send via Resend."""
    os.environ["EMAIL_PROVIDER_API_KEY"] = "test_key"
    os.environ["EMAIL_FROM"] = "sender@example.com"
    
    # Create a mock Resend client
    mock_resend = MagicMock()
    mock_resend.Emails.send.return_value = {"id": "test_email_id"}
    
    provider = EmailProvider()
    provider._client = mock_resend
    
    result = await provider.send(
        user_id=uuid4(),
        title="Test Subject",
        body="<p>Test body</p>",
        user_email="recipient@example.com"
    )
    
    assert result.success is True
    
    # Verify the Resend API was called correctly
    mock_resend.Emails.send.assert_called_once()
    call_args = mock_resend.Emails.send.call_args[0][0]
    assert call_args["from"] == "sender@example.com"
    assert call_args["to"] == ["recipient@example.com"]
    assert call_args["subject"] == "Test Subject"
    assert call_args["html"] == "<p>Test body</p>"
    
    # Clean up
    os.environ.pop("EMAIL_PROVIDER_API_KEY", None)
    os.environ.pop("EMAIL_FROM", None)


@pytest.mark.asyncio
async def test_email_provider_resend_error():
    """Test error handling when Resend API fails."""
    os.environ["EMAIL_PROVIDER_API_KEY"] = "test_key"
    os.environ["EMAIL_FROM"] = "sender@example.com"
    
    # Mock the Resend client to raise an exception
    mock_resend = MagicMock()
    mock_resend.Emails.send.side_effect = Exception("Resend API error")
    
    provider = EmailProvider()
    provider._client = mock_resend
    
    result = await provider.send(
        user_id=uuid4(),
        title="Test Subject",
        body="Test body",
        user_email="recipient@example.com"
    )
    
    assert result.success is False
    assert "Resend API error" in result.error
    
    # Clean up
    os.environ.pop("EMAIL_PROVIDER_API_KEY", None)
    os.environ.pop("EMAIL_FROM", None)


@pytest.mark.asyncio
async def test_email_provider_custom_from_address():
    """Test that custom EMAIL_FROM is used correctly."""
    os.environ["EMAIL_PROVIDER_API_KEY"] = "test_key"
    os.environ["EMAIL_FROM"] = "custom@domain.com"
    
    provider = EmailProvider()
    assert provider.from_email == "custom@domain.com"
    
    # Clean up
    os.environ.pop("EMAIL_PROVIDER_API_KEY", None)
    os.environ.pop("EMAIL_FROM", None)


@pytest.mark.asyncio
async def test_email_provider_default_from_address():
    """Test that default EMAIL_FROM is used when not configured."""
    os.environ["EMAIL_PROVIDER_API_KEY"] = "test_key"
    # Don't set EMAIL_FROM
    
    provider = EmailProvider()
    assert provider.from_email == "onboarding@resend.dev"
    
    # Clean up
    os.environ.pop("EMAIL_PROVIDER_API_KEY", None)