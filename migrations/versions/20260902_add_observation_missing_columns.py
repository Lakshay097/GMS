"""Add missing ORM columns to observations table.

The Observation ORM model declares status, verified_at, verified_by,
rejected_at, rejected_by, rejection_reason, archive_tier, and
archive_status columns that were never created by any prior migration.
This is schema drift that was caught during runtime certification.

Idempotent: skips columns that already exist (the drift was partially
hand-applied on some environments).

Revision: 20260902_observation_schema_drift_fix
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260902_observation_schema_drift_fix"
down_revision = "20260831_kpi_entry_uniqueness"
branch_labels = None
depends_on = None

_NEW_COLUMNS = [
    ("status", sa.Column("status", sa.String(20), nullable=False, server_default="pending")),
    ("verified_at", sa.Column("verified_at", sa.DateTime(), nullable=True)),
    ("verified_by", sa.Column(
        "verified_by",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )),
    ("rejected_at", sa.Column("rejected_at", sa.DateTime(), nullable=True)),
    ("rejected_by", sa.Column(
        "rejected_by",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )),
    ("rejection_reason", sa.Column("rejection_reason", sa.Text(), nullable=True)),
    ("archive_tier", sa.Column("archive_tier", sa.String(50), nullable=True)),
    ("archive_status", sa.Column("archive_status", sa.String(50), nullable=True)),
]


def _existing_columns(table: str) -> set:
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    existing = _existing_columns("observations")
    for column_name, column in _NEW_COLUMNS:
        if column_name not in existing:
            op.add_column("observations", column)


def downgrade() -> None:
    existing = _existing_columns("observations")
    for column_name, _column in reversed(_NEW_COLUMNS):
        if column_name in existing:
            op.drop_column("observations", column_name)
