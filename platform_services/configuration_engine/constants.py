"""
Configuration Engine seed values and key registry.
Per env-and-secrets.md §6a and PRS §54.
"""
from __future__ import annotations

import os
from enum import Enum

from shared.platform_models import ConfigValueType


# R-42/R-33: Max ETA Extensions is fixed at 3 and NOT overridable via Configuration Engine.
MAX_ETA_EXTENSIONS = 3

NON_OVERRIDABLE_KEYS = frozenset({"max_eta_extensions"})


class ConfigKey(str, Enum):
  """Known configuration keys centralized by the Configuration Engine."""

  OBSERVATION_LOCK_PERIOD_MINUTES = "observation_lock_period_minutes"
  MAX_ETA_EXTENSIONS = "max_eta_extensions"
  ESCALATION_SLA_LEVEL_1_HOURS = "escalation_sla_level_1_hours"
  ESCALATION_SLA_LEVEL_2_HOURS = "escalation_sla_level_2_hours"
  ESCALATION_SLA_LEVEL_3_HOURS = "escalation_sla_level_3_hours"
  REMINDER_FREQUENCY_HOURS = "reminder_frequency_hours"
  PERFORMANCE_REVIEW_CADENCE_DAYS = "performance_review_cadence_days"
  SESSION_TIMEOUT_MINUTES = "session_timeout_minutes"
  FILE_UPLOAD_MAX_SIZE_MB = "file_upload_max_size_mb"
  LOCALES = "locales"
  KPI_AMBER_TOLERANCE_BAND = "kpi_amber_tolerance_band"
  KPI_ROUNDING_DECIMAL_PLACES = "kpi_rounding_decimal_places"
  KPI_ROUNDING_MODE = "kpi_rounding_mode"
  KPI_MISSING_DATA_BEHAVIOR = "kpi_missing_data_behavior"
  DUPLICATE_DETECTION_WINDOW_MINUTES = "duplicate_detection_window_minutes"
  GRACE_PERIOD_HOURS = "grace_period_hours"
  EVIDENCE_RETENTION_PERIOD_DAYS = "evidence_retention_period_days"
  # PRS §27 Task Management — escalation matrix SLA timers (per-department overridable)
  TASK_ESCALATION_LEVEL_1_SLA_HOURS = "task_escalation_level_1_sla_hours"
  TASK_ESCALATION_LEVEL_2_SLA_HOURS = "task_escalation_level_2_sla_hours"
  TASK_ESCALATION_LEVEL_3_SLA_HOURS = "task_escalation_level_3_sla_hours"
  TASK_REMINDER_HOURS_BEFORE_ETA = "task_reminder_hours_before_eta"


CONFIG_DEFINITIONS: dict[str, dict] = {
    ConfigKey.OBSERVATION_LOCK_PERIOD_MINUTES.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "60",
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.MAX_ETA_EXTENSIONS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": str(MAX_ETA_EXTENSIONS),
        "editable_by": "super_admin",
        "overridable_scope": "none",  # R-42: not overridable
    },
    ConfigKey.ESCALATION_SLA_LEVEL_1_HOURS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "24",
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.ESCALATION_SLA_LEVEL_2_HOURS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "48",
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.ESCALATION_SLA_LEVEL_3_HOURS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "72",
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.REMINDER_FREQUENCY_HOURS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "24",
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.PERFORMANCE_REVIEW_CADENCE_DAYS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "90",
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.SESSION_TIMEOUT_MINUTES.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": os.getenv("SESSION_TIMEOUT_MINUTES", "30"),
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.FILE_UPLOAD_MAX_SIZE_MB.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": os.getenv("FILE_UPLOAD_MAX_SIZE_MB", "10"),
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.LOCALES.value: {
        "value_type": ConfigValueType.JSON,
        "global_default": '["en", "hi"]',
        "editable_by": "super_admin",
        "overridable_scope": "none",
    },
    ConfigKey.KPI_AMBER_TOLERANCE_BAND.value: {
        "value_type": ConfigValueType.DECIMAL,
        "global_default": "5.0",
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.KPI_ROUNDING_DECIMAL_PLACES.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "2",
        "editable_by": "admin",
        "overridable_scope": "none",
    },
    ConfigKey.KPI_ROUNDING_MODE.value: {
        "value_type": ConfigValueType.ENUM,
        "global_default": "round_half_up",
        "editable_by": "admin",
        "overridable_scope": "none",
    },
    ConfigKey.KPI_MISSING_DATA_BEHAVIOR.value: {
        "value_type": ConfigValueType.ENUM,
        "global_default": "not_submitted",
        "editable_by": "admin",
        "overridable_scope": "none",
    },
    ConfigKey.DUPLICATE_DETECTION_WINDOW_MINUTES.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": os.getenv("DUPLICATE_DETECTION_WINDOW_MINUTES", "60"),
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.GRACE_PERIOD_HOURS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": os.getenv("GRACE_PERIOD_HOURS", "24"),
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    ConfigKey.EVIDENCE_RETENTION_PERIOD_DAYS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": os.getenv("EVIDENCE_RETENTION_PERIOD_DAYS", "90"),
        "editable_by": "admin",
        "overridable_scope": "school",
    },
    # PRS §27 Task escalation matrix — per-department overridable SLA timers
    ConfigKey.TASK_ESCALATION_LEVEL_1_SLA_HOURS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "24",
        "editable_by": "admin",
        "overridable_scope": "department",
    },
    ConfigKey.TASK_ESCALATION_LEVEL_2_SLA_HOURS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "48",
        "editable_by": "admin",
        "overridable_scope": "department",
    },
    ConfigKey.TASK_ESCALATION_LEVEL_3_SLA_HOURS.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "72",
        "editable_by": "admin",
        "overridable_scope": "department",
    },
    ConfigKey.TASK_REMINDER_HOURS_BEFORE_ETA.value: {
        "value_type": ConfigValueType.INTEGER,
        "global_default": "24",
        "editable_by": "admin",
        "overridable_scope": "department",
    },
}
