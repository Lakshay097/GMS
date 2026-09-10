"""Grant superadmin role permission to create observations (KPI entry)

Revision ID: 20260908_1100_superadmin_kpi_entry
Revises: 20260908_1000_admin_kpi_entry
Create Date: 2026-09-08

Changes:
  - permissions row (module='observation', action='create', role='superadmin'):
    is_allowed False → True

Superadmin was previously excluded from KPI entry (observation capture was
considered a field-worker operation). This extends the admin grant to
superadmin so platform administrators can also submit KPI data directly.
"""
from alembic import op
import sqlalchemy as sa


revision = '20260908_1100_superadmin_kpi_entry'
down_revision = '20260908_1000_admin_kpi_entry'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE permissions
            SET is_allowed = TRUE
            WHERE module = 'observation'
              AND action  = 'create'
              AND role    = 'superadmin'
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE permissions
            SET is_allowed = FALSE
            WHERE module = 'observation'
              AND action  = 'create'
              AND role    = 'superadmin'
        """)
    )
