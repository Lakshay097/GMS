"""Self-managed authentication: sessions, password reset tokens, password_hash

Revision ID: 20260906_1000_self_managed_auth
Revises: 20260902_add_observation_missing_columns
Create Date: 2026-09-06

Removes Clerk dependency from the schema:
  - users.clerk_user_id (UNIQUE, NOT NULL) is DROPPED.
  - users.password_hash added (Argon2id).
  - users.failed_login_count / locked_until for brute-force lockout.
  - New auth_sessions table: one row per login, stores sha256(token) — never the raw token.
  - New password_reset_tokens table for self-service password recovery.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '20260906_1000_self_managed_auth'
down_revision = '20260902_observation_schema_drift_fix'
branch_labels = None
depends_on = None


def _index_exists(inspector, index_name: str, table_name: str) -> bool:
    names = {i['name'] for i in inspector.get_indexes(table_name)}
    return index_name in names


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {c['name'] for c in inspector.get_columns('users')}

    # ── users: drop Clerk link, add self-managed credential columns ────────
    if 'clerk_user_id' in columns:
        if _index_exists(inspector, 'ix_users_clerk_user_id', 'users'):
            op.drop_index('ix_users_clerk_user_id', table_name='users')
        op.drop_column('users', 'clerk_user_id')

    if 'password_hash' not in columns:
        op.add_column('users', sa.Column('password_hash', sa.String(255), nullable=True))

    if 'failed_login_count' not in columns:
        op.add_column('users', sa.Column('failed_login_count', sa.Integer(), nullable=False, server_default='0'))

    if 'locked_until' not in columns:
        op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))

    # ── auth_sessions ──────────────────────────────────────────────────────
    op.create_table(
        'auth_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('absolute_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
    )
    op.create_index('ix_auth_sessions_token_hash', 'auth_sessions', ['token_hash'], unique=True)
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'])

    # ── password_reset_tokens ──────────────────────────────────────────────
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'])
    op.create_index('ix_password_reset_tokens_expires_at', 'password_reset_tokens', ['expires_at'])


def downgrade() -> None:
    op.drop_table('password_reset_tokens')
    op.drop_table('auth_sessions')

    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}
    if 'locked_until' in columns:
        op.drop_column('users', 'locked_until')
    if 'failed_login_count' in columns:
        op.drop_column('users', 'failed_login_count')
    if 'password_hash' in columns:
        op.drop_column('users', 'password_hash')
    if 'clerk_user_id' not in columns:
        op.add_column('users', sa.Column('clerk_user_id', sa.String(255), unique=True, nullable=False, server_default='legacy'))
