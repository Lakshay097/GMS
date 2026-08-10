"""
Audit event type constants — v1.5 event types per Prompt 4.
"""
from enum import Enum


class AuditEventType(str, Enum):
    """Canonical audit action types for the shared append-only sink."""

    LOGIN = "login"
    KPI_EDITED = "kpi_edited"
    OBSERVATION_LOCKED = "observation_locked"
    ROLE_CHANGED = "role_changed"
    CONFIG_CHANGED = "config_changed"
    # v1.5 event types
    DUPLICATE_BLOCKED = "duplicate_blocked"
    DUPLICATE_OVERRIDE = "duplicate_override"
    REOPEN_REQUESTED = "reopen_requested"
    REOPEN_APPROVED = "reopen_approved"
    REOPEN_REJECTED = "reopen_rejected"
    COMPLIANCE_SCHEDULER_RUN = "compliance_scheduler_run"
    EVIDENCE_DELETED = "evidence_deleted"
    WORKFLOW_TRANSITION = "workflow_transition"
