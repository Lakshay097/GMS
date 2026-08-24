"""Add field_permissions table for field-level access control

Revision ID: 20260820_field_level_permissions
Revises: kra_kpi_library_001
Create Date: 2026-08-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260820_field_level_permissions'
down_revision = 'kra_kpi_library_001'
branch_labels = None
depends_on = None


def upgrade():
    # Create field_permissions table
    op.create_table(
        'field_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('module', sa.String(100), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('is_allowed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint(
            "role IN ('superadmin', 'admin', 'checker', 'auditor', 'viewer')",
            name='valid_role'
        ),
        sa.UniqueConstraint('module', 'field_name', 'role', name='ix_field_permissions_module_field_role')
    )
    
    # Create indexes
    op.create_index('ix_field_permissions_module', 'field_permissions', ['module'])
    op.create_index('ix_field_permissions_role', 'field_permissions', ['role'])
    
    # Seed initial field permissions for kpi_library module
    # NOTE: Admin/Checker/Auditor/Viewer permissions are currently inert since PATCH /kpis/{id}
    # is SuperAdmin-only. These seed rows are reserved for a possible future Admin-facing KPI edit
    # endpoint with finer-grained field restrictions.
    # SuperAdmin: full access to all restricted fields
    op.execute("""
        INSERT INTO field_permissions (id, module, field_name, role, is_allowed, created_at)
        VALUES 
            (gen_random_uuid(), 'kpi_library', 'target_value', 'superadmin', true, NOW()),
            (gen_random_uuid(), 'kpi_library', 'comparator', 'superadmin', true, NOW()),
            (gen_random_uuid(), 'kpi_library', 'is_sensitive', 'superadmin', true, NOW()),
            (gen_random_uuid(), 'kpi_library', 'category_code', 'superadmin', true, NOW()),
            (gen_random_uuid(), 'kpi_library', 'amber_tolerance_band', 'superadmin', true, NOW())
    """)
    
    # Admin: restricted access (no target_value, comparator, is_sensitive)
    op.execute("""
        INSERT INTO field_permissions (id, module, field_name, role, is_allowed, created_at)
        VALUES 
            (gen_random_uuid(), 'kpi_library', 'target_value', 'admin', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'comparator', 'admin', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'is_sensitive', 'admin', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'category_code', 'admin', true, NOW()),
            (gen_random_uuid(), 'kpi_library', 'amber_tolerance_band', 'admin', true, NOW())
    """)
    
    # Checker: no access to restricted fields
    op.execute("""
        INSERT INTO field_permissions (id, module, field_name, role, is_allowed, created_at)
        VALUES 
            (gen_random_uuid(), 'kpi_library', 'target_value', 'checker', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'comparator', 'checker', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'is_sensitive', 'checker', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'category_code', 'checker', true, NOW()),
            (gen_random_uuid(), 'kpi_library', 'amber_tolerance_band', 'checker', true, NOW())
    """)
    
    # Auditor: no access to restricted fields
    op.execute("""
        INSERT INTO field_permissions (id, module, field_name, role, is_allowed, created_at)
        VALUES 
            (gen_random_uuid(), 'kpi_library', 'target_value', 'auditor', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'comparator', 'auditor', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'is_sensitive', 'auditor', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'category_code', 'auditor', true, NOW()),
            (gen_random_uuid(), 'kpi_library', 'amber_tolerance_band', 'auditor', true, NOW())
    """)
    
    # Viewer: no access to restricted fields
    op.execute("""
        INSERT INTO field_permissions (id, module, field_name, role, is_allowed, created_at)
        VALUES 
            (gen_random_uuid(), 'kpi_library', 'target_value', 'viewer', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'comparator', 'viewer', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'is_sensitive', 'viewer', false, NOW()),
            (gen_random_uuid(), 'kpi_library', 'category_code', 'viewer', true, NOW()),
            (gen_random_uuid(), 'kpi_library', 'amber_tolerance_band', 'viewer', true, NOW())
    """)


def downgrade():
    # Drop field_permissions table
    op.drop_index('ix_field_permissions_role', table_name='field_permissions')
    op.drop_index('ix_field_permissions_module', table_name='field_permissions')
    op.drop_table('field_permissions')
