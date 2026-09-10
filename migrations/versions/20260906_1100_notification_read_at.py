"""Add notifications.read_at for the in-app notification center

Revision ID: 20260906_1100_notification_read_at
Revises: 20260906_1000_self_managed_auth
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa


revision = '20260906_1100_notification_read_at'
down_revision = '20260906_1000_self_managed_auth'
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('notifications')}
    if 'read_at' not in columns:
        op.add_column('notifications', sa.Column('read_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('notifications')}
    if 'read_at' in columns:
        op.drop_column('notifications', 'read_at')
