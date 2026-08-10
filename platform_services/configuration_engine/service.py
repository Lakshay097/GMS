"""
Configuration Engine service — Architecture §5.1.
Centralizes platform configuration with global + school scope tiers.
"""
from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.audit_log_service.event_types import AuditEventType
from platform_services.configuration_engine.constants import (
    CONFIG_DEFINITIONS,
    MAX_ETA_EXTENSIONS,
    NON_OVERRIDABLE_KEYS,
    ConfigKey,
)
from shared.errors import BusinessRuleError, ValidationError
from shared.platform_models import ConfigValueType, ConfigurationItem, ConfigurationOverride

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Configuration Engine domain error."""


class ConfigurationEngine:
    """
    Resolves configuration values with scope tier support:
    school override → global default.
    Phase 2 adds department tier without code changes.
    """

    def __init__(self, db: AsyncSession, audit_log_service: Optional[Any] = None):
        self.db = db
        self.audit_log_service = audit_log_service

    async def seed_defaults(self) -> None:
        """Seed configuration_items from env-and-secrets.md defaults."""
        for config_key, definition in CONFIG_DEFINITIONS.items():
            existing = await self.db.get(ConfigurationItem, config_key)
            if existing is None:
                self.db.add(
                    ConfigurationItem(
                        config_key=config_key,
                        value_type=definition["value_type"],
                        global_default=definition["global_default"],
                        editable_by=definition["editable_by"],
                        overridable_scope=definition["overridable_scope"],
                    )
                )
        await self.db.commit()

    async def get(
        self,
        key: str | ConfigKey,
        *,
        school_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
    ) -> Any:
        """Resolve a configuration value for the given scope."""
        config_key = key.value if isinstance(key, ConfigKey) else key

        if config_key == ConfigKey.MAX_ETA_EXTENSIONS.value:
            # R-42/R-33: always returns fixed value, never from overrides.
            return MAX_ETA_EXTENSIONS

        item = await self.db.get(ConfigurationItem, config_key)
        if item is None:
            raise ConfigurationError(f"Unknown configuration key: {config_key}")

        raw_value = item.global_default

        if school_id is not None and item.overridable_scope in ("school", "department"):
            override = await self._get_override(config_key, "school", school_id)
            if override is not None:
                raw_value = override

        if department_id is not None and item.overridable_scope == "department":
            override = await self._get_override(config_key, "department", department_id)
            if override is not None:
                raw_value = override

        return self._cast_value(raw_value, item.value_type)

    async def set_global(
        self,
        key: str | ConfigKey,
        value: Any,
        *,
        updated_by: Optional[UUID] = None,
    ) -> None:
        """Update the global default for a configuration key."""
        config_key = key.value if isinstance(key, ConfigKey) else key

        if config_key in NON_OVERRIDABLE_KEYS:
            raise BusinessRuleError(
                "max_eta_extensions is fixed at 3 and cannot be changed (R-42/R-33)",
                details={"config_key": config_key},
            )

        item = await self.db.get(ConfigurationItem, config_key)
        if item is None:
            raise ConfigurationError(f"Unknown configuration key: {config_key}")

        # Capture old value for audit logging
        old_value = item.global_default

        # Update the configuration
        item.global_default = self._serialize_value(value, item.value_type)
        await self.db.commit()

        # Log the configuration change to audit log
        if self.audit_log_service:
            try:
                await self.audit_log_service.append(
                    action=AuditEventType.CONFIG_CHANGED,
                    entity_type="configuration",
                    entity_id=None,
                    actor_id=updated_by,
                    old_values={"key": config_key, "value": old_value, "scope": "global"},
                    new_values={"key": config_key, "value": item.global_default, "scope": "global"},
                )
            except Exception as e:
                # Log audit error but don't fail the configuration change
                # This ensures configuration changes succeed even if audit logging fails
                # but the failure is visible in logs for production monitoring
                logger.error(
                    f"Failed to log configuration change for {config_key}: {e}",
                    exc_info=True
                )

    async def set_override(
        self,
        key: str | ConfigKey,
        scope_type: str,
        scope_id: UUID,
        value: Any,
        *,
        updated_by: Optional[UUID] = None,
    ) -> None:
        """Set a school or department override."""
        config_key = key.value if isinstance(key, ConfigKey) else key

        if config_key in NON_OVERRIDABLE_KEYS:
            raise BusinessRuleError(
                "max_eta_extensions is fixed at 3 and cannot be overridden (R-42/R-33)",
                details={"config_key": config_key},
            )

        item = await self.db.get(ConfigurationItem, config_key)
        if item is None:
            raise ConfigurationError(f"Unknown configuration key: {config_key}")

        if item.overridable_scope == "none":
            raise ValidationError(
                f"Configuration key '{config_key}' does not support overrides",
                field="config_key",
            )

        if scope_type == "department" and item.overridable_scope != "department":
            raise ValidationError(
                f"Configuration key '{config_key}' does not support department overrides",
                field="scope_type",
            )

        serialized = self._serialize_value(value, item.value_type)
        existing = await self.db.get(
            ConfigurationOverride,
            {"config_key": config_key, "scope_type": scope_type, "scope_id": scope_id},
        )
        
        # Capture old value for audit logging
        old_value = existing.value if existing else None

        if existing:
            existing.value = serialized
            existing.updated_by = updated_by
        else:
            self.db.add(
                ConfigurationOverride(
                    config_key=config_key,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    value=serialized,
                    updated_by=updated_by,
                )
            )
        await self.db.commit()

        # Log the configuration change to audit log
        if self.audit_log_service:
            try:
                await self.audit_log_service.append(
                    action=AuditEventType.CONFIG_CHANGED,
                    entity_type="configuration",
                    entity_id=None,
                    actor_id=updated_by,
                    old_values={"key": config_key, "value": old_value, "scope": scope_type, "scope_id": str(scope_id)},
                    new_values={"key": config_key, "value": serialized, "scope": scope_type, "scope_id": str(scope_id)},
                )
            except Exception as e:
                # Log audit error but don't fail the configuration change
                # This ensures configuration changes succeed even if audit logging fails
                # but the failure is visible in logs for production monitoring
                logger.error(
                    f"Failed to log configuration override for {config_key}: {e}",
                    exc_info=True
                )

    async def is_feature_enabled(
        self,
        flag_key: str,
        *,
        school_id: Optional[UUID] = None,
    ) -> bool:
        """Feature flags are configuration items prefixed with 'feature.'."""
        try:
            return bool(await self.get(flag_key, school_id=school_id))
        except ConfigurationError:
            return False

    async def get_amber_tolerance_band(
        self,
        *,
        category_code: Optional[str] = None,
        school_id: Optional[UUID] = None,
        kpi_override: Optional[Any] = None,
    ) -> Any:
        """
        Resolve KPI Amber Tolerance Band per R-37/D6.
        Precedence: KPI-level override → per-category override → school override → global default.
        """
        if kpi_override is not None:
            return kpi_override

        if category_code:
            category_key = f"{ConfigKey.KPI_AMBER_TOLERANCE_BAND.value}.{category_code}"
            item = await self.db.get(ConfigurationItem, category_key)
            if item is not None:
                return self._cast_value(item.global_default, item.value_type)

        return await self.get(ConfigKey.KPI_AMBER_TOLERANCE_BAND, school_id=school_id)

    async def set_category_amber_tolerance_band(
        self,
        category_code: str,
        value: Any,
        *,
        updated_by: Optional[UUID] = None,
    ) -> None:
        """Set per-category Amber Tolerance Band override (R-37/D6)."""
        category_key = f"{ConfigKey.KPI_AMBER_TOLERANCE_BAND.value}.{category_code}"
        item = await self.db.get(ConfigurationItem, category_key)
        if item is None:
            self.db.add(
                ConfigurationItem(
                    config_key=category_key,
                    value_type=ConfigValueType.DECIMAL,
                    global_default=str(value),
                    editable_by="super_admin",
                    overridable_scope="none",
                )
            )
        else:
            item.global_default = str(value)
        await self.db.commit()

    async def _get_override(
        self,
        config_key: str,
        scope_type: str,
        scope_id: UUID,
    ) -> Optional[str]:
        result = await self.db.execute(
            select(ConfigurationOverride).where(
                ConfigurationOverride.config_key == config_key,
                ConfigurationOverride.scope_type == scope_type,
                ConfigurationOverride.scope_id == scope_id,
            )
        )
        override = result.scalar_one_or_none()
        return override.value if override else None

    @staticmethod
    def _cast_value(raw: str, value_type: ConfigValueType) -> Any:
        if value_type == ConfigValueType.INTEGER:
            return int(raw)
        if value_type == ConfigValueType.DECIMAL:
            return Decimal(raw)
        if value_type == ConfigValueType.BOOLEAN:
            return raw.lower() in ("true", "1", "yes")
        if value_type == ConfigValueType.JSON:
            return json.loads(raw)
        return raw

    @staticmethod
    def _serialize_value(value: Any, value_type: ConfigValueType) -> str:
        if value_type == ConfigValueType.JSON:
            # If the caller already passed a JSON string, store it verbatim.
            # This avoids double-encoding when a string like '["hi"]' arrives
            # (json.dumps would wrap it as '"[\\"hi\\"]"' making round-trip break).
            if isinstance(value, str):
                # Validate it's actually valid JSON before storing.
                try:
                    json.loads(value)
                    return value
                except (json.JSONDecodeError, ValueError):
                    pass  # fall through — serialize whatever Python object it is
            return json.dumps(value)
        return str(value)
