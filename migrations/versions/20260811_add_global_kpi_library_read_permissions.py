"""Add READ permissions for GLOBAL_KPI_LIBRARY

The GET /kras route requires READ permission for GLOBAL_KPI_LIBRARY,
but the permission matrix only had MANAGE entries. This migration adds
READ permissions for all roles (as defined in the permission matrix)
to allow all users to read the global KPI library as reference data.

Revision ID: 20260811_add_global_kpi_read
Revises: 20260808_approval_chain_config
Create Date: 2026-08-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime
import uuid

# revision identifiers, used by Alembic.
revision = '20260811_add_global_kpi_read'
down_revision = 'observation_extensions_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add READ permissions for GLOBAL_KPI_LIBRARY for all roles
    # Based on the permission matrix in shared/permissions.py lines 107-111
    permissions_data = [
        {
            'id': str(uuid.uuid4()),
            'module': 'global_kpi_library',
            'action': 'read',
            'role': 'superadmin',
            'scope_constraint': 'global',
            'is_allowed': True,
            'created_at': datetime.utcnow()
        },
        {
            'id': str(uuid.uuid4()),
            'module': 'global_kpi_library',
            'action': 'read',
            'role': 'admin',
            'scope_constraint': 'school',
            'is_allowed': True,
            'created_at': datetime.utcnow()
        },
        {
            'id': str(uuid.uuid4()),
            'module': 'global_kpi_library',
            'action': 'read',
            'role': 'checker',
            'scope_constraint': 'school',
            'is_allowed': True,
            'created_at': datetime.utcnow()
        },
        {
            'id': str(uuid.uuid4()),
            'module': 'global_kpi_library',
            'action': 'read',
            'role': 'auditor',
            'scope_constraint': 'school',
            'is_allowed': True,
            'created_at': datetime.utcnow()
        },
        {
            'id': str(uuid.uuid4()),
            'module': 'global_kpi_library',
            'action': 'read',
            'role': 'viewer',
            'scope_constraint': 'granted',
            'is_allowed': True,
            'created_at': datetime.utcnow()
        },
    ]
    
    # Insert permissions only if they don't already exist (idempotent)
    for perm in permissions_data:
        op.execute(
            sa.text("""
                INSERT INTO permissions (id, module, action, role, scope_constraint, is_allowed, created_at)
                VALUES (:id, :module, :action, :role, :scope_constraint, :is_allowed, :created_at)
                ON CONFLICT (module, action, role) DO NOTHING
            """).bindparams(
                id=perm['id'],
                module=perm['module'],
                action=perm['action'],
                role=perm['role'],
                scope_constraint=perm['scope_constraint'],
                is_allowed=perm['is_allowed'],
                created_at=perm['created_at']
            )
        )


def downgrade() -> None:
    # Remove the READ permissions for GLOBAL_KPI_LIBRARY
    op.execute(
        sa.text("""
            DELETE FROM permissions 
            WHERE module = 'global_kpi_library' 
            AND action = 'read'
        """)
    )
