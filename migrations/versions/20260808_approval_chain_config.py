"""Add discrepancy approval chain configuration table for BR-21."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260808_approval_chain_config"
down_revision = "p001_string_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discrepancy_approval_chain_config",
        sa.Column("chain_version_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("levels", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    
    op.create_index("ix_approval_chain_active", "discrepancy_approval_chain_config", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_approval_chain_active", table_name="discrepancy_approval_chain_config")
    op.drop_table("discrepancy_approval_chain_config")
