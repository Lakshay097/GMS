"""Approval chain v2.0: named chains, scope filtering, priority-based matching, person assignment.

Changes:
- Add name, description, priority columns
- Add school_id, department_id, category_id scope filters
- Add indexes for priority-based queries
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260824_approval_chain_v2"
down_revision = "20260821_department_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to approval chain config
    op.add_column(
        "discrepancy_approval_chain_config",
        sa.Column("name", sa.String(255), nullable=False, server_default="Default Chain"),
    )
    op.add_column(
        "discrepancy_approval_chain_config",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "discrepancy_approval_chain_config",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "discrepancy_approval_chain_config",
        sa.Column("school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "discrepancy_approval_chain_config",
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "discrepancy_approval_chain_config",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discrepancy_categories.id", ondelete="SET NULL"), nullable=True),
    )

    # Add index for priority-based queries
    op.create_index("ix_approval_chain_priority", "discrepancy_approval_chain_config", ["priority"])


def downgrade() -> None:
    op.drop_index("ix_approval_chain_priority", table_name="discrepancy_approval_chain_config")
    op.drop_column("discrepancy_approval_chain_config", "category_id")
    op.drop_column("discrepancy_approval_chain_config", "department_id")
    op.drop_column("discrepancy_approval_chain_config", "school_id")
    op.drop_column("discrepancy_approval_chain_config", "priority")
    op.drop_column("discrepancy_approval_chain_config", "description")
    op.drop_column("discrepancy_approval_chain_config", "name")
