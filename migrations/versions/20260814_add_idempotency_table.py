"""
Add idempotency table for PostgreSQL-based idempotency.

This migration creates a table to store idempotency keys and their responses,
enabling safe retry of mutation endpoints without creating duplicate records.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260814_add_idempotency_table'
down_revision = '20260814_add_kpi_formula_type_enum'
branch_labels = None
depends_on = None


def upgrade():
    # Create idempotency_keys table
    op.create_table(
        'idempotency_keys',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('key', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('request_params_hash', sa.String(64), nullable=True),
        sa.Column('response_data', postgresql.JSONB(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    
    # Create index for expiration cleanup
    op.create_index('ix_idempotency_keys_expires_at', 'idempotency_keys', ['expires_at'])
    
    # Create index for user-specific queries
    op.create_index('ix_idempotency_keys_user_id', 'idempotency_keys', ['user_id'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_idempotency_keys_user_id', table_name='idempotency_keys')
    op.drop_index('ix_idempotency_keys_expires_at', table_name='idempotency_keys')
    
    # Drop table
    op.drop_table('idempotency_keys')
