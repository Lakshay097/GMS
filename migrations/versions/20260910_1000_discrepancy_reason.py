"""Add reason column to discrepancies table

Revision ID: 20260910_1000_discrepancy_reason
Revises: 20260908_1200_users_performance_indexes
Create Date: 2026-09-10

Changes:
  - discrepancies.reason (TEXT, nullable) — stores the verifier's stated
    reason for raising a discrepancy at the time of creation.
    Previously the frontend sent this field but the backend had no column
    to persist it; the value was silently dropped by Pydantic.
"""
from alembic import op
import sqlalchemy as sa


revision = '20260910_1000_discrepancy_reason'
down_revision = '20260908_1200_users_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'discrepancies',
        sa.Column('reason', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('discrepancies', 'reason')
