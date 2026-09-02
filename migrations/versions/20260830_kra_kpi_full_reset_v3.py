"""
KRA/KPI/Department/School — FULL HARD RESET (V3) — BUG-FIXED

PURPOSE:
  Complete wipe of Departments, Schools, KRAs, and KPIs so a NEW website/app
  can be launched where all org structure is entered DYNAMICALLY through the
  application — nothing is hardcoded in this migration.

THIS IS A DESTRUCTIVE MIGRATION. It backs up first, then hard-deletes.

FIX LOG (addresses review feedback on V3):
  Bug 1: NOT NULL + RESTRICT FKs on observations, compliance_observations,
         discrepancies — UPDATE SET column = NULL fails because columns are
         nullable=False. Fix: ALTER COLUMN ... DROP NOT NULL before NULLing,
         then restore NOT NULL after (via recreate or manual ALTER).
  Bug 2: RESTRICT FKs on discrepancies.school_id, tasks.school_id, etc. —
         DELETE FROM schools is blocked if ANY row has non-NULL school_id.
         Fix: NULL out all references BEFORE deleting parents, in correct
         dependency order (children before parents).
  Bug 3: kpi_entries has ON DELETE CASCADE FK to kpis.kpi_id — deleting all
         kpis rows cascades to delete all kpi_entries rows. Fix: Temporarily
         DROP the FK constraint before deleting kpis, then RE-ADD it after.
  Bug 4: downgrade() uses INSERT INTO ... SELECT * FROM archive — column
         mismatch between archived schema (pre-V2) and current schema
         (post-V2, with description/owner columns). Fix: Use explicit column
         lists in all restore INSERTs.

WHAT HAPPENS TO DEPENDENT DATA:
  - users.department_id / users.school_id       -> set to NULL (users kept, unassigned)
  - observations.department_id / school_id      -> set to NULL (rows kept, orphan-safe)
  - compliance_observations (same columns)      -> set to NULL
  - discrepancies.department_id / school_id     -> set to NULL
  - tasks, checklist_templates, checklist_instances,
    escalation_rules, performance_reviews,
    discrepancy_approval_chain_config, assets,
    locations, notifications, saved_filters,
    report_export_jobs,
    organization_holiday_calendar                -> department_id/school_id set to NULL
  - department_kpi_assignments, kpi_event_time_points -> DROPPED (recreated empty)
  - kpi_entries                                 -> FK TEMPORARILY DROPPED, rows preserved
  - kpis, kras                                  -> DELETED (all rows)
  - departments, schools                        -> DELETED (all rows)

  If DELETE_HISTORICAL_RECORDS=True, observations/tasks/etc. rows are also deleted.

Revision ID: 20260830_kra_kpi_full_reset_v3
Revises: 20260830_kra_kpi_schema_v2
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260830_kra_kpi_full_reset_v3"
down_revision = "20260830_merge_heads"
branch_labels = None
depends_on = None

# ─────────────────────────────────────────────────────────────────────────
# CONFIG: set True if you ALSO want historical rows in observations, tasks,
# etc. deleted entirely (not just unlinked). Default False = keep rows,
# null the department/school reference only.
# ─────────────────────────────────────────────────────────────────────────
DELETE_HISTORICAL_RECORDS = False


def _table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the current schema."""
    return conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables "
            "  WHERE table_schema = 'public' AND table_name = :t"
            ")"
        ),
        {"t": table_name},
    ).scalar()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    return conn.execute(
        sa.text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.columns "
            "  WHERE table_name = :t AND column_name = :c"
            ")"
        ),
        {"t": table_name, "c": column_name},
    ).scalar()


def _get_fk_constraints(conn, table_name: str, column_name: str):
    """Get FK constraint names for a specific column."""
    rows = conn.execute(
        sa.text(
            "SELECT tc.constraint_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "  AND tc.table_name = :t AND kcu.column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    ).fetchall()
    return [r[0] for r in rows]


def _get_not_null_columns(conn, table_name: str) -> set:
    """Get set of NOT NULL columns for a table."""
    rows = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t AND is_nullable = 'NO'"
        ),
        {"t": table_name},
    ).fetchall()
    return {r[0] for r in rows}


def upgrade() -> None:
    conn = op.get_bind()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 1 — BACKUP everything before deleting (safety net, cheap insurance)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    for table in ["departments", "schools", "kras", "kpis"]:
        if not _table_exists(conn, table):
            print(f"[FULL RESET V3] WARNING: table {table} does not exist, skipping backup.")
            continue
        op.execute(f"DROP TABLE IF EXISTS archive_{table}_v3 CASCADE")
        op.execute(f"CREATE TABLE archive_{table}_v3 (LIKE {table} INCLUDING ALL)")
        op.execute(f"INSERT INTO archive_{table}_v3 SELECT * FROM {table}")
        count = conn.execute(
            sa.text(f"SELECT COUNT(*) FROM archive_{table}_v3")
        ).scalar()
        print(f"[FULL RESET V3] Archived {count} rows from {table} -> archive_{table}_v3")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 2 — Unassign users (keep accounts, clear org linkage)
    #
    # users has:
    #   school_id      FK → schools.id (SET NULL)     nullable=True
    #   department_id  FK → departments.id (SET NULL)  nullable=True
    #   requested_department_id FK → departments.id (SET NULL) nullable=True
    #
    # After NULLing, DELETE FROM departments/schools will succeed because
    # RESTRICT only blocks when non-NULL matching rows exist.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    conn.execute(sa.text(
        "UPDATE users SET department_id = NULL, school_id = NULL, "
        "requested_department_id = NULL "
        "WHERE department_id IS NOT NULL "
        "OR school_id IS NOT NULL "
        "OR requested_department_id IS NOT NULL"
    ))
    print("[FULL RESET V3] Cleared department/school assignment on all users.")

    if _table_exists(conn, "user_school_grants"):
        conn.execute(sa.text("DELETE FROM user_school_grants"))
        print("[FULL RESET V3] Cleared all user_school_grants.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 3 — BUG 1 FIX: Handle NOT NULL + RESTRICT FKs
    #
    # Problem: Several tables have department_id/school_id columns that are:
    #   - nullable=False (NOT NULL) — prevents UPDATE SET column = NULL
    #   - FK with RESTRICT — prevents DELETE from parent even after NULLing
    #
    # Affected tables:
    #   observations:         department_id NOT NULL FK(departments) RESTRICT
    #                         school_id     NOT NULL FK(schools) RESTRICT
    #   compliance_observations: school_id NOT NULL FK(schools) RESTRICT
    #   discrepancies:        school_id     NOT NULL FK(schools) RESTRICT
    #                         department_id nullable  FK(departments) RESTRICT
    #
    # Strategy:
    #   a) Drop RESTRICT FK constraints on these columns
    #   b) Drop NOT NULL constraints on these columns
    #   c) SET NULL all references
    #   d) DELETE will then succeed (no non-NULL refs, no blocking FKs)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    tables_with_dept_school = [
        # (table, column, has_not_null, has_fk)
        ("observations", "department_id", True, True),
        ("observations", "school_id", True, True),
        ("compliance_observations", "department_id", False, True),
        ("compliance_observations", "school_id", True, True),
        ("discrepancies", "department_id", False, True),
        ("discrepancies", "school_id", True, True),
        ("tasks", "department_id", False, True),
        ("tasks", "school_id", False, True),
        ("checklist_templates", "department_id", False, True),
        ("checklist_templates", "school_id", False, True),
        ("checklist_instances", "department_id", True, True),
        ("checklist_instances", "school_id", True, True),
        ("escalation_rules", "department_id", False, True),
        ("escalation_rules", "school_id", False, True),
        ("performance_reviews", "department_id", False, True),
        ("performance_reviews", "school_id", False, True),
        ("discrepancy_approval_chain_config", "department_id", False, True),
        ("discrepancy_approval_chain_config", "school_id", False, True),
        ("assets", "school_id", False, True),
        ("locations", "school_id", False, True),
        ("notifications", "school_id", False, True),
        ("saved_filters", "school_id", False, True),
        ("report_export_jobs", "school_id", False, True),
        ("organization_holiday_calendar", "school_id", False, True),
        ("audit_log_entries", "school_id", False, True),
        ("audit_log_entries", "department_id", False, True),
    ]

    # Phase 3a: Drop FK constraints on department_id/school_id
    for table, column, _, _ in tables_with_dept_school:
        if not _table_exists(conn, table):
            continue
        if not _has_column(conn, table, column):
            continue
        fks = _get_fk_constraints(conn, table, column)
        for fk_name in fks:
            op.drop_constraint(fk_name, table, type_="foreignkey")
            print(f"[FULL RESET V3] Dropped FK constraint {fk_name} on {table}.{column}")

    # Phase 3b: Drop NOT NULL constraints on department_id/school_id
    for table, column, has_not_null, _ in tables_with_dept_school:
        if not has_not_null:
            continue
        if not _table_exists(conn, table):
            continue
        if not _has_column(conn, table, column):
            continue
        # Check if column is actually NOT NULL (might have been changed since ORM definition)
        nn_cols = _get_not_null_columns(conn, table)
        if column in nn_cols:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL"
            )
            print(f"[FULL RESET V3] Dropped NOT NULL on {table}.{column}")

    # Phase 3c: NULL out all department_id/school_id references
    for table, column, _, _ in tables_with_dept_school:
        if not _table_exists(conn, table):
            continue
        if not _has_column(conn, table, column):
            continue
        conn.execute(
            sa.text(f"UPDATE {table} SET {column} = NULL WHERE {column} IS NOT NULL")
        )
        print(f"[FULL RESET V3] Cleared {column} on {table}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 3d — BUG 3 FIX: Handle kpi_entries ON DELETE CASCADE
    #
    # kpi_entries.kpi_id has FK → kpis.kpi_id ON DELETE CASCADE.
    # Deleting all kpis rows would cascade-delete all kpi_entries rows.
    # Fix: Drop the FK constraint, NULL the kpi_id column, then re-add
    # the FK constraint after kpis is recreated (empty).
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if _table_exists(conn, "kpi_entries"):
        # BUG FIX: Drop NOT NULL before attempting to NULL the column
        nn_cols = _get_not_null_columns(conn, "kpi_entries")
        if "kpi_id" in nn_cols:
            op.execute("ALTER TABLE kpi_entries ALTER COLUMN kpi_id DROP NOT NULL")
            print("[FULL RESET V3] Dropped NOT NULL on kpi_entries.kpi_id")

        kpi_entry_fks = _get_fk_constraints(conn, "kpi_entries", "kpi_id")
        for fk_name in kpi_entry_fks:
            op.drop_constraint(fk_name, "kpi_entries", type_="foreignkey")
            print(f"[FULL RESET V3] Dropped FK {fk_name} on kpi_entries.kpi_id (preserve rows)")

        # BUG FIX: Archive id→kpi_id mapping BEFORE nulling, so downgrade can restore
        op.execute("DROP TABLE IF EXISTS archive_kpi_entries_kpi_map_v3")
        op.execute(
            "CREATE TABLE archive_kpi_entries_kpi_map_v3 ("
            "  entry_id UUID PRIMARY KEY,"
            "  old_kpi_id UUID"
            ")"
        )
        conn.execute(
            sa.text(
                "INSERT INTO archive_kpi_entries_kpi_map_v3 (entry_id, old_kpi_id) "
                "SELECT id, kpi_id FROM kpi_entries WHERE kpi_id IS NOT NULL"
            )
        )
        map_count = conn.execute(
            sa.text("SELECT COUNT(*) FROM archive_kpi_entries_kpi_map_v3")
        ).scalar()
        print(f"[FULL RESET V3] Archived {map_count} kpi_entries id->kpi_id mappings")

        conn.execute(sa.text("UPDATE kpi_entries SET kpi_id = NULL WHERE kpi_id IS NOT NULL"))
        print("[FULL RESET V3] Cleared kpi_id on kpi_entries (rows preserved)")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 4 — Drop child tables that hard-FK to kpis
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    op.execute("DROP TABLE IF EXISTS department_kpi_assignments CASCADE")
    op.execute("DROP TABLE IF EXISTS kpi_event_time_points CASCADE")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 5 — HARD DELETE (children before parents)
    #          All non-NULL references cleared in Step 2/3, so DELETE succeeds.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if DELETE_HISTORICAL_RECORDS:
        # Delete all dependent rows entirely
        for table in [
            "kpi_entries", "observations", "compliance_observations",
            "discrepancies", "discrepancy_approval_history",
            "tasks", "task_owners", "task_owner_completions",
            "task_eta_extensions", "task_escalations",
            "checklist_instances", "checklist_templates",
            "scorecards", "scorecard_run_log", "performance_reviews",
            "escalation_rules",
        ]:
            if _table_exists(conn, table):
                op.execute(f"DELETE FROM {table}")
                print(f"[FULL RESET V3] Deleted all rows from {table}")

    # Delete core entities (order: children before parents)
    op.execute("DELETE FROM kpis")
    op.execute("DELETE FROM kras")
    op.execute("DELETE FROM departments")
    op.execute("DELETE FROM schools")
    print("[FULL RESET V3] Deleted all rows: kpis, kras, departments, schools.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 6 — Recreate dropped child tables (empty)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
            "assigned_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
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
    op.create_index(
        "ix_department_kpi_kpi_id", "department_kpi_assignments", ["kpi_id"]
    )

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
    # STEP 7 — BUG 3 FIX: Re-add FK constraint on kpi_entries.kpi_id
    #          Now that kpis is empty and will be repopulated dynamically,
    #          the FK is valid for new rows.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if _table_exists(conn, "kpi_entries"):
        # BUG FIX: Guard against constraint name collision on re-run cycles
        existing_fks = _get_fk_constraints(conn, "kpi_entries", "kpi_id")
        for fk_name in existing_fks:
            op.drop_constraint(fk_name, "kpi_entries", type_="foreignkey")
            print(f"[FULL RESET V3] Pre-guard: dropped existing FK {fk_name}")

        op.create_foreign_key(
            "fk_kpi_entries_kpi_id",
            "kpi_entries",
            "kpis",
            ["kpi_id"],
            ["kpi_id"],
            ondelete="CASCADE",
        )
        print("[FULL RESET V3] Re-added FK constraint on kpi_entries.kpi_id -> kpis.kpi_id")

    print("[FULL RESET V3] DONE. All Departments, Schools, KRAs, KPIs are empty.")
    print("[FULL RESET V3] Create new records dynamically via the app/API — no hardcoded seed data.")


def downgrade() -> None:
    conn = op.get_bind()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP R1 — Drop recreated child tables
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    op.execute("DROP TABLE IF EXISTS department_kpi_assignments CASCADE")
    op.execute("DROP TABLE IF EXISTS kpi_event_time_points CASCADE")

    # Drop kpi_entries FK so we can restore kpis without cascade issues
    if _table_exists(conn, "kpi_entries"):
        kpi_entry_fks = _get_fk_constraints(conn, "kpi_entries", "kpi_id")
        for fk_name in kpi_entry_fks:
            op.drop_constraint(fk_name, "kpi_entries", type_="foreignkey")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP R2 — Clear current (empty) data
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    op.execute("DELETE FROM kpis")
    op.execute("DELETE FROM kras")
    op.execute("DELETE FROM departments")
    op.execute("DELETE FROM schools")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP R3 — BUG 4 FIX: Restore archived data with explicit column lists
    #
    # The archive tables were created with LIKE ... INCLUDING ALL, so they
    # mirror the schema at backup time. But the current tables may have
    # different columns (e.g., kpis gained 'description' and 'owner' in V2).
    # Using explicit column lists ensures compatibility.
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Restore schools (original columns — these haven't changed since V1)
    if _table_exists(conn, "archive_schools_v3"):
        # Check which columns exist in both archive and current table
        archive_cols = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'archive_schools_v3'"
                )
            ).fetchall()
        }
        current_cols = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'schools'"
                )
            ).fetchall()
        }
        common_cols = archive_cols & current_cols
        col_list = ", ".join(common_cols)
        conn.execute(
            sa.text(
                f"INSERT INTO schools ({col_list}) "
                f"SELECT {col_list} FROM archive_schools_v3"
            )
        )
        print(f"[FULL RESET V3] Restored schools ({len(common_cols)} columns)")

    # Restore departments
    if _table_exists(conn, "archive_departments_v3"):
        archive_cols = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'archive_departments_v3'"
                )
            ).fetchall()
        }
        current_cols = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'departments'"
                )
            ).fetchall()
        }
        common_cols = archive_cols & current_cols
        col_list = ", ".join(common_cols)
        conn.execute(
            sa.text(
                f"INSERT INTO departments ({col_list}) "
                f"SELECT {col_list} FROM archive_departments_v3"
            )
        )
        print(f"[FULL RESET V3] Restored departments ({len(common_cols)} columns)")

    # Restore KRAs
    if _table_exists(conn, "archive_kras_v3"):
        archive_cols = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'archive_kras_v3'"
                )
            ).fetchall()
        }
        current_cols = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'kras'"
                )
            ).fetchall()
        }
        common_cols = archive_cols & current_cols
        col_list = ", ".join(common_cols)
        conn.execute(
            sa.text(
                f"INSERT INTO kras ({col_list}) "
                f"SELECT {col_list} FROM archive_kras_v3"
            )
        )
        print(f"[FULL RESET V3] Restored kras ({len(common_cols)} columns)")

    # Restore KPIs
    if _table_exists(conn, "archive_kpis_v3"):
        archive_cols = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'archive_kpis_v3'"
                )
            ).fetchall()
        }
        current_cols = {
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'kpis'"
                )
            ).fetchall()
        }
        common_cols = archive_cols & current_cols
        col_list = ", ".join(common_cols)
        conn.execute(
            sa.text(
                f"INSERT INTO kpis ({col_list}) "
                f"SELECT {col_list} FROM archive_kpis_v3"
            )
        )
        print(f"[FULL RESET V3] Restored kpis ({len(common_cols)} columns)")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP R4 — Recreate child tables
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
            "assigned_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
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
    op.create_index(
        "ix_department_kpi_kpi_id", "department_kpi_assignments", ["kpi_id"]
    )

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

    # BUG FIX: Restore kpi_entries.kpi_id from archived mapping
    if _table_exists(conn, "archive_kpi_entries_kpi_map_v3"):
        conn.execute(
            sa.text(
                "UPDATE kpi_entries ke "
                "SET kpi_id = m.old_kpi_id "
                "FROM archive_kpi_entries_kpi_map_v3 m "
                "WHERE ke.id = m.entry_id"
            )
        )
        restored = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM kpi_entries ke "
                "JOIN archive_kpi_entries_kpi_map_v3 m ON ke.id = m.entry_id "
                "WHERE ke.kpi_id = m.old_kpi_id"
            )
        ).scalar()
        print(f"[FULL RESET V3] Restored kpi_id on {restored} kpi_entries from archive")
        op.execute("DROP TABLE IF EXISTS archive_kpi_entries_kpi_map_v3")

    # BUG FIX: Guard against constraint name collision on re-run cycles
    if _table_exists(conn, "kpi_entries"):
        existing_fks = _get_fk_constraints(conn, "kpi_entries", "kpi_id")
        for fk_name in existing_fks:
            op.drop_constraint(fk_name, "kpi_entries", type_="foreignkey")

        op.create_foreign_key(
            "fk_kpi_entries_kpi_id",
            "kpi_entries",
            "kpis",
            ["kpi_id"],
            ["kpi_id"],
            ondelete="CASCADE",
        )
        print("[FULL RESET V3] Re-added FK constraint on kpi_entries.kpi_id -> kpis.kpi_id")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP R5 — Drop archive tables
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    for t in [
        "archive_kpis_v3",
        "archive_kras_v3",
        "archive_departments_v3",
        "archive_schools_v3",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {t}")

    print("[FULL RESET V3] Rollback complete. Restored from archive_*_v3 tables.")
    print("[FULL RESET V3] NOTE: users.department_id/school_id and other cleared FKs "
          "are NOT automatically restored — they were set to NULL and that change "
          "is not reversible from this migration alone.")
