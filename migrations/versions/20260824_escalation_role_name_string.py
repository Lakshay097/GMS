"""Change escalation_rules.escalate_to_role_id from UUID to role name string.

Previously stored a UUID referencing a (non-existent) roles table.
Now stores the role name string directly (e.g., 'admin', 'checker').
"""

from alembic import op
import sqlalchemy as sa

revision = "20260824_escalation_role_name"
down_revision = "20260824_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old UUID column and recreate as string
    op.alter_column(
        "escalation_rules",
        "escalate_to_role_id",
        type_=sa.String(50),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "escalation_rules",
        "escalate_to_role_id",
        type_=sa.dialects.postgresql.UUID(as_uuid=True),
        existing_nullable=True,
    )
