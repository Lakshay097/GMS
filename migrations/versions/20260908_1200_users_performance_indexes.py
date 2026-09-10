"""Add performance indexes on users table

Revision ID: 20260908_1200_users_performance_indexes
Revises: 20260908_1100_superadmin_kpi_entry
Create Date: 2026-09-08

Changes:
  - GIN index on users.roles (JSONB) — replaces CAST(...) LIKE full-table scan
    for role-based filtering with an index-supported containment query (@>).
  - Composite index (school_id, status) — covers the most common list_users
    query pattern (Admin listing active users in their school).
  - Composite index (school_id, full_name) — covers ORDER BY full_name for
    school-scoped listing without a sort on the full table.
"""
from alembic import op


revision = '20260908_1200_users_performance_indexes'
down_revision = '20260908_1100_superadmin_kpi_entry'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GIN index on users.roles JSONB — enables @> containment queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_roles_gin "
        "ON users USING gin(roles)"
    )
    # Composite covering index for the common admin list pattern
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_school_status "
        "ON users (school_id, status)"
    )
    # Composite covering index for sorted listing within a school
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_school_fullname "
        "ON users (school_id, full_name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_roles_gin")
    op.execute("DROP INDEX IF EXISTS ix_users_school_status")
    op.execute("DROP INDEX IF EXISTS ix_users_school_fullname")
