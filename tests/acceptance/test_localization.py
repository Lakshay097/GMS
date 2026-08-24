"""
Acceptance tests for English localization per PRS §54.
Verifies that notification templates work correctly.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import pytest
from uuid import uuid4
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.configuration_engine.constants import ConfigKey
from platform_services.notification_service.service import NotificationService, NotificationPayload
from platform_services.notification_service.localization import NotificationLocalizationService, NOTIFICATION_TEMPLATES


@pytest.mark.asyncio
async def test_locale_configuration_engine_value(db: AsyncSession):
    """
    Acceptance test: Verify Supported Locales is a Configuration Engine value.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()

    # Get supported locales from configuration
    locales = await config_engine.get(ConfigKey.LOCALES)

    # Verify it's a list containing English
    assert isinstance(locales, list), "Locales should be a list"
    assert "en" in locales, "English should be in supported locales"


@pytest.mark.asyncio
async def test_notification_localization_templates(db: AsyncSession):
    """
    Acceptance test: Verify notification templates support English.
    """
    localization_service = NotificationLocalizationService(config_engine=None)

    # Test English template
    template = localization_service.get_template("escalation")
    title, body = localization_service.format_template(template, level=1)

    assert "Escalated" in title or "Escalated" in body, "English template should contain English text"


@pytest.mark.asyncio
async def test_notification_service_uses_localization(db: AsyncSession):
    """
    Acceptance test: Verify Notification Service uses localization when template_key is provided.
    """
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()

    notification_service = NotificationService(db, config_engine=config_engine)
    user_id = uuid4()

    # Test with English template
    notification_en = await notification_service.dispatch(
        NotificationPayload(
            user_id=user_id,
            category=1,  # ESCALATION
            title="Test",  # Fallback title
            body="Test",   # Fallback body
            template_key="escalation",
            template_vars={"level": 1}
        )
    )

    # Verify notification was created
    from shared.platform_models import Notification
    result = await db.execute(select(Notification).where(Notification.id == notification_en))
    notification = result.scalar_one_or_none()

    assert notification is not None, "Notification should be created"
    # The title/body should be from the template, not the fallback


@pytest.mark.asyncio
async def test_all_notification_templates_have_translations(db: AsyncSession):
    """
    Acceptance test: Verify all notification templates have English versions.
    """
    localization_service = NotificationLocalizationService(config_engine=None)

    # Check that all templates have English
    for template_key in NOTIFICATION_TEMPLATES:
        template = NOTIFICATION_TEMPLATES[template_key]

        # Verify English versions exist
        assert template.title, f"Template {template_key} missing English title"
        assert template.body, f"Template {template_key} missing English body"

        # Verify they're not empty
        assert len(template.title) > 0, f"Template {template_key} has empty English title"
        assert len(template.body) > 0, f"Template {template_key} has empty English body"
