"""
Add locations table for floor/zone/wing scoping per PRS §37.10, FR-189.

Locations are per-school reference entities used to scope Event-Time
observations and assets to specific physical areas.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260829_add_locations_table'
down_revision = '20260829_add_feature_flags_table'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('location_type', sa.String(50), nullable=False, server_default='floor'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )

    op.create_index('ix_locations_school', 'locations', ['school_id'])
    op.create_unique_constraint('uq_location_school_name_type', 'locations', ['school_id', 'name', 'location_type'])


def downgrade():
    op.drop_constraint('uq_location_school_name_type', 'locations', type_='unique')
    op.drop_index('ix_locations_school', table_name='locations')
    op.drop_table('locations')
