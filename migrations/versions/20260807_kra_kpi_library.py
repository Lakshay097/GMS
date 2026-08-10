"""KRA/KPI schema extensions migration."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "kra_kpi_library_001"
down_revision = "platform_services_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kras", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "kras",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.add_column(
        "kpis",
        sa.Column("formula_type", sa.String(50), server_default="threshold_comparison", nullable=False),
    )
    op.add_column(
        "kpis",
        sa.Column("capture_type", sa.String(50), server_default="value_reading", nullable=False),
    )
    op.add_column("kpis", sa.Column("category_code", sa.String(100), nullable=True))
    op.add_column(
        "kpis",
        sa.Column("is_sensitive", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "kpis",
        sa.Column("evidence_required", sa.Boolean(), server_default="false", nullable=False),
    )

    op.create_table(
        "kpi_event_time_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kpi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kpi_version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("capture_mode_allowed", sa.String(50), nullable=False, server_default="manual_only"),
        sa.Column("target_time", sa.Time(), nullable=True),
        sa.ForeignKeyConstraint(["kpi_id", "kpi_version"], ["kpis.kpi_id", "kpis.version"]),
    )

    op.create_table(
        "department_kpi_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("kpi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("department_id", "kpi_id", name="uq_department_kpi_assignment"),
    )
    op.create_index("ix_department_kpi_kpi_id", "department_kpi_assignments", ["kpi_id"])

    op.create_table(
        "observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kpi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kpi_version", sa.Integer(), nullable=False),
        sa.Column("checker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("value_numeric", sa.Numeric(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("auto_result", sa.String(20), nullable=False),
        sa.Column("rag_status", sa.String(20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("is_late", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("submission_token", postgresql.UUID(as_uuid=True), unique=True, nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("event_times", postgresql.JSONB(), nullable=True),
        sa.Column("time_capture_mode", sa.String(50), nullable=True),
        sa.Column("manual_time_reason", sa.String(100), nullable=True),
    )
    op.create_index("ix_observations_kpi_id", "observations", ["kpi_id"])
    op.create_index("ix_observations_school_id", "observations", ["school_id"])


def downgrade() -> None:
    op.drop_index("ix_observations_school_id", table_name="observations")
    op.drop_index("ix_observations_kpi_id", table_name="observations")
    op.drop_table("observations")
    op.drop_index("ix_department_kpi_kpi_id", table_name="department_kpi_assignments")
    op.drop_table("department_kpi_assignments")
    op.drop_table("kpi_event_time_points")
    op.drop_column("kpis", "evidence_required")
    op.drop_column("kpis", "is_sensitive")
    op.drop_column("kpis", "category_code")
    op.drop_column("kpis", "capture_type")
    op.drop_column("kpis", "formula_type")
    op.drop_column("kras", "updated_at")
    op.drop_column("kras", "description")
