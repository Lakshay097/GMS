"""
Add tables for Dashboards (PRS §30-31), Report Catalogue (PRS §50),
Global Search (PRS §33/§51), and Export Pipeline (R-59/BR-17).

Tables created
--------------
kpi_category_export_restrictions
    Per-category, per-role export/view overrides (BR-04/BR-19/R-50).
    A row here DENIES export for (category_code, role).  Absence = allow.
    Configurable by SuperAdmin/Admin only.

report_export_jobs
    Async export queue.  Heavy Excel/PDF generation is decoupled from the
    request path.  The API enqueues a row; a background worker processes it
    and writes the result_url back (R-59/BR-17).
    - status: pending | processing | completed | failed
    - format: excel | csv | pdf | api
    - expires_at: cleanup after retention period

saved_filters
    Per-user saved search/report filters (PRS §51).
    Private by default (is_public = false).  Only the owner can update/delete.

search_index_sync_log
    Tracks the last-indexed-at timestamp per entity type.
    Used by the indexing lag monitor to confirm < 60 s target (R-60).

Permission matrix rows for DASHBOARD, REPORT, SEARCH modules are inserted
via raw SQL so they survive across the existing ORM-managed permissions table
without requiring a model change.

Revision ID: 20260808_dashboards_reports_search
Revises: 20260808_performance_reviews_scorecards
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260808_dashboards_reports_search"
down_revision = "20260808_performance_reviews_scorecards"
branch_labels = None
depends_on = None

# ── permission rows to seed ────────────────────────────────────────────────────
# (module, action, role, scope_constraint, is_allowed)
_PERMISSION_ROWS = [
    # Dashboard
    ("dashboard", "view", "superadmin", "global",   True),
    ("dashboard", "view", "admin",      "school",   True),
    ("dashboard", "view", "checker",    "school",   True),
    ("dashboard", "view", "auditor",    "school",   True),
    ("dashboard", "view", "viewer",     "granted",  True),
    # Report — read
    ("report",    "read", "superadmin", "global",              True),
    ("report",    "read", "admin",      "school",              True),
    ("report",    "read", "checker",    "school",              False),
    ("report",    "read", "auditor",    "school",              True),
    ("report",    "read", "viewer",     "granted",             True),
    # Report — export (Viewer export gated per-category by kpi_category_export_restrictions)
    ("report",    "export", "superadmin", "global",            True),
    ("report",    "export", "admin",      "school",            True),
    ("report",    "export", "checker",    "school",            False),
    ("report",    "export", "auditor",    "school",            True),
    ("report",    "export", "viewer",     "category_dependent", True),
    # Search — read & create (saved filters)
    ("search",    "read",   "superadmin", "global",  True),
    ("search",    "read",   "admin",      "school",  True),
    ("search",    "read",   "checker",    "school",  True),
    ("search",    "read",   "auditor",    "school",  True),
    ("search",    "read",   "viewer",     "granted", True),
    ("search",    "create", "superadmin", "global",  True),
    ("search",    "create", "admin",      "school",  True),
    ("search",    "create", "checker",    "school",  True),
    ("search",    "create", "auditor",    "school",  True),
    ("search",    "create", "viewer",     "granted", True),
]


def upgrade() -> None:
    # ── kpi_category_export_restrictions ──────────────────────────────────────
    # A row here DENIES export for (category_code, role).
    # Absence of a row = export is allowed (default-open, override-to-restrict).
    op.create_table(
        "kpi_category_export_restrictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("category_code", sa.String(100), nullable=False,
                  comment="KPI category_code from kpis.category_code"),
        sa.Column("restricted_role", sa.String(50), nullable=False,
                  comment="Lowercase role name (e.g. viewer, checker)"),
        # restrict_view also blocks the data from appearing in dashboard widgets
        sa.Column("restrict_export", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("restrict_view",   sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("category_code", "restricted_role",
                            name="uq_category_export_restriction"),
        comment="Per-category, per-role export/view restrictions (BR-04/BR-19/R-50)",
    )
    op.create_index(
        "ix_cat_export_restriction_category",
        "kpi_category_export_restrictions",
        ["category_code"],
    )
    op.create_index(
        "ix_cat_export_restriction_role",
        "kpi_category_export_restrictions",
        ["restricted_role"],
    )

    # ── report_export_jobs ─────────────────────────────────────────────────────
    op.create_table(
        "report_export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        # report_type matches the report slug from PRS §50 catalogue
        # e.g. "compliance", "kpi_performance", "task_aging", …
        sa.Column("report_type", sa.String(100), nullable=False),
        # format: excel | csv | pdf | api
        sa.Column("format", sa.String(20), nullable=False),
        # Serialised filter params (date ranges, dept filter, etc.)
        sa.Column("filters", postgresql.JSONB(), nullable=True),
        # status: pending | processing | completed | failed
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("result_url", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        # Cleanup: expire after configurable retention period
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        comment="Async export job queue (R-59/BR-17) — heavy generation off the write path",
    )
    op.create_index("ix_export_jobs_requested_by", "report_export_jobs", ["requested_by"])
    op.create_index("ix_export_jobs_school",        "report_export_jobs", ["school_id"])
    op.create_index("ix_export_jobs_status",        "report_export_jobs", ["status"])
    op.create_index("ix_export_jobs_enqueued",      "report_export_jobs", ["enqueued_at"])
    op.create_index("ix_export_jobs_expires",       "report_export_jobs", ["expires_at"])

    # ── saved_filters ──────────────────────────────────────────────────────────
    op.create_table(
        "saved_filters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=True),
        # context: "search" | "report:<report_type>" | "dashboard"
        sa.Column("context", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False),
        # Private by default per PRS §51
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        comment="User-saved search/report/dashboard filters — private by default (PRS §51)",
    )
    op.create_index("ix_saved_filters_owner",   "saved_filters", ["owner_user_id"])
    op.create_index("ix_saved_filters_school",  "saved_filters", ["school_id"])
    op.create_index("ix_saved_filters_context", "saved_filters", ["context"])

    # ── search_index_sync_log ──────────────────────────────────────────────────
    # Tracks per-entity-type last-indexed timestamp.  The lag monitor queries
    # this table to verify the < 60 s indexing target (R-60).
    op.create_table(
        "search_index_sync_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        # entity_type matches Meilisearch index name:
        # observation | task | discrepancy | kpi | user | school | department
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation", sa.String(20), nullable=False,
                  comment="upsert | delete"),
        sa.Column("indexed_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
        # write_committed_at: timestamp of the originating write (set by the
        # write-path service before calling the indexer).  Lag = indexed_at - write_committed_at.
        sa.Column("write_committed_at", sa.DateTime(), nullable=True),
        sa.Column("lag_seconds", sa.Numeric(10, 3), nullable=True,
                  comment="Actual lag in seconds; NULL if write_committed_at not provided"),
        comment="Search indexing lag audit log (R-60) — lag target < 60 s",
    )
    op.create_index("ix_sync_log_entity",    "search_index_sync_log",
                    ["entity_type", "entity_id"])
    op.create_index("ix_sync_log_indexed",   "search_index_sync_log", ["indexed_at"])
    op.create_index("ix_sync_log_school",    "search_index_sync_log", ["school_id"])

    # ── Permission matrix rows ────────────────────────────────────────────────
    # Insert new DASHBOARD / REPORT / SEARCH rows; skip if already present
    # (idempotent so re-running upgrade() on a non-fresh DB is safe).
    conn = op.get_bind()
    for module, action, role, scope, allowed in _PERMISSION_ROWS:
        conn.execute(
            sa.text(
                """
                INSERT INTO permissions (id, module, action, role, scope_constraint, is_allowed, created_at)
                VALUES (gen_random_uuid(), :module, :action, :role, :scope, :allowed, now())
                ON CONFLICT (module, action, role) DO NOTHING
                """
            ),
            {"module": module, "action": action, "role": role,
             "scope": scope, "allowed": allowed},
        )


def downgrade() -> None:
    # Remove seeded permission rows first
    conn = op.get_bind()
    modules = tuple({"dashboard", "report", "search"})
    conn.execute(
        sa.text("DELETE FROM permissions WHERE module IN :modules"),
        {"modules": modules},
    )

    op.drop_index("ix_sync_log_school",    table_name="search_index_sync_log")
    op.drop_index("ix_sync_log_indexed",   table_name="search_index_sync_log")
    op.drop_index("ix_sync_log_entity",    table_name="search_index_sync_log")
    op.drop_table("search_index_sync_log")

    op.drop_index("ix_saved_filters_context", table_name="saved_filters")
    op.drop_index("ix_saved_filters_school",  table_name="saved_filters")
    op.drop_index("ix_saved_filters_owner",   table_name="saved_filters")
    op.drop_table("saved_filters")

    op.drop_index("ix_export_jobs_expires",      table_name="report_export_jobs")
    op.drop_index("ix_export_jobs_enqueued",     table_name="report_export_jobs")
    op.drop_index("ix_export_jobs_status",       table_name="report_export_jobs")
    op.drop_index("ix_export_jobs_school",       table_name="report_export_jobs")
    op.drop_index("ix_export_jobs_requested_by", table_name="report_export_jobs")
    op.drop_table("report_export_jobs")

    op.drop_index("ix_cat_export_restriction_role",     table_name="kpi_category_export_restrictions")
    op.drop_index("ix_cat_export_restriction_category", table_name="kpi_category_export_restrictions")
    op.drop_table("kpi_category_export_restrictions")
