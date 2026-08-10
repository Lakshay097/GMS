"""
Database models for School Operations Platform.
Implements user, role, school, and department entities per PRS §36 and Data Model Specification.
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import enum
from shared.database import Base
from shared.datetime_utils import utc_now

# Re-exports for backwards-compat: tests and older modules import these from shared.models
# The authoritative definitions live in shared.platform_models.
from shared.platform_models import DiscrepancyCategory, TaskCompletionRule  # noqa: F401
from shared.platform_models import (  # noqa: F401
    Observation,
    KPI,
    KRA,
    Task,
    TaskOwner,
    TaskStatus,
    TaskEscalation,
)


class UserRole(enum.Enum):
    """System roles per PRS §11."""
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    CHECKER = "checker"
    AUDITOR = "auditor"
    VIEWER = "viewer"


class UserStatus(enum.Enum):
    """User status per BR-08."""
    ACTIVE = "active"
    ARCHIVED = "archived"


class SchoolStatus(enum.Enum):
    """School status per PRS §18."""
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class DepartmentStatus(enum.Enum):
    """Department status per PRS §19."""
    ACTIVE = "active"
    ARCHIVED = "archived"


class School(Base):
    """
    School entity per PRS §18.
    Row-level isolation via school_id on all tenant-scoped tables.
    """
    __tablename__ = "schools"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(SQLEnum(SchoolStatus), default=SchoolStatus.ACTIVE, nullable=False)
    address = Column(Text)
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    configuration = Column(JSONB, default={})  # School-specific configuration overrides
    timezone = Column(String(100), nullable=True)  # IANA tz; seeded from DEFAULT_SCHOOL_TIMEZONE (BR-24)
    working_days = Column(
        JSONB,
        default=["mon", "tue", "wed", "thu", "fri", "sat"],
    )  # v1.5 School working days calendar (BR-22)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    deactivated_at = Column(DateTime, nullable=True)
    
    # Relationships
    departments = relationship("Department", back_populates="school", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_schools_status', 'status'),
    )


class Department(Base):
    """
    Department entity per PRS §19.
    Belongs to exactly one School (R-07).
    """
    __tablename__ = "departments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)
    status = Column(SQLEnum(DepartmentStatus), default=DepartmentStatus.ACTIVE, nullable=False)
    description = Column(Text)
    head_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    
    # Relationships
    school = relationship("School", back_populates="departments")
    
    __table_args__ = (
        Index('ix_departments_school_id', 'school_id'),
        Index('ix_departments_status', 'status'),
        Index('ix_departments_school_code', 'school_id', 'code', unique=True),
    )


class User(Base):
    """
    User entity per PRS §20 and BR-08.
    - Never hard-deleted, only archived (R-12)
    - May hold multiple roles within their school (R-08)
    - Belongs to exactly one School, except SuperAdmin (R-01)
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    neon_auth_user_id = Column(String(255), unique=True, nullable=False)  # Link to Neon Auth
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)  # Null for SuperAdmin
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    roles = Column(JSONB, default=list)  # List of UserRole enum values as strings
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255), nullable=True)  # Encrypted MFA secret
    phone = Column(String(50))
    employee_id = Column(String(50), unique=True, nullable=True)
    language_preference = Column(String(10), default="en", nullable=False)  # FR-163: Language preference (en, hi, etc.)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    
    # Relationships
    school = relationship("School", foreign_keys=[school_id])
    department = relationship("Department", foreign_keys=[department_id])
    
    __table_args__ = (
        Index('ix_users_school_id', 'school_id'),
        Index('ix_users_department_id', 'department_id'),
        Index('ix_users_status', 'status'),
    )


class UserSchoolGrant(Base):
    """
    Explicit scope-grant records for multi-school access per R-04.
    Used for Viewer (multiple schools) and SuperAdmin (all schools).
    Models multi-school access as explicit grants, never as a bypass.
    """
    __tablename__ = "user_school_grants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    granted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    granted_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration for temporary grants
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships - simplified to avoid ambiguity
    user = relationship("User", foreign_keys=[user_id])
    school = relationship("School", foreign_keys=[school_id])
    # Remove back_populates to avoid ambiguity
    
    __table_args__ = (
        Index('ix_user_school_grants_user_school', 'user_id', 'school_id', unique=True),
        Index('ix_user_school_grants_is_active', 'is_active'),
    )


class Permission(Base):
    """
    Permission definitions per PRS §12 Permission Matrix.
    Stores the canonical permission matrix for runtime evaluation.
    role stores the lowercase UserRole value (e.g., "superadmin", "admin").
    """
    __tablename__ = "permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module = Column(String(100), nullable=False)  # e.g., "school", "observation", "discrepancy"
    action = Column(String(100), nullable=False)  # e.g., "create", "read", "update", "delete"
    role = Column(String(50), nullable=False)  # Lowercase UserRole value (e.g., "superadmin")
    scope_constraint = Column(String(50), nullable=True)  # e.g., "school", "department", "own"
    is_allowed = Column(Boolean, nullable=False)  # True if permission granted, False if denied
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    __table_args__ = (
        Index('ix_permissions_module_action_role', 'module', 'action', 'role', unique=True),
        Index('ix_permissions_role', 'role'),
    )


class AuditLogEntry(Base):
    """
    Audit log per Architecture §5.5 and R-19.
    Append-only at database grant level - no UPDATE/DELETE grants.
    """
    __tablename__ = "audit_log_entries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., "create_observation", "approve_discrepancy"
    entity_type = Column(String(100), nullable=False)  # e.g., "observation", "task", "user"
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    old_values = Column(JSONB, nullable=True)  # For UPDATE operations
    new_values = Column(JSONB, nullable=True)  # For CREATE/UPDATE operations
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    
    __table_args__ = (
        Index('ix_audit_log_entries_timestamp', 'timestamp'),
        Index('ix_audit_log_entries_user_id', 'user_id'),
        Index('ix_audit_log_entries_school_id', 'school_id'),
        Index('ix_audit_log_entries_entity', 'entity_type', 'entity_id'),
    )
