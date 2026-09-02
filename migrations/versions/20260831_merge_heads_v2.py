"""Merge heads after adding observation check fields and audit table."""

from alembic import op

revision = "20260831_merge_heads_v2"
down_revision = ("20260830_kra_kpi_full_reset_v3", "20260831_add_observation_check_audit")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
