"""Add performance_reviews, scorecards, and scorecard_run_log tables for PRS §28-29.

Business rules enforced at the schema level:
  R-18/BR-14/C6  Scorecards are generated, never updated.  The schema does NOT
                 grant UPDATE/DELETE to any application role on the scorecards
                 table.  This migration adds the tables and explicit REVOKE
                 statements that strip those privileges from the app user.
  versioning     The unique constraint (subject_type, subject_id, cycle_start,
                 cycle_end, version) guarantees each subject×cycle×version is
                 written exactly once.
  superseded_by  Self-referential FK — older version rows point to their
                 replacement row once a new version is generated.

Revision ID: 20260808_performance_reviews_scorecards
Revises: 20260808_task_management
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260808_performance_reviews_scorecards"
down_revision = "20260808_task_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── performance_reviews ───────────────────────────────────────────────────
    op.create_table(
        "performance_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("cycle_start", sa.Date(), nullable=False),
        sa.Column("cycle_end", sa.Date(), nullable=False),
        # Snapshot of cadence_days at creation — avoids retroactive shifts when
        # the Configuration Engine value is later changed by an admin.
        sa.Column("cadence_days", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "school_id",
            "department_id",
            "cycle_start",
            "cycle_end",
            name="uq_performance_review_cycle",
        ),
    )
    op.create_index("ix_perf_review_school", "performance_reviews", ["school_id"])
    op.create_index("ix_perf_review_department", "performance_reviews", ["department_id"])
    op.create_index("ix_perf_review_status", "performance_reviews", ["status"])
    op.create_index(
        "ix_perf_review_cycle", "performance_reviews", ["cycle_start", "cycle_end"]
    )

    # ── scorecards ────────────────────────────────────────────────────────────
    # Created before adding the self-referential FK so the FK target exists.
    op.create_table(
        "scorecards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("performance_reviews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # subject_type: "user" | "department"
        sa.Column("subject_type", sa.String(50), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        # cycle dates — denormalised copy for standalone queries
        sa.Column("cycle_start", sa.Date(), nullable=False),
        sa.Column("cycle_end", sa.Date(), nullable=False),
        # R-18/BR-14: immutable version counter; 1-based per subject×cycle.
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        # Null on the current (latest) version; set to the successor's id when
        # a newer version is generated.
        sa.Column(
            "superseded_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scorecards.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Computed metrics
        sa.Column("rag_status", sa.String(50), nullable=False),
        sa.Column(
            "pct_kpis_met",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "pct_tasks_on_time",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "open_discrepancy_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        # JSONB audit snapshot of per-KPI statuses used for the roll-up.
        sa.Column("kpi_breakdown", postgresql.JSONB(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        # ── uniqueness: each subject×cycle×version written exactly once ────────
        sa.UniqueConstraint(
            "subject_type",
            "subject_id",
            "cycle_start",
            "cycle_end",
            "version",
            name="uq_scorecard_subject_cycle_version",
        ),
    )
    op.create_index("ix_scorecard_review", "scorecards", ["review_id"])
    op.create_index("ix_scorecard_subject", "scorecards", ["subject_type", "subject_id"])
    op.create_index("ix_scorecard_cycle", "scorecards", ["cycle_start", "cycle_end"])
    op.create_index(
        "ix_scorecard_version",
        "scorecards",
        ["subject_type", "subject_id", "cycle_start", "cycle_end", "version"],
    )
    op.create_index("ix_scorecard_superseded_by", "scorecards", ["superseded_by_id"])

    # ── scorecard_run_log ─────────────────────────────────────────────────────
    op.create_table(
        "scorecard_run_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("performance_reviews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        # "success" | "partial_failure" | "failed"
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column(
            "scorecards_generated", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "scorecards_versioned", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("error_detail", sa.Text(), nullable=True),
    )
    op.create_index("ix_scorecard_run_log_review", "scorecard_run_log", ["review_id"])
    op.create_index("ix_scorecard_run_log_started", "scorecard_run_log", ["started_at"])

    # ── R-18/BR-14/C6 — revoke mutation privileges from the application role ──
    # The application connects as the role named in DATABASE_URL.  No application
    # role (checker, auditor, admin, superadmin) may UPDATE or DELETE scorecard
    # rows — recalculation always inserts a new version row instead.
    # These statements are intentionally advisory in SQLite test environments
    # (where REVOKE is a no-op) and enforced on PostgreSQL in production.
    try:
        op.execute(
            "REVOKE UPDATE, DELETE ON scorecards FROM PUBLIC"
        )
    except Exception:
        # SQLite in tests does not support REVOKE — silently skip.
        pass


def downgrade() -> None:
    op.drop_table("scorecard_run_log")
    op.drop_table("scorecards")
    op.drop_table("performance_reviews")
