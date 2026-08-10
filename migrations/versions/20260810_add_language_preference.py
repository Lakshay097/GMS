"""Add language_preference column to users table for FR-163.

Revision ID: 20260810_add_language_preference
Revises: 20260808_task_management
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260810_add_language_preference"
down_revision = "20260808_task_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add language_preference column to users table
    op.add_column(
        "users",
        sa.Column("language_preference", sa.String(10), nullable=False, server_default="en")
    )


def downgrade() -> None:
    # Remove language_preference column from users table
    op.drop_column("users", "language_preference")
