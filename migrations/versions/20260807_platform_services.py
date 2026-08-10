"""Add platform service tables and scheduler schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "platform_services_001"
down_revision = "4e2ed61991ff"
branch_labels = None
depends_on = None


def _rename_if_legacy(table: str, legacy_column: str, archive_name: str) -> None:
    """
    Neon may still hold Prisma-era tables that collide on name but not shape.
    Archive them so Phase 1 schema can be created cleanly.
    """
    bind = op.get_bind()
    exists = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :t"
        ),
        {"t": table},
    ).scalar()
    if not exists:
        return
    has_legacy_col = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": legacy_column},
    ).scalar()
    if has_legacy_col:
        op.rename_table(table, archive_name)


def upgrade() -> None:
    # Prisma leftovers collide with Phase 1 table names (different shapes).
    _rename_if_legacy("kras", "categoryId", "kras_legacy_prisma")
    _rename_if_legacy("notifications", "userId", "notifications_legacy_prisma")

    op.add_column("schools", sa.Column("timezone", sa.String(100), nullable=True))
    op.add_column(
        "schools",
        sa.Column(
            "working_days",
            postgresql.JSONB(),
            server_default='["mon","tue","wed","thu","fri","sat"]',
        ),
    )

    op.create_table(
        "configuration_items",
        sa.Column("config_key", sa.String(100), primary_key=True),
        sa.Column("value_type", sa.String(50), nullable=False),
        sa.Column("global_default", sa.Text(), nullable=False),
        sa.Column("editable_by", sa.String(50), nullable=False),
        sa.Column("overridable_scope", sa.String(50), nullable=False, server_default="none"),
    )

    op.create_table(
        "configuration_overrides",
        sa.Column("config_key", sa.String(100), sa.ForeignKey("configuration_items.config_key"), primary_key=True),
        sa.Column("scope_type", sa.String(50), primary_key=True),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "master_data_entries",
        sa.Column("code", sa.String(100), primary_key=True),
        sa.Column("category", sa.String(100), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "discrepancy_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("allow_delegate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "organization_holiday_calendar",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("recurrence_type", sa.String(50), nullable=False, server_default="one_time"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category_code", sa.String(100), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("category", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "workflow_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(100), unique=True, nullable=False),
        sa.Column("initial_state", sa.String(100), nullable=False),
        sa.Column("transitions", postgresql.JSONB(), nullable=False),
        sa.Column("approval_chain_config", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "kras",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "kpis",
        sa.Column("kpi_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("kra_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kras.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("target_value", sa.Numeric(), nullable=False),
        sa.Column("comparator", sa.String(10), nullable=False),
        sa.Column("unit_of_measure", sa.String(50), nullable=False),
        sa.Column("frequency_code", sa.String(50), nullable=False),
        sa.Column("amber_tolerance_band", sa.Numeric(), nullable=True),
        sa.Column("working_days", postgresql.JSONB(), nullable=True),
        sa.Column("non_working_day_policy", sa.String(50), nullable=False, server_default="skip"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "compliance_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kpi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kpi_version", sa.Integer(), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("compliance_status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("grace_period_elapsed_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "kpi_id", "kpi_version", "department_id", "location_id", "asset_id", "due_at",
            name="uq_compliance_observation_generation_key",
        ),
    )

    op.create_table(
        "checklist_templates",
        sa.Column("template_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("frequency_code", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "checklist_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="generated"),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "template_id", "template_version", "school_id", "department_id", "period_start",
            name="uq_checklist_instance_generation_key",
        ),
    )

    op.create_table(
        "compliance_scheduler_run_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("records_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_backfilled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("school_timezone_batch", sa.String(100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("compliance_scheduler_run_log")
    op.drop_table("checklist_instances")
    op.drop_table("checklist_templates")
    op.drop_table("compliance_observations")
    op.drop_table("kpis")
    op.drop_table("kras")
    op.drop_table("workflow_definitions")
    op.drop_table("notifications")
    op.drop_table("assets")
    op.drop_table("organization_holiday_calendar")
    op.drop_table("discrepancy_categories")
    op.drop_table("master_data_entries")
    op.drop_table("configuration_overrides")
    op.drop_table("configuration_items")
    op.drop_column("schools", "working_days")
    op.drop_column("schools", "timezone")
