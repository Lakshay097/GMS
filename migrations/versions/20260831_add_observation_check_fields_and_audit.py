"""Add check/reason fields, captured_at, edit tracking to observations, and create observation_audit table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260831_add_observation_check_audit"
down_revision = "20260830_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to observations table
    op.add_column("observations", sa.Column("check_result", sa.String(10), nullable=True))
    op.add_column("observations", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("observations", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("observations", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("observations", sa.Column("edited_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("observations", sa.Column("edit_count", sa.Integer(), nullable=False, server_default="0"))

    # Create observation_audit table
    op.create_table(
        "observation_audit",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("observation_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("observations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("change_type", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("is_within_edit_window", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_observation_audit_observation", "observation_audit", ["observation_id"])
    op.create_index("ix_observation_audit_actor", "observation_audit", ["actor_id"])


def downgrade() -> None:
    op.drop_table("observation_audit")
    op.drop_column("observations", "edit_count")
    op.drop_column("observations", "edited_by")
    op.drop_column("observations", "edited_at")
    op.drop_column("observations", "captured_at")
    op.drop_column("observations", "reason")
    op.drop_column("observations", "check_result")
