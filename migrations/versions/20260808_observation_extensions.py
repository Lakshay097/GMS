"""Observation table extensions for PRS §24 implementation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "observation_extensions_001"
down_revision = "20260808_approval_chain_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add lock period tracking
    op.add_column(
        "observations",
        sa.Column("locked_at", sa.DateTime(), nullable=True),
    )

    # Add evidence storage (JSONB array of evidence metadata)
    op.add_column(
        "observations",
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
    )

    # Add duplicate detection tracking
    op.add_column(
        "observations",
        sa.Column("is_duplicate_override", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "observations",
        sa.Column("duplicate_override_justification", sa.Text(), nullable=True),
    )
    op.add_column(
        "observations",
        sa.Column("duplicate_override_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "observations",
        sa.Column("original_observation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Add grace period & reopen tracking
    op.add_column(
        "observations",
        sa.Column("is_reopened", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "observations",
        sa.Column("reopen_requested_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "observations",
        sa.Column("reopen_requested_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "observations",
        sa.Column("reopen_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "observations",
        sa.Column("reopen_approved_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "observations",
        sa.Column("reopen_approved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Add indexes for duplicate detection
    op.create_index(
        "ix_observations_duplicate_check",
        "observations",
        ["kpi_id", "kpi_version", "checker_id", "department_id", "asset_id", "location_id", "submitted_at"],
    )

    # Add index for lock period queries
    op.create_index(
        "ix_observations_locked_at",
        "observations",
        ["locked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_observations_locked_at", table_name="observations")
    op.drop_index("ix_observations_duplicate_check", table_name="observations")

    op.drop_column("observations", "reopen_approved_by")
    op.drop_column("observations", "reopen_approved_at")
    op.drop_column("observations", "reopen_reason")
    op.drop_column("observations", "reopen_requested_by")
    op.drop_column("observations", "reopen_requested_at")
    op.drop_column("observations", "is_reopened")

    op.drop_column("observations", "original_observation_id")
    op.drop_column("observations", "duplicate_override_by")
    op.drop_column("observations", "duplicate_override_justification")
    op.drop_column("observations", "is_duplicate_override")

    op.drop_column("observations", "evidence")
    op.drop_column("observations", "locked_at")
