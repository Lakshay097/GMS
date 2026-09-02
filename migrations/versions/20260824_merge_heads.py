"""Merge all heads into a single head.

This resolves the fragmented migration chain so `alembic upgrade head` works.
"""

from alembic import op
import sqlalchemy as sa

# All heads that need to be merged
revision = "20260824_merge_heads"
down_revision = (
    "20260808_dashboards_reports_search",
    "20260810_add_language_preference",
    "20260811_add_global_kpi_read",
    "20260814_add_idempotency_table",
    "20260817_1500_clerk_migration",
    "20260820_field_level_permissions",
    "20260824_approval_chain_v2",
    "20260821_department_requests",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge only — no schema changes needed.
    # All individual migrations have already been applied.
    pass


def downgrade() -> None:
    # Cannot undo a merge — each head still exists independently.
    pass
