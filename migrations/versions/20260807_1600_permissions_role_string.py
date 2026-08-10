"""Change permissions.role from userrole enum to String(50)

The Permission model stores the lowercase UserRole value (e.g. "superadmin")
as a plain string. This migration converts the `permissions.role` column from
the PostgreSQL `userrole` enum type to a VARCHAR(50) column, keeping the
stored lowercase values (which already match the enum members).

Revision ID: p001_string_role
Revises: kra_kpi_library_001
Create Date: 2026-08-07 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'p001_string_role'
down_revision = 'kra_kpi_library_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the unique index that includes the role column (it references the enum)
    op.drop_index(op.f('ix_permissions_module_action_role'), table_name='permissions')
    op.drop_index(op.f('ix_permissions_role'), table_name='permissions')

    # Convert the role column from the userrole enum to VARCHAR(50)
    # The existing lowercase values ("superadmin", "admin", ...) carry over cleanly.
    op.alter_column(
        'permissions',
        'role',
        existing_type=postgresql.ENUM('superadmin', 'admin', 'checker', 'auditor', 'viewer', name='userrole'),
        type_=sa.String(50),
        existing_nullable=False,
        postgresql_using='role::text',
    )

    # Recreate the indexes
    op.create_index(op.f('ix_permissions_module_action_role'), 'permissions', ['module', 'action', 'role'], unique=True)
    op.create_index(op.f('ix_permissions_role'), 'permissions', ['role'])


def downgrade() -> None:
    # Recreate the enum type
    user_role_enum = postgresql.ENUM('superadmin', 'admin', 'checker', 'auditor', 'viewer', name='userrole', create_type=False)
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # Drop the indexes
    op.drop_index(op.f('ix_permissions_module_action_role'), table_name='permissions')
    op.drop_index(op.f('ix_permissions_role'), table_name='permissions')

    # Convert the role column back to the userrole enum
    op.alter_column(
        'permissions',
        'role',
        existing_type=sa.String(50),
        type_=user_role_enum,
        existing_nullable=False,
        postgresql_using='role::userrole',
    )

    # Recreate the indexes
    op.create_index(op.f('ix_permissions_module_action_role'), 'permissions', ['module', 'action', 'role'], unique=True)
    op.create_index(op.f('ix_permissions_role'), 'permissions', ['role'])
