"""Add task management tables for PRS §27.

Tables: tasks, task_owners, task_owner_completions, task_eta_extensions,
        task_escalations, escalation_rules.

Revision ID: 20260808_task_management
Revises: 20260808_discrepancy_tables
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260808_task_management"
down_revision = "20260808_discrepancy_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── tasks ────────────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # R-31/BR-09/PRS §52 — IMMUTABLE after creation
        sa.Column("completion_rule", sa.String(50), nullable=False),
        # R-32 — must be in future at creation
        sa.Column("eta", sa.DateTime(), nullable=False),
        # R-33/BR-10 — capped at 3
        sa.Column("eta_extension_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        # optional entity linkage
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tasks_school", "tasks", ["school_id"])
    op.create_index("ix_tasks_department", "tasks", ["department_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_eta", "tasks", ["eta"])
    op.create_index("ix_tasks_entity", "tasks", ["entity_type", "entity_id"])

    # ── task_owners ──────────────────────────────────────────────────────────
    op.create_table(
        "task_owners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column(
            "assigned_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_owner"),
    )
    op.create_index("ix_task_owners_task", "task_owners", ["task_id"])
    op.create_index("ix_task_owners_user", "task_owners", ["user_id"])

    # ── task_owner_completions ───────────────────────────────────────────────
    op.create_table(
        "task_owner_completions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_owner_completion"),
    )
    op.create_index("ix_task_completions_task", "task_owner_completions", ["task_id"])

    # ── task_eta_extensions ──────────────────────────────────────────────────
    op.create_table(
        "task_eta_extensions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("previous_eta", sa.DateTime(), nullable=False),
        sa.Column("requested_eta", sa.DateTime(), nullable=False),
        # "granted" | "auto_escalated"
        sa.Column("outcome", sa.String(50), nullable=False, server_default="granted"),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_eta_extensions_task", "task_eta_extensions", ["task_id"])

    # ── task_escalations ─────────────────────────────────────────────────────
    op.create_table(
        "task_escalations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # "overdue_sla" | "fourth_extension_request"
        sa.Column("trigger", sa.String(100), nullable=False),
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "escalated_to_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("escalated_to_role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("escalated_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_task_escalations_task", "task_escalations", ["task_id"])
    op.create_index("ix_task_escalations_status", "task_escalations", ["status"])
    op.create_index("ix_task_escalations_escalated_at", "task_escalations", ["escalated_at"])

    # ── escalation_rules ─────────────────────────────────────────────────────
    op.create_table(
        "escalation_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # NULL = global default (applies when no dept/school override exists)
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column("sla_hours", sa.Integer(), nullable=False),
        sa.Column("escalate_to_role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "department_id", "school_id", "escalation_level",
            name="uq_escalation_rule_level",
        ),
    )
    op.create_index("ix_escalation_rules_dept", "escalation_rules", ["department_id"])
    op.create_index("ix_escalation_rules_school", "escalation_rules", ["school_id"])
    op.create_index("ix_escalation_rules_active", "escalation_rules", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_escalation_rules_active", table_name="escalation_rules")
    op.drop_index("ix_escalation_rules_school", table_name="escalation_rules")
    op.drop_index("ix_escalation_rules_dept", table_name="escalation_rules")
    op.drop_table("escalation_rules")

    op.drop_index("ix_task_escalations_escalated_at", table_name="task_escalations")
    op.drop_index("ix_task_escalations_status", table_name="task_escalations")
    op.drop_index("ix_task_escalations_task", table_name="task_escalations")
    op.drop_table("task_escalations")

    op.drop_index("ix_eta_extensions_task", table_name="task_eta_extensions")
    op.drop_table("task_eta_extensions")

    op.drop_index("ix_task_completions_task", table_name="task_owner_completions")
    op.drop_table("task_owner_completions")

    op.drop_index("ix_task_owners_user", table_name="task_owners")
    op.drop_index("ix_task_owners_task", table_name="task_owners")
    op.drop_table("task_owners")

    op.drop_index("ix_tasks_entity", table_name="tasks")
    op.drop_index("ix_tasks_eta", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_department", table_name="tasks")
    op.drop_index("ix_tasks_school", table_name="tasks")
    op.drop_table("tasks")
