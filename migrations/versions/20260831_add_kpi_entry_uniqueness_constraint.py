"""Add unique constraint and indexes for KPI entry uniqueness.

Adds a partial unique index on observations to prevent duplicate submissions
for the same KPI, checker, and day.  Also adds indexes for common query
patterns (submissions-by-date, audit history lookup).

Revision ID: 20260831_kpi_entry_uniqueness
"""

from alembic import op
import sqlalchemy as sa

revision = "20260831_kpi_entry_uniqueness"
down_revision = "20260831_merge_heads_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Unique partial index: at most one observation per (kpi_id, checker_id) per
    # calendar day.  Uses date(submitted_at) so the constraint is enforced at
    # the database level regardless of frontend state.
    #
    # NOTE: PostgreSQL supports partial unique indexes; the WHERE clause filters
    # out any rows with NULL submitted_at (which should not exist in practice).
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_observation_kpi_checker_date
        ON observations (kpi_id, checker_id, (submitted_at::date))
        WHERE submitted_at IS NOT NULL
        """
    )

    # Index for the submissions-by-date endpoint (checker_id + submitted_at)
    op.create_index(
        "ix_observations_checker_submitted",
        "observations",
        ["checker_id", "submitted_at"],
    )

    # Index for audit history lookups
    op.create_index(
        "ix_observations_captured_at",
        "observations",
        ["captured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_observations_captured_at", table_name="observations")
    op.drop_index("ix_observations_checker_submitted", table_name="observations")
    op.execute("DROP INDEX IF EXISTS uq_observation_kpi_checker_date")
