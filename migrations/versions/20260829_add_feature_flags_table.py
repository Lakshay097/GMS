"""
Add feature_flags table for phased rollout toggle management.

SuperAdmin can toggle feature flags via the Settings UI to enable/disable
features without code deployment (PRS §56).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20260829_add_feature_flags_table'
down_revision = '20260824_merge_heads'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'feature_flags',
        sa.Column('flag_key', sa.String(100), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )

    # Seed the known feature flags
    op.execute("""
        INSERT INTO feature_flags (flag_key, enabled, description) VALUES
        ('mfa_enabled', false, 'Enable Multi-Factor Authentication setup for Admin/SuperAdmin roles'),
        ('sso_enabled', false, 'Enable Single Sign-On (SSO/OAuth) login provider'),
        ('observation_reopen_enabled', false, 'Allow Checkers to request reopening of closed-missed observations'),
        ('saved_filters_enabled', false, 'Allow users to save and manage custom report filters')
        ON CONFLICT (flag_key) DO NOTHING;
    """)


def downgrade():
    op.drop_table('feature_flags')
