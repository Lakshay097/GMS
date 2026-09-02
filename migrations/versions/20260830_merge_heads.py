"""Merge heads: approval_history_role + feature_flags/locations/KPI schema chain.

Revision ID: 20260830_merge_heads
Revises: 20260824_approval_history_role, 20260829_add_feature_flags_table
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "20260830_merge_heads"
down_revision = ("20260824_approval_history_role", "20260830_kra_kpi_schema_v2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op merge — just joins the two branches
    pass


def downgrade() -> None:
    pass
