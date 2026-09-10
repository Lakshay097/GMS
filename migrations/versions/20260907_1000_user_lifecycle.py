"""Extend self-managed auth: user profile fields, statuses, verifier role,
invitation codes, email verification tokens

Revision ID: 20260907_1000_user_lifecycle
Revises: 20260906_1100_notification_read_at
Create Date: 2026-09-07

Adds:
  - users.manager_id (FK users.id), designation, location, last_login_at,
    email_verified — profile/lifecycle columns for the user-management spec.
  - users.status: PENDING / SUSPENDED / INACTIVE values (existing 'active' and
    'archived' are preserved; the column is VARCHAR, so no type change needed).
  - 'verifier' role support (roles is JSONB — no schema change, but the
    field_permissions CHECK constraint and permission seeding are updated).
  - invitation_codes table: hashed codes with department/role binding,
    expiration, max uses, revocation, and consumption tracking.
  - email_verification_tokens table: single-use hashed tokens for account
    activation/verification (structure mirrors password_reset_tokens).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = '20260907_1000_user_lifecycle'
down_revision = '20260906_1100_notification_read_at'
branch_labels = None
depends_on = None


def _columns(inspector, table):
    return {c['name'] for c in inspector.get_columns(table)}


def _tables(inspector):
    from sqlalchemy import inspect as _inspect
    return set(_inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # ── users: profile + lifecycle columns ─────────────────────────────────
    cols = _columns(inspector, 'users')
    if 'manager_id' not in cols:
        op.add_column('users', sa.Column(
            'manager_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ))
        op.create_index('ix_users_manager_id', 'users', ['manager_id'])
    if 'designation' not in cols:
        op.add_column('users', sa.Column('designation', sa.String(120), nullable=True))
    if 'location' not in cols:
        op.add_column('users', sa.Column('location', sa.String(120), nullable=True))
    if 'last_login_at' not in cols:
        op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
        op.create_index('ix_users_last_login_at', 'users', ['last_login_at'])
    if 'email_verified' not in cols:
        op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # Role constraint on field_permissions: add 'verifier'
    fks = inspector.get_check_constraints('field_permissions')
    if not any('verifier' in (c.get('sqltext') or c.get('sql') or '') for c in fks):
        # Drop and recreate the role CHECK with the verifier value included.
        op.drop_constraint('valid_role', 'field_permissions', type_='check')
        op.create_check_constraint(
            'valid_role',
            'field_permissions',
            "role IN ('superadmin', 'admin', 'dept_head', 'checker', 'auditor', 'viewer', 'verifier')",
        )

    # ── invitation_codes ───────────────────────────────────────────────────
    if 'invitation_codes' not in _tables(inspector):
        op.create_table(
            'invitation_codes',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('code_hash', sa.String(64), nullable=False),
            sa.Column('code_prefix', sa.String(8), nullable=False),  # display prefix (first segment) — no full code
            sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('school_id', UUID(as_uuid=True), sa.ForeignKey('schools.id', ondelete='CASCADE'), nullable=True),
            sa.Column('department_id', UUID(as_uuid=True), sa.ForeignKey('departments.id', ondelete='CASCADE'), nullable=True),
            sa.Column('role', sa.String(50), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('max_uses', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('used_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('status', sa.String(20), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_invitation_codes_code_hash', 'invitation_codes', ['code_hash'], unique=True)
        op.create_index('ix_invitation_codes_department_id', 'invitation_codes', ['department_id'])
        op.create_index('ix_invitation_codes_status', 'invitation_codes', ['status'])
        op.create_index('ix_invitation_codes_created_by', 'invitation_codes', ['created_by'])

    # ── invitation_uses: which user consumed which code ────────────────────
    if 'invitation_uses' not in _tables(inspector):
        op.create_table(
            'invitation_uses',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('invitation_id', UUID(as_uuid=True), sa.ForeignKey('invitation_codes.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('used_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_invitation_uses_invitation_id', 'invitation_uses', ['invitation_id'])
        op.create_index('ix_invitation_uses_user_id', 'invitation_uses', ['user_id'])

    # ── email_verification_tokens ──────────────────────────────────────────
    if 'email_verification_tokens' not in _tables(inspector):
        op.create_table(
            'email_verification_tokens',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('token_hash', sa.String(64), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_email_verification_tokens_token_hash', 'email_verification_tokens', ['token_hash'], unique=True)
        op.create_index('ix_email_verification_tokens_user_id', 'email_verification_tokens', ['user_id'])
        op.create_index('ix_email_verification_tokens_expires_at', 'email_verification_tokens', ['expires_at'])


def downgrade() -> None:
    op.drop_table('email_verification_tokens')
    op.drop_table('invitation_uses')
    op.drop_table('invitation_codes')

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = _columns(inspector, 'users')
    if 'email_verified' in cols:
        op.drop_column('users', 'email_verified')
    if 'last_login_at' in cols:
        op.drop_index('ix_users_last_login_at', table_name='users')
        op.drop_column('users', 'last_login_at')
    if 'location' in cols:
        op.drop_column('users', 'location')
    if 'designation' in cols:
        op.drop_column('users', 'designation')
    if 'manager_id' in cols:
        op.drop_index('ix_users_manager_id', table_name='users')
        op.drop_column('users', 'manager_id')

    # Restore original role CHECK without 'verifier'
    op.drop_constraint('valid_role', 'field_permissions', type_='check')
    op.create_check_constraint(
        'valid_role',
        'field_permissions',
        "role IN ('superadmin', 'admin', 'dept_head', 'checker', 'auditor', 'viewer')",
    )
