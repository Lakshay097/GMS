"""
Unit tests for Settings (FR-163–168) using real ConfigurationEngine.
Tests configuration creation, updates, scope overrides, and audit logging using real methods.
"""
import uuid
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from platform_services.audit_log_service.service import AuditLogService
from platform_services.audit_log_service.event_types import AuditEventType
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.configuration_engine.constants import ConfigKey
from shared.platform_models import (
    ConfigurationItem,
    ConfigValueType,
    ConfigScopeType,
)
from shared.datetime_utils import utc_now
from shared.models import User
from shared.models import AuditLogEntry


@pytest.mark.asyncio
async def test_settings_creation_happy_path(db, school, department):
    """
    FR-163: Settings Creation - Happy Path.
    Verify that settings can be created with valid parameters using ConfigurationEngine.
    """
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="admin@test.com",
        full_name="Settings Admin",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["admin"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(admin)
    await db.commit()
    
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Verify default settings exist
    grace_period = await config_engine.get(ConfigKey.GRACE_PERIOD_HOURS)
    assert grace_period is not None
    assert grace_period > 0


@pytest.mark.asyncio
async def test_settings_update_happy_path(db, school, department):
    """
    FR-164: Settings Update - Happy Path.
    Verify that settings can be updated by authorized users using real set_global().
    """
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="admin@test.com",
        full_name="Settings Admin",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["admin"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(admin)
    await db.commit()
    
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Update global setting using real set_global
    await config_engine.set_global(
        ConfigKey.GRACE_PERIOD_HOURS,
        48  # Update from default
    )
    
    # Verify update
    updated_value = await config_engine.get(ConfigKey.GRACE_PERIOD_HOURS)
    assert updated_value == 48


@pytest.mark.asyncio
async def test_settings_scope_override_happy_path(db, school, department):
    """
    FR-165: Settings Scope Override - Happy Path.
    Verify that settings can be overridden at different scopes using real set_override().
    """
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="admin@test.com",
        full_name="Settings Admin",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["admin"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(admin)
    await db.commit()
    
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Set global default
    await config_engine.set_global(
        ConfigKey.GRACE_PERIOD_HOURS,
        24
    )
    
    # Override at school scope using real set_override
    await config_engine.set_override(
        key=ConfigKey.GRACE_PERIOD_HOURS,
        scope_type="school",
        scope_id=school.id,
        value=36
    )
    
    # Override at department scope using real set_override (use task escalation which supports department)
    await config_engine.set_override(
        key=ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS,  # Supports department scope
        scope_type="department",
        scope_id=department.id,
        value=12
    )
    
    # Verify scope overrides
    global_value = await config_engine.get(ConfigKey.GRACE_PERIOD_HOURS)
    school_value = await config_engine.get(ConfigKey.GRACE_PERIOD_HOURS, school_id=school.id)
    department_value = await config_engine.get(ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS, school_id=school.id, department_id=department.id)
    
    assert global_value == 24
    assert school_value == 36
    assert department_value == 12


@pytest.mark.asyncio
async def test_settings_scope_override_invalid_scope(db, school, department):
    """
    FR-165: Settings Scope Override - Failure Case.
    Verify that settings cannot be overridden at invalid scopes using real set_override().
    """
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="admin@test.com",
        full_name="Settings Admin",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["admin"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(admin)
    await db.commit()
    
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Attempt to override a setting that doesn't support department scope
    with pytest.raises(Exception) as exc_info:
        await config_engine.set_override(
            key=ConfigKey.GRACE_PERIOD_HOURS,  # Only supports school scope
            scope_type="department",
            scope_id=department.id,
            value=90
        )
    
    # Verify validation error
    assert "scope" in str(exc_info.value).lower() or "override" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_settings_non_overridable_key(db, school, department):
    """
    FR-165: Settings Non-Overridable Key - Failure Case.
    Verify that non-overridable keys cannot be overridden.
    """
    # Create super admin user
    super_admin = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="super_admin@test.com",
        full_name="Super Admin",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["super_admin"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(super_admin)
    await db.commit()
    
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Attempt to override MAX_ETA_EXTENSIONS (non-overridable)
    with pytest.raises(Exception) as exc_info:
        await config_engine.set_global(
            ConfigKey.MAX_ETA_EXTENSIONS,
            5
        )
    
    # Verify business rule error
    assert "max_eta_extensions" in str(exc_info.value).lower() or "fixed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_settings_feature_flag(db, school, department):
    """
    FR-166: Settings Feature Flag.
    Verify that feature flags can be checked using is_feature_enabled().
    """
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Check a non-existent feature flag (should return False)
    is_enabled = await config_engine.is_feature_enabled("feature.new_dashboard")
    assert is_enabled is False
    
    # Create a custom configuration item for feature flag
    from shared.platform_models import ConfigurationItem
    feature_item = ConfigurationItem(
        config_key="feature.new_dashboard",
        value_type=ConfigValueType.BOOLEAN,
        global_default="false",
        editable_by="super_admin",
        overridable_scope="none",
    )
    db.add(feature_item)
    await db.commit()
    
    # Set the feature flag to true
    await config_engine.set_global("feature.new_dashboard", True)
    
    # Check the feature flag (should return True)
    is_enabled = await config_engine.is_feature_enabled("feature.new_dashboard")
    assert is_enabled is True


@pytest.mark.asyncio
async def test_settings_amber_tolerance_band(db, school, department):
    """
    FR-167: Settings Amber Tolerance Band.
    Verify that KPI Amber Tolerance Band can be configured and retrieved.
    """
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Get default amber tolerance band
    default_band = await config_engine.get(ConfigKey.KPI_AMBER_TOLERANCE_BAND)
    assert default_band is not None
    
    # Set category-specific amber tolerance band
    await config_engine.set_category_amber_tolerance_band(
        category_code="academic",
        value=7.5
    )
    
    # Verify category-specific override
    category_band = await config_engine.get_amber_tolerance_band(category_code="academic")
    assert category_band == 7.5
    
    # Verify global default still works for other categories
    other_category_band = await config_engine.get_amber_tolerance_band(category_code="safety")
    assert other_category_band == default_band


@pytest.mark.asyncio
async def test_settings_get_unknown_key(db, school, department):
    """
    FR-168: Settings Unknown Key - Failure Case.
    Verify that getting an unknown configuration key raises an error.
    """
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Attempt to get unknown configuration key
    with pytest.raises(Exception) as exc_info:
        await config_engine.get("unknown.config.key")
    
    # Verify configuration error
    assert "unknown" in str(exc_info.value).lower() or "configuration" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_settings_set_unknown_key(db, school, department):
    """
    FR-168: Settings Unknown Key - Failure Case.
    Verify that setting an unknown configuration key raises an error.
    """
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Attempt to set unknown configuration key
    with pytest.raises(Exception) as exc_info:
        await config_engine.set_global("unknown.config.key", 100)
    
    # Verify configuration error
    assert "unknown" in str(exc_info.value).lower() or "configuration" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_settings_override_precedence(db, school, department):
    """
    FR-165: Settings Override Precedence.
    Verify that department override takes precedence over school override,
    which takes precedence over global default.
    """
    # Initialize service
    config_engine = ConfigurationEngine(db)
    await config_engine.seed_defaults()
    
    # Set global default
    await config_engine.set_global(ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS, 24)
    
    # Set school override
    await config_engine.set_override(
        key=ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS,
        scope_type="school",
        scope_id=school.id,
        value=36
    )
    
    # Set department override
    await config_engine.set_override(
        key=ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS,
        scope_type="department",
        scope_id=department.id,
        value=48
    )
    
    # Verify precedence: department > school > global
    global_value = await config_engine.get(ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS)
    school_value = await config_engine.get(ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS, school_id=school.id)
    department_value = await config_engine.get(ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS, school_id=school.id, department_id=department.id)
    
    assert global_value == 24
    assert school_value == 36
    assert department_value == 48


@pytest.mark.asyncio
async def test_settings_audit_logging_configuration_changes(db, school, department):
    """
    FR-167: Audit logging for configuration changes.
    Verify that configuration changes are logged to the audit log with proper
    old/new values, actor information, and scope details.
    """
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="admin@test.com",
        full_name="Settings Admin",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["admin"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(admin)
    await db.commit()
    
    # Initialize services with audit logging
    audit_log_service = AuditLogService(db)
    config_engine = ConfigurationEngine(db, audit_log_service=audit_log_service)
    await config_engine.seed_defaults()
    
    # Get initial value for audit verification
    initial_value = await config_engine.get(ConfigKey.GRACE_PERIOD_HOURS)
    
    # Test 1: set_global() creates audit log entry
    await config_engine.set_global(
        ConfigKey.GRACE_PERIOD_HOURS,
        48,
        updated_by=admin.id
    )
    
    # Verify audit log entry was created for set_global
    result = await db.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.action == AuditEventType.CONFIG_CHANGED.value,
            AuditLogEntry.entity_type == "configuration",
            AuditLogEntry.user_id == admin.id
        )
    )
    audit_entries = result.scalars().all()
    
    assert len(audit_entries) > 0, "Audit log entry should be created for set_global"
    
    # Get the most recent entry
    global_change_entry = audit_entries[-1]
    assert global_change_entry.old_values == {
        "key": ConfigKey.GRACE_PERIOD_HOURS.value,
        "value": str(initial_value),
        "scope": "global"
    }
    assert global_change_entry.new_values == {
        "key": ConfigKey.GRACE_PERIOD_HOURS.value,
        "value": "48",
        "scope": "global"
    }
    assert global_change_entry.action == AuditEventType.CONFIG_CHANGED.value
    
    # Test 2: set_override() creates audit log entry
    await config_engine.set_override(
        key=ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS,
        scope_type="school",
        scope_id=school.id,
        value=36,
        updated_by=admin.id
    )
    
    # Verify audit log entry was created for set_override
    result = await db.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.action == AuditEventType.CONFIG_CHANGED.value,
            AuditLogEntry.entity_type == "configuration",
            AuditLogEntry.user_id == admin.id
        )
    )
    all_entries = result.scalars().all()
    
    # Filter for school scope entries manually (JSONB query compatibility)
    override_entries = [e for e in all_entries if e.new_values and e.new_values.get("scope") == "school"]
    
    assert len(override_entries) > 0, "Audit log entry should be created for set_override"
    
    # Get the most recent override entry
    override_entry = override_entries[-1]
    assert override_entry.old_values == {
        "key": ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS.value,
        "value": None,  # No previous override
        "scope": "school",
        "scope_id": str(school.id)
    }
    assert override_entry.new_values == {
        "key": ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS.value,
        "value": "36",
        "scope": "school",
        "scope_id": str(school.id)
    }
    
    # Test 3: Verify configuration change succeeds even if audit logging fails
    # Create config engine without audit log service
    config_engine_no_audit = ConfigurationEngine(db, audit_log_service=None)
    await config_engine_no_audit.seed_defaults()
    
    # This should succeed without audit logging
    await config_engine_no_audit.set_global(
        ConfigKey.GRACE_PERIOD_HOURS,
        72,
        updated_by=admin.id
    )
    
    # Verify the change took effect
    updated_value = await config_engine_no_audit.get(ConfigKey.GRACE_PERIOD_HOURS)
    assert updated_value == 72, "Configuration change should succeed even without audit logging"
    
    # Test 4: Verify audit logging failure doesn't block configuration change
    # Create a mock audit service that raises an exception
    class FailingAuditLogService:
        async def append(self, *args, **kwargs):
            raise Exception("Audit logging failed")
    
    config_engine_failing_audit = ConfigurationEngine(db, audit_log_service=FailingAuditLogService())
    await config_engine_failing_audit.seed_defaults()
    
    # This should succeed despite audit logging failure
    await config_engine_failing_audit.set_global(
        ConfigKey.GRACE_PERIOD_HOURS,
        96,
        updated_by=admin.id
    )
    
    # Verify the change took effect
    final_value = await config_engine_failing_audit.get(ConfigKey.GRACE_PERIOD_HOURS)
    assert final_value == 96, "Configuration change should succeed even if audit logging fails"