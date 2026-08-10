"""Add discrepancy and discrepancy_approval_history tables for PRS §25-26."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260808_discrepancy_tables"
down_revision = "20260808_approval_chain_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create discrepancies table
    op.create_table(
        "discrepancies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("observations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discrepancy_categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("raised_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("investigation_owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("state", sa.String(50), nullable=False, server_default="raised"),
        sa.Column("investigation_findings", sa.Text(), nullable=True),
        sa.Column("bound_chain_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discrepancy_approval_chain_config.chain_version_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("raised_at", sa.DateTime(), nullable=False),
        sa.Column("under_investigation_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    
    op.create_index("ix_discrepancies_observation", "discrepancies", ["observation_id"])
    op.create_index("ix_discrepancies_category", "discrepancies", ["category_id"])
    op.create_index("ix_discrepancies_school", "discrepancies", ["school_id"])
    op.create_index("ix_discrepancies_state", "discrepancies", ["state"])
    op.create_index("ix_discrepancies_bound_chain", "discrepancies", ["bound_chain_version_id"])

    # Create discrepancy_approval_history table
    op.create_table(
        "discrepancy_approval_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("discrepancy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discrepancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("assigned_role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    
    op.create_index("ix_approval_history_discrepancy", "discrepancy_approval_history", ["discrepancy_id"])
    op.create_index("ix_approval_history_level", "discrepancy_approval_history", ["discrepancy_id", "level"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_approval_history_level", table_name="discrepancy_approval_history")
    op.drop_index("ix_approval_history_discrepancy", table_name="discrepancy_approval_history")
    op.drop_table("discrepancy_approval_history")
    
    op.drop_index("ix_discrepancies_bound_chain", table_name="discrepancies")
    op.drop_index("ix_discrepancies_state", table_name="discrepancies")
    op.drop_index("ix_discrepancies_school", table_name="discrepancies")
    op.drop_index("ix_discrepancies_category", table_name="discrepancies")
    op.drop_index("ix_discrepancies_observation", table_name="discrepancies")
    op.drop_table("discrepancies")
