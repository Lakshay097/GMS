"""Add kpiformulatype enum and convert formula_type column."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260814_add_kpi_formula_type_enum"
down_revision = "kra_kpi_library_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the enum type
    kpiformulatype_enum = postgresql.ENUM(
        "threshold_comparison",
        name="kpiformulatype",
        create_type=True
    )
    kpiformulatype_enum.create(op.get_bind())
    
    # Convert existing data to ensure it matches the enum value
    op.execute("""
        UPDATE kpis 
        SET formula_type = 'threshold_comparison' 
        WHERE formula_type IS NULL OR formula_type NOT IN ('threshold_comparison')
    """)
    
    # Drop the default first (it's a string, can't cast to enum automatically)
    op.execute("ALTER TABLE kpis ALTER COLUMN formula_type DROP DEFAULT")
    
    # Alter the column to use the enum type with explicit cast
    op.execute("""
        ALTER TABLE kpis 
        ALTER COLUMN formula_type TYPE kpiformulatype 
        USING formula_type::kpiformulatype
    """)
    
    # Set the default using the enum value
    op.execute("ALTER TABLE kpis ALTER COLUMN formula_type SET DEFAULT 'threshold_comparison'::kpiformulatype")


def downgrade() -> None:
    # Revert to VARCHAR
    op.alter_column(
        "kpis",
        "formula_type",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(name="kpiformulatype"),
        server_default="threshold_comparison",
        nullable=False
    )
    
    # Drop the enum type
    kpiformulatype_enum = postgresql.ENUM(name="kpiformulatype")
    kpiformulatype_enum.drop(op.get_bind())
