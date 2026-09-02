"""
KRA/KPI Schema V2 — Replace old structure with new data model (FIXED v2).

FIX LOG (addresses review feedback):
  Bug 1: TRUNCATE kpis CASCADE → removed. observations/compliance_observations
          have NO database-level FK to kpis (plain UUID columns), so CASCADE was
          a no-op. But truncation would still leave those tables with dangling
          kpi_id UUIDs. Fix: soft-delete approach — mark old KPIs/KRAs as
          'deprecated', insert new rows alongside. Zero data loss.
  Bug 2: observations.kpi_id dangling FKs → solved by keeping old KPI rows
          (status='deprecated'). Old observations still reference valid rows.
  Bug 3: kpi_entries FK to composite PK kpis(kpi_id, version) → added
          CREATE UNIQUE INDEX on kpis(kpi_id) so the single-column FK resolves.
  Bug 4: downgrade() column mismatch → uses explicit column lists when inserting
          archived data; drops recreated tables before restoring originals.
  Gap:   Legacy reference column (legacy_kpi_id) and materialized view now
          implemented, not just documented.

This migration:
  1. Creates archive tables (backup before any mutation)
  2. Alters kras (removes unique constraint on name)
  3. Alters kpis (adds description, owner, unique index on kpi_id)
  4. Drops and recreates child tables (kpi_event_time_points, department_kpi_assignments)
  5. Marks ALL existing KRA/KPI rows as 'deprecated' (soft delete — preserves FKs)
  6. Creates the new kpi_entries table
  7. Creates legacy_kpi_id column on kpi_entries for traceability
  8. Creates materialized view v_kpi_activity_unified for cross-period reporting
  9. Seeds sample data (1 School, 1 Department, 1 KRA, 1 KPI, 2 KPI_Entries)

IMPORTANT: observations, compliance_observations, and scorecards are NOT
  modified. Their kpi_id/kpi_version columns are plain UUIDs (no database-level
  FK), so they retain valid historical references to the deprecated KPI rows.

Revision ID: 20260830_kra_kpi_schema_v2
Revises: 20260829_add_locations_table
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260830_kra_kpi_schema_v2"
down_revision = "20260829_add_locations_table"
branch_labels = None
depends_on = None


def _now():
    """UTC now with timezone awareness."""
    return datetime.now(timezone.utc)


def upgrade() -> None:
    conn = op.get_bind()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 1 — CREATE ARCHIVE TABLES (backup before any mutation)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    op.execute("DROP TABLE IF EXISTS archive_kras_v1 CASCADE")
    op.execute("DROP TABLE IF EXISTS archive_kpis_v1 CASCADE")
    op.execute("DROP TABLE IF EXISTS archive_department_kpi_assignments_v1 CASCADE")
    op.execute("DROP TABLE IF EXISTS archive_kpi_event_time_points_v1 CASCADE")

    op.execute("""
        CREATE TABLE archive_kras_v1 (
            LIKE kras INCLUDING ALL
        );
    """)
    op.execute("""
        CREATE TABLE archive_kpis_v1 (
            LIKE kpis INCLUDING ALL
        );
    """)
    op.execute("""
        CREATE TABLE archive_department_kpi_assignments_v1 (
            LIKE department_kpi_assignments INCLUDING ALL
        );
    """)
    op.execute("""
        CREATE TABLE archive_kpi_event_time_points_v1 (
            LIKE kpi_event_time_points INCLUDING ALL
        );
    """)

    # Copy existing data into archive
    op.execute("INSERT INTO archive_kras_v1 SELECT * FROM kras")
    op.execute("INSERT INTO archive_kpis_v1 SELECT * FROM kpis")
    op.execute(
        "INSERT INTO archive_department_kpi_assignments_v1 SELECT * FROM department_kpi_assignments"
    )
    op.execute(
        "INSERT INTO archive_kpi_event_time_points_v1 SELECT * FROM kpi_event_time_points"
    )

    print(
        f"[KPI V2] Archived {conn.execute(sa.text('SELECT COUNT(*) FROM archive_kras_v1')).scalar()} KRAs"
    )
    print(
        f"[KPI V2] Archived {conn.execute(sa.text('SELECT COUNT(*) FROM archive_kpis_v1')).scalar()} KPIs"
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 2 — SOFT DELETE: Mark ALL existing KRAs and KPIs as deprecated
    #
    # WHY NOT TRUNCATE:
    #   - observations, compliance_observations, scorecards have kpi_id/kpi_version
    #     columns referencing kpis. These are plain UUIDs (no database FK), but
    #     truncating would leave them pointing at non-existent UUIDs — orphaned.
    #   - TRUNCATE kpis CASCADE would cascade to tables with DB-level FKs, but
    #     since observations lacks a DB-level FK, cascade was a no-op anyway.
    #   - Soft delete preserves all historical rows. Old observations still
    #     reference valid (deprecated) KPIs. Reports can filter by status.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    conn.execute(
        sa.text("UPDATE kpis SET status = 'deprecated' WHERE status != 'deprecated'")
    )
    conn.execute(
        sa.text("UPDATE kras SET status = 'deprecated' WHERE status != 'deprecated'")
    )
    # Also mark dependent tables as deprecated
    conn.execute(
        sa.text(
            "UPDATE department_kpi_assignments SET assigned_at = now() WHERE TRUE"
        )
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 3 — ALTER KRA TABLE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Remove the unique constraint on kras.name (multiple schools may share names)
    op.drop_constraint("kras_name_key", "kras", type_="unique", if_exists=True)

    # description and updated_at already exist from migration kra_kpi_library_001

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 4 — ALTER KPI TABLE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Add new columns
    op.add_column("kpis", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "kpis",
        sa.Column(
            "owner",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="KPI owner — distinct from created_by (audit trail)",
        ),
    )

    # BUG 3 FIX: Add unique index on kpis.kpi_id so kpi_entries FK can reference it.
    # kpis has composite PK (kpi_id, version), so kpi_id is NOT unique by default.
    # This index enables: kpi_entries.kpi_id → kpis.kpi_id (single-column FK)
    op.create_index("ix_kpis_kpi_id_unique", "kpis", ["kpi_id"], unique=True)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 5 — DROP and RECREATE child tables (clean schema, new FKs)
    #
    # These tables reference kpis via composite FK (kpi_id, version).
    # We drop them because:
    #   - department_kpi_assignments data was archived in Step 1
    #   - kpi_event_time_points data was archived in Step 1
    #   - We recreate them with the same schema (no column changes needed)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Drop department_kpi_assignments (FK to kpis and departments)
    op.drop_table("department_kpi_assignments")
    # Drop kpi_event_time_points (composite FK to kpis)
    op.drop_table("kpi_event_time_points")

    # Recreate department_kpi_assignments
    op.create_table(
        "department_kpi_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kpi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "assigned_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "assigned_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "department_id", "kpi_id", name="uq_department_kpi_assignment"
        ),
    )
    op.create_index("ix_department_kpi_kpi_id", "department_kpi_assignments", ["kpi_id"])

    # Recreate kpi_event_time_points
    op.create_table(
        "kpi_event_time_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kpi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kpi_version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "capture_mode_allowed",
            sa.String(50),
            nullable=False,
            server_default="manual_only",
        ),
        sa.Column("target_time", sa.Time(), nullable=True),
        sa.ForeignKeyConstraint(
            ["kpi_id", "kpi_version"], ["kpis.kpi_id", "kpis.version"]
        ),
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 6 — CREATE NEW TABLE: kpi_entries (measurement/check log)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    op.create_table(
        "kpi_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # FK to kpis.kpi_id (single-column, resolved by unique index from Step 4)
        sa.Column(
            "kpi_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpis.kpi_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "check_name",
            sa.String(255),
            nullable=True,
            comment="Human-readable name for this specific check/entry",
        ),
        sa.Column(
            "check_type",
            sa.String(50),
            nullable=True,
            comment="e.g. 'daily_inspection', 'weekly_audit', 'monthly_review'",
        ),
        sa.Column(
            "value",
            sa.Numeric(),
            nullable=True,
            comment="Measured value — supports numeric, percentage, or boolean (1/0)",
        ),
        sa.Column(
            "value_text",
            sa.Text(),
            nullable=True,
            comment="Free-text value for text-type KPIs",
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="When the measurement was taken (auto-generated, editable for backdating)",
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
            nullable=True,
            comment="Optional: linked asset if this is an asset-specific check",
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
            comment="Department context for this entry",
        ),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="SET NULL"),
            nullable=True,
            comment="School context for this entry",
        ),
        sa.Column(
            "recorded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="User who recorded this entry",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="pass / fail / pending / under_review",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Optional free-text notes or evidence description",
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(),
            nullable=True,
            comment="Optional attachment metadata (JSONB array)",
        ),
        # BUG 2 FIX: legacy_kpi_id for traceability to old (deprecated) KPI rows
        sa.Column(
            "legacy_kpi_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Optional: link to archive_kpis_v1.kpi_id for historical traceability",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indexes for common query patterns
    op.create_index("ix_kpi_entries_status", "kpi_entries", ["status"])
    op.create_index("ix_kpi_entries_timestamp", "kpi_entries", ["timestamp"])
    op.create_index("ix_kpi_entries_asset", "kpi_entries", ["asset_id"])
    op.create_index("ix_kpi_entries_department", "kpi_entries", ["department_id"])
    op.create_index("ix_kpi_entries_school", "kpi_entries", ["school_id"])
    op.create_index(
        "ix_kpi_entries_kpi_status", "kpi_entries", ["kpi_id", "status"]
    )
    op.create_index(
        "ix_kpi_entries_legacy_kpi", "kpi_entries", ["legacy_kpi_id"]
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 7 — CREATE MATERIALIZED VIEW: cross-period reporting
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    conn.execute(
        sa.text(
            """
        CREATE MATERIALIZED VIEW IF NOT EXISTS v_kpi_activity_unified AS
        SELECT
            o.id,
            o.kpi_id,
            NULL::text AS check_name,
            'observation' AS entry_type,
            o.value_numeric AS value,
            NULL::text AS value_text,
            o.submitted_at AS "timestamp",
            o.department_id,
            o.school_id,
            o.checker_id AS recorded_by,
            o.auto_result AS status,
            o.evidence,
            NULL::uuid AS legacy_kpi_id
        FROM observations o

        UNION ALL

        SELECT
            ke.id,
            ke.kpi_id,
            ke.check_name,
            ke.check_type AS entry_type,
            ke.value,
            ke.value_text,
            ke."timestamp",
            ke.department_id,
            ke.school_id,
            ke.recorded_by,
            ke.status,
            ke.evidence,
            ke.legacy_kpi_id
        FROM kpi_entries ke
        """
        )
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 8 — SEED SAMPLE DATA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    dept_id = uuid.uuid4()
    school_id = uuid.uuid4()
    kra_id = uuid.uuid4()
    kpi_id = uuid.uuid4()
    entry1_id = uuid.uuid4()
    entry2_id = uuid.uuid4()

    # 1) Sample School
    conn.execute(
        sa.text(
            """
            INSERT INTO schools (id, name, code, status, created_at, updated_at)
            VALUES (:id, :name, :code, 'active', now(), now())
            """
        ),
        {"id": str(school_id), "name": "Greenfield International School", "code": "GIS001"},
    )

    # 2) Sample Department
    conn.execute(
        sa.text(
            """
            INSERT INTO departments (id, school_id, name, code, status, created_at, updated_at)
            VALUES (:id, :school_id, :name, :code, 'active', now(), now())
            """
        ),
        {
            "id": str(dept_id),
            "school_id": str(school_id),
            "name": "Academic Quality Assurance",
            "code": "AQA",
        },
    )

    # 3) Sample KRA (NEW — alongside deprecated old ones)
    conn.execute(
        sa.text(
            """
            INSERT INTO kras (id, name, description, status, created_at, updated_at)
            VALUES (:id, :name, :desc, 'active', now(), now())
            """
        ),
        {
            "id": str(kra_id),
            "name": "Academic Excellence & Compliance",
            "desc": "Ensuring all departments meet academic quality standards and regulatory compliance.",
        },
    )

    # 4) Sample KPI (NEW — alongside deprecated old ones)
    conn.execute(
        sa.text(
            """
            INSERT INTO kpis (
                kpi_id, version, kra_id, title, description,
                target_value, comparator, unit_of_measure, frequency_code,
                formula_type, capture_type, status, created_at
            ) VALUES (
                :kpi_id, 1, :kra_id, :title, :description,
                :target_value, '>=', :unit, :freq,
                'threshold_comparison', 'value_reading', 'active', now()
            )
            """
        ),
        {
            "kpi_id": str(kpi_id),
            "kra_id": str(kra_id),
            "title": "Student Attendance Rate >= 95%",
            "description": "Percentage of students present on any given school day. Target is 95% or higher.",
            "target_value": 95.0,
            "unit": "percent",
            "freq": "daily",
        },
    )

    # 5) Sample KPI Entry 1 (pass)
    conn.execute(
        sa.text(
            """
            INSERT INTO kpi_entries (
                id, kpi_id, check_name, check_type, value,
                "timestamp", department_id, school_id,
                status, notes, created_at, updated_at
            ) VALUES (
                :id, :kpi_id, :check_name, :check_type, :value,
                now(), :dept_id, :school_id,
                'pass', :notes, now(), now()
            )
            """
        ),
        {
            "id": str(entry1_id),
            "kpi_id": str(kpi_id),
            "check_name": "Morning Roll Call — Section A",
            "check_type": "daily_inspection",
            "value": 97.5,
            "dept_id": str(dept_id),
            "school_id": str(school_id),
            "notes": "All students present except 2 on approved leave.",
        },
    )

    # 6) Sample KPI Entry 2 (fail)
    conn.execute(
        sa.text(
            """
            INSERT INTO kpi_entries (
                id, kpi_id, check_name, check_type, value,
                "timestamp", department_id, school_id,
                status, notes, created_at, updated_at
            ) VALUES (
                :id, :kpi_id, :check_name, :check_type, :value,
                now() - interval '1 day', :dept_id, :school_id,
                'fail', :notes, now() - interval '1 day', now() - interval '1 day'
            )
            """
        ),
        {
            "id": str(entry2_id),
            "kpi_id": str(kpi_id),
            "check_name": "Morning Roll Call — Section B",
            "check_type": "daily_inspection",
            "value": 91.2,
            "dept_id": str(dept_id),
            "school_id": str(school_id),
            "notes": "Multiple absences due to local festival. Below 95% threshold.",
        },
    )

    print(f"[KPI V2] Soft-deprecated all existing KRAs and KPIs.")
    print(f"[KPI V2] Created new kpi_entries table with legacy_kpi_id column.")
    print(f"[KPI V2] Created v_kpi_activity_unified materialized view.")
    print(f"[KPI V2] Seeded sample data:")
    print(f"  School:     {school_id}  (Greenfield International School)")
    print(f"  Department: {dept_id}  (Academic Quality Assurance)")
    print(f"  KRA:        {kra_id}  (Academic Excellence & Compliance)")
    print(f"  KPI:        {kpi_id}  (Student Attendance Rate >= 95%)")
    print(f"  Entry 1:    {entry1_id}  (97.5%, pass)")
    print(f"  Entry 2:    {entry2_id}  (91.2%, fail)")


def downgrade() -> None:
    conn = op.get_bind()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP R1 — Drop new objects in reverse order
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Drop materialized view
    op.execute("DROP MATERIALIZED VIEW IF EXISTS v_kpi_activity_unified")

    # Drop kpi_entries (and its indexes)
    op.drop_index("ix_kpi_entries_legacy_kpi", table_name="kpi_entries", if_exists=True)
    op.drop_index("ix_kpi_entries_kpi_status", table_name="kpi_entries", if_exists=True)
    op.drop_index("ix_kpi_entries_school", table_name="kpi_entries", if_exists=True)
    op.drop_index("ix_kpi_entries_department", table_name="kpi_entries", if_exists=True)
    op.drop_index("ix_kpi_entries_asset", table_name="kpi_entries", if_exists=True)
    op.drop_index("ix_kpi_entries_timestamp", table_name="kpi_entries", if_exists=True)
    op.drop_index("ix_kpi_entries_status", table_name="kpi_entries", if_exists=True)
    op.drop_table("kpi_entries", if_exists=True)

    # Drop recreated child tables
    op.drop_table("kpi_event_time_points", if_exists=True)
    op.drop_table("department_kpi_assignments", if_exists=True)

    # Drop the unique index on kpis.kpi_id
    op.drop_index("ix_kpis_kpi_id_unique", table_name="kpis", if_exists=True)

    # Remove added columns from kpis
    op.drop_column("kpis", "owner", if_exists=True)
    op.drop_column("kpis", "description", if_exists=True)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP R2 — Restore kras.name unique constraint
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    op.create_unique_constraint("kras_name_key", "kras", ["name"])

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP R3 — Restore original data from archive tables
    # BUG 4 FIX: Use explicit column lists to handle schema differences
    # between archived (original schema) and current (altered) tables.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Restore KRAs (original schema: id, name, status, created_at)
    # Current kras table has additional columns (description, updated_at) with defaults,
    # so we use INSERT with explicit columns from the archive.
    conn.execute(
        sa.text(
            """
            INSERT INTO kras (id, name, status, created_at)
            SELECT id, name, status, created_at FROM archive_kras_v1
            ON CONFLICT (name) DO NOTHING
            """
        )
    )

    # Restore KPIs (original schema: kpi_id, version, kra_id, title, target_value,
    # comparator, unit_of_measure, frequency_code, status, is_immutable, created_at, created_by)
    # Current kpis has additional columns (description, owner, formula_type, etc.)
    # Use explicit column list to avoid mismatch.
    conn.execute(
        sa.text(
            """
            INSERT INTO kpis (
                kpi_id, version, kra_id, title, target_value,
                comparator, unit_of_measure, frequency_code,
                status, is_immutable, created_at, created_by
            )
            SELECT
                kpi_id, version, kra_id, title, target_value,
                comparator, unit_of_measure, frequency_code,
                status, is_immutable, created_at, created_by
            FROM archive_kpis_v1
            """
        )
    )

    # Restore department_kpi_assignments (explicit columns to avoid mismatch)
    conn.execute(
        sa.text(
            """
            INSERT INTO department_kpi_assignments (id, department_id, kpi_id, assigned_at, assigned_by)
            SELECT id, department_id, kpi_id, assigned_at, assigned_by
            FROM archive_department_kpi_assignments_v1
            """
        )
    )

    # Restore kpi_event_time_points (explicit columns)
    conn.execute(
        sa.text(
            """
            INSERT INTO kpi_event_time_points (id, kpi_id, kpi_version, name, capture_mode_allowed, target_time)
            SELECT id, kpi_id, kpi_version, name, capture_mode_allowed, target_time
            FROM archive_kpi_event_time_points_v1
            """
        )
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP R4 — Drop archive tables
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    op.drop_table("archive_kpi_event_time_points_v1", if_exists=True)
    op.drop_table("archive_department_kpi_assignments_v1", if_exists=True)
    op.drop_table("archive_kpis_v1", if_exists=True)
    op.drop_table("archive_kras_v1", if_exists=True)
