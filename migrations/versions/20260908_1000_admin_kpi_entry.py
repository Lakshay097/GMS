"""Grant admin role permission to create observations (KPI entry)

Revision ID: 20260908_1000_admin_kpi_entry
Revises: 20260907_1000_user_lifecycle
Create Date: 2026-09-08

Changes:
  - permissions row (module='observation', action='create', role='admin'):
    is_allowed False → True

This allows admin users to submit KPI entries via the DailyKpiInput UI.
The change flows automatically through capabilities_for_roles(), which
derives the frontend kpiEntry capability flag from OBSERVATION.CREATE.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260908_1000_admin_kpi_entry'
down_revision = '20260907_1000_user_lifecycle'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE permissions
            SET is_allowed = TRUE
            WHERE module = 'observation'
              AND action  = 'create'
              AND role    = 'admin'
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text("""
            UPDATE permissions
            SET is_allowed = FALSE
            WHERE module = 'observation'
              AND action  = 'create'
              AND role    = 'admin'
        """)
    )
