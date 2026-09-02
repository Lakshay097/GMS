"""Add missing ORM columns to observations table.

The Observation ORM model declares status, verified_at, verified_by,
rejected_at, rejected_by, rejection_reason, archive_tier, and
archive_status columns that were never created by any prior migration.
This is schema drift that was caught during runtime certification.

Revision: 20260902_observation_schema_drift_fix
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260902_observation_schema_drift_fix"
down_revision = "20260831_kpi_entry_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # status column (pending / verified / rejected) with default
    op.add_column(
        "observations",
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )

    # Verification / rejection tracking
    op.add_column("observations", sa.Column("verified_at", sa.DateTime(), nullable=True))
    op.add_column(
        "observations",
        sa.Column(
            "verified_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("observations", sa.Column("rejected_at", sa.DateTime(), nullable=True))
    op.add_column(
        "observations",
        sa.Column(
            "rejected_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("observations", sa.Column("rejection_reason", sa.Text(), nullable=True))

    # Archive tier tracking (Phase 2)
    op.add_column("observations", sa.Column("archive_tier", sa.String(50), nullable=True))
    op.add_column("observations", sa.Column("archive_status", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("observations", "archive_status")
    op.drop_column("observations", "archive_tier")
    op.drop_column("observations", "rejection_reason")
    op.drop_column("observations", "rejected_by")
    op.drop_column("observations", "rejected_at")
    op.drop_column("observations", "verified_by")
    op.drop_column("observations", "verified_at")
    op.drop_column("observations", "status")
