"""Migrate from Neon Auth to Clerk

Revision ID: 20260817_1500_clerk_migration
Revises: 20260814_add_kpi_formula_type_enum
Create Date: 2026-08-17 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260817_1500_clerk_migration'
down_revision = '20260814_add_kpi_formula_type_enum'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column exists before renaming (in case it's already been renamed)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]

    if 'neon_auth_user_id' in columns:
        # Rename neon_auth_user_id to clerk_user_id
        op.alter_column('users', 'neon_auth_user_id', new_column_name='clerk_user_id')


def downgrade() -> None:
    # Revert clerk_user_id back to neon_auth_user_id
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]

    if 'clerk_user_id' in columns:
        op.alter_column('users', 'clerk_user_id', new_column_name='neon_auth_user_id')
