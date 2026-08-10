"""
Platform service and scheduler-related SQLAlchemy models.
Per Data-Model.md §4-5 and Architecture.md §5.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from shared.database import Base
from shared.datetime_utils import utc_now


class ConfigValueType(str, enum.Enum):
    INTEGER = "integer"
    DECIMAL = "decimal"
    DURATION = "duration"
    ENUM = "enum"
    BOOLEAN = "boolean"
    JSON = "json"


class ConfigScopeType(str, enum.Enum):
    GLOBAL = "global"
    SCHOOL = "school"
    DEPARTMENT = "department"


class MasterDataStatus(str, enum.Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class NotificationCategory(int, enum.Enum):
    """R-38/BR-15: fixed priority order 1 (highest) through 7."""
    ESCALATION = 1
    AUDIT_FAILURE = 2
    TASK_ASSIGNMENT = 3
    DUE_TODAY = 4
    KPI_REMINDER = 5
    COMMENTS = 6
    INFORMATIONAL = 7


class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    FAILED = "failed"


class AssetStatus(str, enum.Enum):
    ACTIVE = "active"
    RETIRED = "retired"


class NonWorkingDayPolicy(str, enum.Enum):
    SKIP = "skip"
    SHIFT_FORWARD = "shift_forward"
    SHIFT_BACKWARD = "shift_backward"


class KpiStatus(str, enum.Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class KraStatus(str, enum.Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class KpiCaptureType(str, enum.Enum):
    VALUE_READING = "value_reading"
    EVENT_TIME = "event_time"
    VALUE_AND_EVENT_TIME = "value_and_event_time"


class KpiFormulaType(str, enum.Enum):
    THRESHOLD_COMPARISON = "threshold_comparison"


class KpiComparator(str, enum.Enum):
    GTE = ">="
    LTE = "<="
    EQ = "="
    LT = "<"
    GT = ">"


class AutoResult(str, enum.Enum):
    MET = "met"
    NOT_MET = "not_met"
    N_A = "n_a"


class RagStatus(str, enum.Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    NOT_SUBMITTED = "not_submitted"


VALID_COMPARATORS = frozenset({">=", "<=", "=", "<", ">"})


class ComplianceStatus(str, enum.Enum):
    OPEN = "open"
    LATE_SUBMITTABLE = "late_submittable"
    CLOSED_MISSED = "closed_missed"
    SUBMITTED = "submitted"


class SchedulerRunStatus(str, enum.Enum):
    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class ChecklistInstanceStatus(str, enum.Enum):
    GENERATED = "generated"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    MISSED = "missed"
    ESCALATED = "escalated"
    ARCHIVED = "archived"


class ChecklistTemplateStatus(str, enum.Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class ConfigurationItem(Base):
    """Data-Model §5.1 configuration_items."""

    __tablename__ = "configuration_items"

    config_key = Column(String(100), primary_key=True)
    value_type = Column(SQLEnum(ConfigValueType), nullable=False)
    global_default = Column(Text, nullable=False)
    editable_by = Column(String(50), nullable=False, default="admin")
    overridable_scope = Column(String(50), nullable=False, default="none")


class ConfigurationOverride(Base):
    """Data-Model §5.1 configuration_overrides."""

    __tablename__ = "configuration_overrides"

    config_key = Column(String(100), ForeignKey("configuration_items.config_key"), primary_key=True)
    scope_type = Column(String(50), primary_key=True)
    scope_id = Column(UUID(as_uuid=True), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=utc_now, nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class MasterDataEntry(Base):
    """Data-Model §4.4 master_data_entries — forward-only reference data (R-14)."""

    __tablename__ = "master_data_entries"

    code = Column(String(100), primary_key=True)
    category = Column(String(100), primary_key=True)
    label = Column(String(255), nullable=False)
    status = Column(SQLEnum(MasterDataStatus), default=MasterDataStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class DiscrepancyCategory(Base):
    """v1.5 discrepancy_categories per Data-Model §4.8."""

    __tablename__ = "discrepancy_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    allow_delegate = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class OrganizationHoliday(Base):
    """v1.5 organization_holiday_calendar per Data-Model §4.8."""

    __tablename__ = "organization_holiday_calendar"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True, index=True)
    holiday_date = Column(Date, nullable=False)
    label = Column(String(255), nullable=False)
    recurrence_type = Column(String(50), default="one_time", nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("school_id", "holiday_date", "label", name="uq_holiday_school_date_label"),
        Index("ix_holiday_school_date", "school_id", "holiday_date"),
    )


class Asset(Base):
    """v1.5 assets per Data-Model §4.6 — Active/Retired only (BR-23)."""

    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category_code = Column(String(100), nullable=True)
    location_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(SQLEnum(AssetStatus), default=AssetStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class DiscrepancyApprovalChainConfig(Base):
    """v1.5 approval chain configuration per Data-Model §4.8 — forward-only versioning (BR-21)."""

    __tablename__ = "discrepancy_approval_chain_config"

    chain_version_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    levels = Column(JSONB, nullable=False)  # Ordered approval levels with role-based approvers
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_approval_chain_active", "is_active"),
    )


class Discrepancy(Base):
    """
    v1.5 discrepancies per PRS §25-26.
    Linear state machine: Raised → Under Investigation → Resolved → Pending Approval (Level 1..N) → Closed.
    """

    __tablename__ = "discrepancies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id = Column(UUID(as_uuid=True), ForeignKey("observations.id", ondelete="RESTRICT"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("discrepancy_categories.id", ondelete="RESTRICT"), nullable=False)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True)
    raised_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    investigation_owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    state = Column(String(50), nullable=False, default="raised")  # Current state in workflow
    investigation_findings = Column(Text, nullable=True)  # Required before moving to Resolved
    bound_chain_version_id = Column(UUID(as_uuid=True), ForeignKey("discrepancy_approval_chain_config.chain_version_id", ondelete="RESTRICT"), nullable=True)  # Chain version when entering approval
    raised_at = Column(DateTime, default=utc_now, nullable=False)
    under_investigation_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_discrepancies_observation", "observation_id"),
        Index("ix_discrepancies_category", "category_id"),
        Index("ix_discrepancies_school", "school_id"),
        Index("ix_discrepancies_state", "state"),
        Index("ix_discrepancies_bound_chain", "bound_chain_version_id"),
    )


class DiscrepancyApprovalHistory(Base):
    """
    v1.5 discrepancy_approval_history per PRS §26.
    Records each approval action as a separate row (not fixed columns).
    One row per approval level with Role/User/Status/Comments.
    """

    __tablename__ = "discrepancy_approval_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    discrepancy_id = Column(UUID(as_uuid=True), ForeignKey("discrepancies.id", ondelete="CASCADE"), nullable=False)
    level = Column(Integer, nullable=False)  # Approval level (1, 2, 3, ...)
    assigned_role_id = Column(UUID(as_uuid=True), nullable=True)  # Role assigned to this level
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), nullable=False)  # pending, approved, rejected
    comments = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_approval_history_discrepancy", "discrepancy_id"),
        Index("ix_approval_history_level", "discrepancy_id", "level", unique=True),
    )


class Notification(Base):
    """Notifications table per Data-Model §4.3."""

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True, index=True)
    category = Column(Integer, nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    dispatched_at = Column(DateTime, nullable=True)


class WorkflowDefinition(Base):
    """Data-defined state machine definitions for Workflow Engine (ADR-03)."""

    __tablename__ = "workflow_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(100), unique=True, nullable=False)
    initial_state = Column(String(100), nullable=False)
    transitions = Column(JSONB, nullable=False, default=list)
    approval_chain_config = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class KRA(Base):
    """KRA model per Data-Model §3.4 / PRS §22."""

    __tablename__ = "kras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(KraStatus), default=KraStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class KPI(Base):
    """Versioned KPI model per Data-Model §3.5 / PRS §23 (R-17)."""

    __tablename__ = "kpis"

    kpi_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(Integer, primary_key=True, default=1)
    kra_id = Column(UUID(as_uuid=True), ForeignKey("kras.id"), nullable=False)
    title = Column(String(255), nullable=False)
    target_value = Column(Numeric, nullable=False, default=100)
    comparator = Column(String(10), nullable=False, default=">=")
    unit_of_measure = Column(String(50), nullable=False, default="percent")
    frequency_code = Column(String(50), nullable=False, default="daily")
    formula_type = Column(
        SQLEnum(KpiFormulaType),
        default=KpiFormulaType.THRESHOLD_COMPARISON,
        nullable=False,
    )
    capture_type = Column(
        SQLEnum(KpiCaptureType),
        default=KpiCaptureType.VALUE_READING,
        nullable=False,
    )
    category_code = Column(String(100), nullable=True)
    is_sensitive = Column(Boolean, default=False, nullable=False)
    evidence_required = Column(Boolean, default=False, nullable=False)
    amber_tolerance_band = Column(Numeric, nullable=True)
    working_days = Column(JSONB, nullable=True)
    non_working_day_policy = Column(
        SQLEnum(NonWorkingDayPolicy), default=NonWorkingDayPolicy.SKIP, nullable=False
    )
    status = Column(SQLEnum(KpiStatus), default=KpiStatus.ACTIVE, nullable=False)
    is_immutable = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    event_time_points = relationship(
        "KpiEventTimePoint",
        back_populates="kpi",
        cascade="all, delete-orphan",
    )


class KpiEventTimePoint(Base):
    """Child of KPI per Data-Model §3.5 / PRS §23.6."""

    __tablename__ = "kpi_event_time_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kpi_id = Column(UUID(as_uuid=True), nullable=False)
    kpi_version = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    capture_mode_allowed = Column(String(50), default="manual_only", nullable=False)
    target_time = Column(Time, nullable=True)

    kpi = relationship(
        "KPI",
        foreign_keys=[kpi_id, kpi_version],
        primaryjoin="and_(KpiEventTimePoint.kpi_id==KPI.kpi_id, KpiEventTimePoint.kpi_version==KPI.version)",
        back_populates="event_time_points",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["kpi_id", "kpi_version"],
            ["kpis.kpi_id", "kpis.version"],
        ),
    )


class DepartmentKpiAssignment(Base):
    """Department-to-KPI assignment per FR-055."""

    __tablename__ = "department_kpi_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    kpi_id = Column(UUID(as_uuid=True), nullable=False)
    assigned_at = Column(DateTime, default=utc_now, nullable=False)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("department_id", "kpi_id", name="uq_department_kpi_assignment"),
        Index("ix_department_kpi_kpi_id", "kpi_id"),
    )


class Observation(Base):
    """
    Observation per Data-Model §3.6 and PRS §24.
    Simplified non-partitioned table for Phase 1 module implementation.
    Extended with lock period, evidence, duplicate detection, and grace period tracking.
    """

    __tablename__ = "observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kpi_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    kpi_version = Column(Integer, nullable=False)
    checker_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False, index=True)
    value_numeric = Column(Numeric, nullable=True)
    value_text = Column(Text, nullable=True)
    auto_result = Column(SQLEnum(AutoResult), nullable=False)
    rag_status = Column(SQLEnum(RagStatus), nullable=False)
    submitted_at = Column(DateTime, default=utc_now, nullable=False)
    is_late = Column(Boolean, default=False, nullable=False)
    submission_token = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    location_id = Column(UUID(as_uuid=True), nullable=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True)
    event_times = Column(JSONB, nullable=True)
    time_capture_mode = Column(String(50), nullable=True)
    manual_time_reason = Column(String(100), nullable=True)
    
    # PRS §24 lock period tracking
    locked_at = Column(DateTime, nullable=True)
    
    # PRS §24 evidence storage (JSONB array of evidence metadata)
    evidence = Column(JSONB, nullable=True)
    
    # PRS §24.6 duplicate detection tracking
    is_duplicate_override = Column(Boolean, default=False, nullable=False)
    duplicate_override_justification = Column(Text, nullable=True)
    duplicate_override_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    original_observation_id = Column(UUID(as_uuid=True), nullable=True)
    
    # PRS §24.16 grace period & reopen tracking
    is_reopened = Column(Boolean, default=False, nullable=False)
    reopen_requested_at = Column(DateTime, nullable=True)
    reopen_requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reopen_reason = Column(Text, nullable=True)
    reopen_approved_at = Column(DateTime, nullable=True)
    reopen_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class ComplianceObservation(Base):
    """
    Compliance scheduler shell observation rows.
    Simplified observations table for platform scheduler (Data-Model §3.6).
    """

    __tablename__ = "compliance_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kpi_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    kpi_version = Column(Integer, nullable=False)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    location_id = Column(UUID(as_uuid=True), nullable=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True)
    compliance_status = Column(
        SQLEnum(ComplianceStatus), default=ComplianceStatus.OPEN, nullable=False
    )
    due_at = Column(DateTime, nullable=False)
    grace_period_elapsed_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "kpi_id",
            "kpi_version",
            "department_id",
            "location_id",
            "asset_id",
            "due_at",
            name="uq_compliance_observation_generation_key",
        ),
        Index("ix_compliance_obs_due", "compliance_status", "due_at"),
    )


class ChecklistTemplate(Base):
    """Checklist template per Data-Model §4.7."""

    __tablename__ = "checklist_templates"

    template_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(Integer, primary_key=True, default=1)
    title = Column(String(255), nullable=False)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    frequency_code = Column(String(50), nullable=False, default="daily")
    status = Column(
        SQLEnum(ChecklistTemplateStatus), default=ChecklistTemplateStatus.ACTIVE, nullable=False
    )
    is_immutable = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class ChecklistInstance(Base):
    """Checklist instance per Data-Model §4.7 — scheduler-generated (R-55)."""

    __tablename__ = "checklist_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), nullable=False)
    template_version = Column(Integer, nullable=False)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    status = Column(
        SQLEnum(ChecklistInstanceStatus), default=ChecklistInstanceStatus.GENERATED, nullable=False
    )
    generated_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "template_version",
            "school_id",
            "department_id",
            "period_start",
            name="uq_checklist_instance_generation_key",
        ),
    )


class ComplianceSchedulerRunLog(Base):
    """v1.5 compliance_scheduler_run_log per Data-Model §4.8 / Prompt 4."""

    __tablename__ = "compliance_scheduler_run_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(SchedulerRunStatus), nullable=False)
    records_generated = Column(Integer, default=0, nullable=False)
    records_backfilled = Column(Integer, default=0, nullable=False)
    school_timezone_batch = Column(String(100), nullable=True)
    error_detail = Column(Text, nullable=True)


# ── PRS §27 Task Management ───────────────────────────────────────────────────


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_APPROVAL = "pending_approval"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class TaskCompletionRule(str, enum.Enum):
    ANY_OWNER = "any_owner"        # ANY primary owner completing closes the task (R-31)
    ALL_OWNERS = "all_owners"      # ALL primary owners must complete (R-31)
    POST_APPROVAL = "post_approval"  # Completion requires post-completion approval (R-31/PRS §52)


class TaskEscalationStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Task(Base):
    """
    PRS §27 Task Management.
    Immutable fields: completion_rule (R-31/BR-09/PRS §52).
    ETA extension cap: 3 extensions maximum (R-33/BR-10/C8/R-42).
    A 4th extension request auto-converts to an escalation (R-33/BR-10).
    """

    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # R-31/BR-09/PRS §52 — IMMUTABLE after creation
    completion_rule = Column(SQLEnum(TaskCompletionRule), nullable=False)

    # R-32/PRS §52 — must be in the future at creation
    eta = Column(DateTime, nullable=False)

    # R-33/BR-10 — incremented on each approved extension; capped at 3
    eta_extension_count = Column(Integer, nullable=False, default=0)

    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.OPEN)

    # entity linkage (optional — task may be standalone or linked to observation/discrepancy)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    owners = relationship("TaskOwner", back_populates="task", cascade="all, delete-orphan")
    completions = relationship("TaskOwnerCompletion", back_populates="task", cascade="all, delete-orphan")
    eta_extensions = relationship("TaskEtaExtension", back_populates="task", cascade="all, delete-orphan")
    escalations = relationship("TaskEscalation", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tasks_school", "school_id"),
        Index("ix_tasks_department", "department_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_eta", "eta"),
        Index("ix_tasks_entity", "entity_type", "entity_id"),
    )


class TaskOwner(Base):
    """
    PRS §27 — Primary Owners of a Task.
    A Task must have ≥1 Primary Owner (R-30/BR-09).
    No collaborators; every owner receives notifications, reminders, escalations.
    """

    __tablename__ = "task_owners"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_at = Column(DateTime, nullable=False, default=utc_now)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    task = relationship("Task", back_populates="owners")

    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_task_owner"),
        Index("ix_task_owners_task", "task_id"),
        Index("ix_task_owners_user", "user_id"),
    )


class TaskOwnerCompletion(Base):
    """
    Per-owner completion record for ALL_OWNERS and POST_APPROVAL completion rules.
    For ANY_OWNER rule, the first completion closes the task.
    """

    __tablename__ = "task_owner_completions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    completed_at = Column(DateTime, nullable=False, default=utc_now)
    notes = Column(Text, nullable=True)

    task = relationship("Task", back_populates="completions")

    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_task_owner_completion"),
        Index("ix_task_completions_task", "task_id"),
    )


class TaskEtaExtension(Base):
    """
    Records each ETA extension request and its outcome.
    Maximum 3 extensions per task (R-33/BR-10).  A 4th request is converted to escalation.
    """

    __tablename__ = "task_eta_extensions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    previous_eta = Column(DateTime, nullable=False)
    requested_eta = Column(DateTime, nullable=False)
    # outcome: "granted" | "auto_escalated" (4th attempt)
    outcome = Column(String(50), nullable=False, default="granted")
    justification = Column(Text, nullable=True)
    requested_at = Column(DateTime, nullable=False, default=utc_now)

    task = relationship("Task", back_populates="eta_extensions")

    __table_args__ = (
        Index("ix_eta_extensions_task", "task_id"),
    )


class TaskEscalation(Base):
    """
    Escalation record for a task.
    Sourced from the per-department escalation_rules table (Configuration Engine).
    Created by the scheduled escalation checker job.
    """

    __tablename__ = "task_escalations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    # trigger: "overdue_sla" | "fourth_extension_request"
    trigger = Column(String(100), nullable=False)
    escalation_level = Column(Integer, nullable=False, default=1)
    escalated_to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    escalated_to_role_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(SQLEnum(TaskEscalationStatus), nullable=False, default=TaskEscalationStatus.OPEN)
    notes = Column(Text, nullable=True)
    escalated_at = Column(DateTime, nullable=False, default=utc_now)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="escalations")

    __table_args__ = (
        Index("ix_task_escalations_task", "task_id"),
        Index("ix_task_escalations_status", "status"),
        Index("ix_task_escalations_escalated_at", "escalated_at"),
    )


class EscalationRule(Base):
    """
    Configurable, per-department Escalation Matrix (PRS §27 Escalation Matrix).
    Sourced from the Configuration Engine; used by the scheduled escalation checker.
    SLA timers are in hours from the task ETA.
    """

    __tablename__ = "escalation_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)  # NULL = global default
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=True)         # NULL = all schools
    escalation_level = Column(Integer, nullable=False)  # 1, 2, 3, ...
    sla_hours = Column(Integer, nullable=False)          # hours after ETA before this level fires
    escalate_to_role_id = Column(UUID(as_uuid=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_escalation_rules_dept", "department_id"),
        Index("ix_escalation_rules_school", "school_id"),
        Index("ix_escalation_rules_active", "is_active"),
        UniqueConstraint("department_id", "school_id", "escalation_level", name="uq_escalation_rule_level"),
    )


# ── PRS §28-29 Performance Reviews & Scorecards ───────────────────────────────


class PerformanceReviewStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ScorecardSubjectType(str, enum.Enum):
    USER = "user"
    DEPARTMENT = "department"


class PerformanceReview(Base):
    """
    Performance Review period per PRS §28.
    Represents a review cycle (cycle_start → cycle_end) for a school/department.
    Cadence is driven by PERFORMANCE_REVIEW_CADENCE_DAYS from the Configuration Engine.
    """

    __tablename__ = "performance_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False
    )
    department_id = Column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    cycle_start = Column(Date, nullable=False)
    cycle_end = Column(Date, nullable=False)
    # Cadence in days at creation time (snapshot — Configuration Engine value may change later)
    cadence_days = Column(Integer, nullable=False)
    status = Column(
        SQLEnum(PerformanceReviewStatus),
        default=PerformanceReviewStatus.SCHEDULED,
        nullable=False,
    )
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    scorecards = relationship(
        "Scorecard",
        back_populates="review",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "department_id",
            "cycle_start",
            "cycle_end",
            name="uq_performance_review_cycle",
        ),
        Index("ix_perf_review_school", "school_id"),
        Index("ix_perf_review_department", "department_id"),
        Index("ix_perf_review_status", "status"),
        Index("ix_perf_review_cycle", "cycle_start", "cycle_end"),
    )


class Scorecard(Base):
    """
    Scorecard per PRS §29 / Data-Model §3.9.

    IMMUTABILITY RULES (R-18/BR-14/C6):
      - Scorecards are GENERATED, never updated.
      - Recalculation creates a NEW version row (v2, v3, …).
      - The prior version is retained and marked superseded_by → new version id.
      - No application role holds UPDATE/DELETE grants on this table.

    The composite unique key (subject_type, subject_id, cycle_start, cycle_end, version)
    enforces that each subject×cycle×version combination is written exactly once.
    """

    __tablename__ = "scorecards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Parent review (nullable — scorecards can be generated ad-hoc via job queue)
    review_id = Column(
        UUID(as_uuid=True),
        ForeignKey("performance_reviews.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Subject — either a user or a department
    subject_type = Column(SQLEnum(ScorecardSubjectType), nullable=False)
    subject_id = Column(UUID(as_uuid=True), nullable=False)

    # Cycle dates — denormalised copy from the parent review for query convenience
    cycle_start = Column(Date, nullable=False)
    cycle_end = Column(Date, nullable=False)

    # Immutable version counter.  v1 is the first generation for this subject×cycle.
    # Each recalculation increments this by 1.  Prior versions retain their rows.
    version = Column(Integer, nullable=False, default=1)

    # R-18/BR-14: superseded_by is set (not null) once a newer version exists.
    # The column is a self-referential FK — points to the row that supersedes this one.
    superseded_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scorecards.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── computed metrics ─────────────────────────────────────────────────────
    # Worst-status-wins aggregate across all KPI observations in the cycle.
    rag_status = Column(SQLEnum(RagStatus), nullable=False)

    # Percentage of KPIs with auto_result == "met" in the cycle window.
    pct_kpis_met = Column(Numeric(5, 2), nullable=False, default=0)

    # Percentage of assigned tasks completed on or before their ETA.
    pct_tasks_on_time = Column(Numeric(5, 2), nullable=False, default=0)

    # Count of open (unresolved) discrepancies at cycle_end.
    open_discrepancy_count = Column(Integer, nullable=False, default=0)

    # JSONB snapshot of per-KPI roll-up used to compute rag_status (audit trail).
    kpi_breakdown = Column(JSONB, nullable=True)

    generated_at = Column(DateTime, nullable=False, default=utc_now)

    review = relationship("PerformanceReview", back_populates="scorecards")
    superseded_by = relationship(
        "Scorecard",
        foreign_keys=[superseded_by_id],
        remote_side="Scorecard.id",
        uselist=False,
    )

    __table_args__ = (
        # Ensures each subject×cycle×version is written once and only once.
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "cycle_start",
            "cycle_end",
            "version",
            name="uq_scorecard_subject_cycle_version",
        ),
        Index("ix_scorecard_review", "review_id"),
        Index("ix_scorecard_subject", "subject_type", "subject_id"),
        Index("ix_scorecard_cycle", "cycle_start", "cycle_end"),
        Index("ix_scorecard_version", "subject_type", "subject_id", "cycle_start", "cycle_end", "version"),
        Index("ix_scorecard_superseded_by", "superseded_by_id"),
    )


class ScorecardRunLog(Base):
    """
    Audit log for each scorecard generation job run per PRS §29.
    Mirrors ComplianceSchedulerRunLog pattern.
    """

    __tablename__ = "scorecard_run_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id = Column(
        UUID(as_uuid=True),
        ForeignKey("performance_reviews.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(SchedulerRunStatus), nullable=False)
    scorecards_generated = Column(Integer, default=0, nullable=False)
    scorecards_versioned = Column(Integer, default=0, nullable=False)
    error_detail = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_scorecard_run_log_review", "review_id"),
        Index("ix_scorecard_run_log_started", "started_at"),
    )


# ---------------------------------------------------------------------------
# Backwards-compat alias — tests import `Holiday` from shared.platform_models
# The full model is OrganizationHoliday; alias keeps tests passing without
# renaming the canonical model (which would require a migration).
# Tests use slightly different field names (date, name, is_school_wide);
# a thin subclass normalises those to the real column names.
# ---------------------------------------------------------------------------

class Holiday(OrganizationHoliday):
    """
    Convenience alias for OrganizationHoliday that also accepts the
    field names used in test fixtures (date, name, is_school_wide).
    """
    def __init__(self, **kwargs):
        # Map alternate field names to canonical column names
        if "date" in kwargs and "holiday_date" not in kwargs:
            kwargs["holiday_date"] = kwargs.pop("date")
        if "name" in kwargs and "label" not in kwargs:
            kwargs["label"] = kwargs.pop("name")
        # is_school_wide has no DB column — drop it silently (school_id=None means global)
        kwargs.pop("is_school_wide", None)
        super().__init__(**kwargs)

    __mapper_args__ = {"polymorphic_identity": "holiday"}  # noqa: RUF012
