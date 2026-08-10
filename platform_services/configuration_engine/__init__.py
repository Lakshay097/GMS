"""Configuration Engine — Architecture §5.1."""

from platform_services.configuration_engine.service import (
    ConfigurationEngine,
    ConfigurationError,
    ConfigKey,
    MAX_ETA_EXTENSIONS,
    NON_OVERRIDABLE_KEYS,
)

__all__ = [
    "ConfigurationEngine",
    "ConfigurationError",
    "ConfigKey",
    "MAX_ETA_EXTENSIONS",
    "NON_OVERRIDABLE_KEYS",
]
