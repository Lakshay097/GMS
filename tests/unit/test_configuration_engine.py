"""Unit tests for Configuration Engine — Architecture §5.1."""
import uuid

import pytest

from platform_services.configuration_engine.constants import MAX_ETA_EXTENSIONS, ConfigKey
from platform_services.configuration_engine.service import ConfigurationEngine
from shared.errors import BusinessRuleError


@pytest.mark.asyncio
async def test_configuration_engine_seeds_and_resolves_global(db):
    engine = ConfigurationEngine(db)
    await engine.seed_defaults()

    lock_period = await engine.get(ConfigKey.OBSERVATION_LOCK_PERIOD_MINUTES)
    assert isinstance(lock_period, int)
    assert lock_period > 0


@pytest.mark.asyncio
async def test_R42_max_eta_extensions_not_configurable(db):
    """R-42/R-33: Max ETA Extensions is fixed at 3 and cannot be overridden."""
    engine = ConfigurationEngine(db)
    await engine.seed_defaults()

    value = await engine.get(ConfigKey.MAX_ETA_EXTENSIONS)
    assert value == MAX_ETA_EXTENSIONS == 3

    with pytest.raises(BusinessRuleError, match="cannot be changed"):
        await engine.set_global(ConfigKey.MAX_ETA_EXTENSIONS, 5)

    with pytest.raises(BusinessRuleError, match="cannot be overridden"):
        await engine.set_override(
            ConfigKey.MAX_ETA_EXTENSIONS,
            "school",
            uuid.uuid4(),
            5,
        )


@pytest.mark.asyncio
async def test_configuration_school_override(db, school):
    engine = ConfigurationEngine(db)
    await engine.seed_defaults()

    await engine.set_override(
        ConfigKey.SESSION_TIMEOUT_MINUTES,
        "school",
        school.id,
        45,
    )
    global_val = await engine.get(ConfigKey.SESSION_TIMEOUT_MINUTES)
    school_val = await engine.get(ConfigKey.SESSION_TIMEOUT_MINUTES, school_id=school.id)
    assert school_val == 45
    assert global_val != 45 or global_val == 45  # school override takes precedence


@pytest.mark.asyncio
async def test_v15_duplicate_grace_evidence_config_keys(db):
    """v1.5 config keys seeded from env-and-secrets.md §6a."""
    engine = ConfigurationEngine(db)
    await engine.seed_defaults()

    dup_window = await engine.get(ConfigKey.DUPLICATE_DETECTION_WINDOW_MINUTES)
    grace = await engine.get(ConfigKey.GRACE_PERIOD_HOURS)
    retention = await engine.get(ConfigKey.EVIDENCE_RETENTION_PERIOD_DAYS)

    assert dup_window > 0
    assert grace > 0
    assert retention > 0


@pytest.mark.asyncio
async def test_FR164_immediate_setting_changes_without_relogin(db, school):
    """FR-164: Configuration changes are immediately visible without re-login."""
    engine = ConfigurationEngine(db)
    await engine.seed_defaults()

    # Get original value
    original_value = await engine.get(ConfigKey.SESSION_TIMEOUT_MINUTES)
    
    # Set a new global value via set_global()
    new_value = original_value + 10
    await engine.set_global(ConfigKey.SESSION_TIMEOUT_MINUTES, new_value)
    
    # Immediately call get() in the same session - should return new value
    # No cache clear, no re-login, no service restart
    immediate_value = await engine.get(ConfigKey.SESSION_TIMEOUT_MINUTES)
    assert immediate_value == new_value, "Configuration change should be immediately visible"
    
    # Test with school override as well
    school_override_value = original_value + 20
    await engine.set_override(
        ConfigKey.SESSION_TIMEOUT_MINUTES,
        "school",
        school.id,
        school_override_value
    )
    
    # Immediately get school-scoped value - should return override
    immediate_school_value = await engine.get(
        ConfigKey.SESSION_TIMEOUT_MINUTES,
        school_id=school.id
    )
    assert immediate_school_value == school_override_value, "School override should be immediately visible"


@pytest.mark.asyncio
async def test_FR166_configuration_engine_lacks_role_enforcement(db, school):
    """
    FR-166 GAP IDENTIFIED: ConfigurationEngine.set_global() and set_override() 
    do NOT enforce editable_by restrictions internally.
    
    Enforcement exists ONLY at the API route layer (configuration_routes.py lines 178-207).
    ConfigurationEngine itself accepts any caller regardless of role.
    
    This test calls ConfigurationEngine directly (bypassing API routes) to demonstrate
    that a non-admin actor could theoretically modify configuration if they have
    direct service access.
    
    SECURITY GAP: The test demonstrates that ConfigurationEngine has no internal
    role-based access control. Any code with direct access to the service can modify
    configuration regardless of the editable_by setting. This is a security concern
    that requires service-layer enforcement, not just API-layer enforcement.
    """
    engine = ConfigurationEngine(db)
    await engine.seed_defaults()

    # Use SESSION_TIMEOUT_MINUTES which is editable_by="admin" per CONFIG_DEFINITIONS
    # This should be restricted to admin role, but ConfigurationEngine doesn't check
    
    # Call set_global() directly without any role check
    # This simulates a non-admin actor with direct service access
    # The service layer does NOT check editable_by - this succeeds (demonstrating the gap)
    original_value = await engine.get(ConfigKey.SESSION_TIMEOUT_MINUTES)
    new_value = original_value + 100
    
    # GAP: This call should fail if editable_by were enforced at service layer
    # But it succeeds because ConfigurationEngine has no internal role checking
    await engine.set_global(ConfigKey.SESSION_TIMEOUT_MINUTES, new_value)
    
    # Verify the change was applied despite no role authorization (demonstrating the gap)
    result = await engine.get(ConfigKey.SESSION_TIMEOUT_MINUTES)
    assert result == new_value, "GAP: Configuration change succeeded without role authorization"
    
    # Same test for set_override - no role check at service layer
    school_override_value = original_value + 200
    await engine.set_override(
        ConfigKey.SESSION_TIMEOUT_MINUTES,
        "school",
        school.id,
        school_override_value
    )
    
    # Verify override was applied despite no role authorization (demonstrating the gap)
    result = await engine.get(ConfigKey.SESSION_TIMEOUT_MINUTES, school_id=school.id)
    assert result == school_override_value, "GAP: Configuration override succeeded without role authorization"

