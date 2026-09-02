# KRA/KPI Schema V2 — Complete Migration Plan (FIXED)

**Date:** 2026-08-30  
**Database:** PostgreSQL (SchoolOP — Neon)  
**Alembic revision:** `20260830_kra_kpi_schema_v2`  
**Status:** Bug-fixed v2 — see Fix Log below

---

## FIX LOG

| Bug | Problem | Fix Applied |
|---|---|---|
| **Bug 1** | `TRUNCATE kpis CASCADE` was intended to only clear KPIs, but could cascade-delete dependent tables. observations/compliance_observations lack DB-level FKs to kpis (plain UUID columns), so cascade was a no-op, but truncation would still orphan those rows. | **Replaced TRUNCATE with soft-delete.** Old KPIs/KRAs are marked `status='deprecated'`, not deleted. New rows are inserted alongside. Zero data loss. |
| **Bug 2** | After truncating kpis, observations.kpi_id rows would point at non-existent UUIDs (dangling FKs). | **Solved by keeping old KPI rows.** Deprecated KPIs remain valid DB rows; old observations still reference them. |
| **Bug 3** | `kpi_entries` FK to `kpis.kpi_id` fails because kpis has composite PK `(kpi_id, version)` — `kpi_id` alone is not unique. | **Added `CREATE UNIQUE INDEX ix_kpis_kpi_id_unique ON kpis(kpi_id)`.** Enables single-column FK from kpi_entries. |
| **Bug 4** | `downgrade()` inserts archived data into recreated tables that may have different column sets than the originals. | **Uses explicit column lists** in all INSERT statements to handle schema differences between archived and current tables. |
| **Gap 1** | Doc claimed 27 tables but migration only handled 4. observations/compliance_observations not protected. | **Clarified:** observations lack DB-level FKs to kpis. No protection needed; old KPI rows preserved. |
| **Gap 2** | Options B/C/D from Phase 5.3 were documented but not implemented. | **Now implemented:** `legacy_kpi_id` column on kpi_entries; `v_kpi_activity_unified` materialized view created. |

---

## PHASE 1 — PRE-DELETION SAFETY CHECK

### 1.1 Tables with Foreign Keys referencing Departments, Schools, KRA, KPI

| Table | FK to Departments | FK to Schools | FK to KRA | FK to KPI | DB-level FK? |
|---|---|---|---|---|---|
| `departments` | — | `school_id` → `schools.id` | — | — | ✅ YES |
| `users` | `department_id`, `requested_department_id` | `school_id` | — | — | ✅ YES |
| `user_school_grants` | — | `school_id` | — | — | ✅ YES |
| `audit_log_entries` | `department_id` | `school_id` | — | — | ✅ YES |
| `kpis` | — | — | `kra_id` → `kras.id` | — | ✅ YES |
| `kpi_event_time_points` | — | — | — | composite FK → `kpis` | ✅ YES |
| `department_kpi_assignments` | `department_id` | — | — | `kpi_id` | ✅ YES |
| `observations` | `department_id` | `school_id` | — | `kpi_id`, `kpi_version` | ⚠️ **NO** — plain UUID columns, no ForeignKey() in ORM |
| `compliance_observations` | `department_id` | `school_id` | — | `kpi_id`, `kpi_version` | ⚠️ **NO** — same as observations |
| `checklist_templates` | `department_id` | `school_id` | — | — | ✅ YES |
| `checklist_instances` | `department_id` | `school_id` | — | — | ✅ YES |
| `tasks` | `department_id` | `school_id` | — | — | ✅ YES |
| `escalation_rules` | `department_id` | `school_id` | — | — | ✅ YES |
| `performance_reviews` | `department_id` | `school_id` | — | — | ✅ YES |
| `scorecards` | — (subject_id can be dept) | — | — | — | — |
| `discrepancies` | `department_id` | `school_id` | — | via `observations` | ✅ YES |
| `discrepancy_approval_chain_config` | `department_id` | `school_id` | — | — | ✅ YES |
| `report_export_jobs` | — | `school_id` | — | — | ✅ YES |
| `saved_filters` | — | `school_id` | — | — | ✅ YES |
| `kpi_category_export_restrictions` | — | — | — | references `category_code` | — |
| `organization_holiday_calendar` | — | `school_id` | — | — | ✅ YES |
| `assets` | — | `school_id` | — | — | ✅ YES |
| `locations` | — | `school_id` | — | — | ✅ YES |
| `notifications` | — | `school_id` | — | — | ✅ YES |

**Critical finding:** `observations` and `compliance_observations` have `kpi_id`/`kpi_version` as **plain UUID/Integer columns** — no `ForeignKey()` in the ORM and no database-level FK constraint. This means:
- `TRUNCATE kpis CASCADE` would **not** cascade-delete observations (no FK to cascade through)
- But truncation would still leave observations with dangling `kpi_id` UUIDs pointing at non-existent rows
- The migration uses soft-delete to avoid this entirely

### 1.2 Dependent Records at Risk

**Direct KPI children (soft-deprecated, not truncated):**
- `kpi_event_time_points` — event-time capture definitions per KPI
- `department_kpi_assignments` — which departments are assigned which KPIs

**Indirectly affected (retain references, safe with soft-delete):**
- `observations` — historical observation records reference `kpi_id` + `kpi_version`. These are **plain UUID columns** (no DB FK), so they survive any KPI table changes. Old observations still reference valid (deprecated) KPI rows.
- `compliance_observations` — same as observations
- `scorecards.kpi_breakdown` — JSONB snapshots reference old KPI data (JSONB, not FK)
- `kpi_category_export_restrictions` — references `category_code` from old KPIs (string match, not FK)

**NOT affected (safe):**
- `departments`, `schools`, `users` — structural entities, not deleted
- `tasks`, `performance_reviews` — reference departments/schools, not KPIs directly
- `discrepancies` — reference `observations`, not KPIs directly

### 1.3 Backup Strategy

The migration creates **archive tables** before any mutation:
- `archive_kras_v1` — full copy of `kras` before modification
- `archive_kpis_v1` — full copy of `kpis` before modification
- `archive_department_kpi_assignments_v1` — full copy before drop
- `archive_kpi_event_time_points_v1` — full copy before drop

For a complete SQL dump before migration:
```bash
pg_dump $DATABASE_URL \
  --data-only \
  --table=kras --table=kpis \
  --table=department_kpi_assignments --table=kpi_event_time_points \
  --table=observations --table=compliance_observations \
  --table=scorecards \
  > backup_kra_kpi_pre_v2_$(date +%Y%m%d).sql
```

### 1.4 Hard Delete vs Soft Delete — FINAL DECISION

| Entity | Decision | Rationale |
|---|---|---|
| `kras` | **SOFT DELETE** → `UPDATE status = 'deprecated'` | Preserves FK references from kpis; audit trail intact |
| `kpis` | **SOFT DELETE** → `UPDATE status = 'deprecated'` | Preserves FK references from observations/compliance_observations; archive tables created as backup |
| `department_kpi_assignments` | **DROP & RECREATE** | Data archived first; recreated with same schema (no column changes) |
| `kpi_event_time_points` | **DROP & RECREATE** | Data archived first; recreated with same schema |
| Old `observations` | **KEEP** (do not touch) | Plain UUID columns still reference valid (deprecated) KPI rows |

**Implementation:** The migration marks all existing KRA/KPI rows as `status='deprecated'` and inserts new rows alongside them. This is safer than TRUNCATE because:
1. No cascade-delete risk
2. No dangling FKs
3. Archive tables provide additional backup
4. Old observations remain fully queryable against deprecated KPIs

---

## PHASE 2 — DELETION ORDER

The migration processes entities in this order:

```
1. ARCHIVE all existing data to archive_*_v1 tables (backup)
2. SOFT-DELETE: UPDATE kpis SET status = 'deprecated'
3. SOFT-DELETE: UPDATE kras SET status = 'deprecated'
4. DROP department_kpi_assignments  (child of kpis — archived first)
5. DROP kpi_event_time_points       (child of kpis — archived first)
6. ALTER kras: drop unique constraint on name
7. ALTER kpis: add description, owner, unique index on kpi_id
8. RECREATE department_kpi_assignments with new schema
9. RECREATE kpi_event_time_points with new schema
10. INSERT new active KRA, KPI, kpi_entries alongside deprecated ones
```

---

## PHASE 3 — NEW SCHEMA DESIGN

### 3.1 Final Schema DDL (PostgreSQL)

```sql
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- DEPARTMENT (unchanged — existing table preserved)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Existing table. Columns: id, school_id, name, code, status, description,
-- head_user_id, auto_accept_requests, created_at, updated_at, archived_at

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- SCHOOL (unchanged — existing table preserved)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Existing table. Columns: id, name, code, status, address, contact_email,
-- contact_phone, configuration, timezone, working_days, created_at, updated_at, deactivated_at

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- KRA — Key Result Area (altered: unique constraint on name removed)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Existing table with columns:
--   id          UUID PK
--   name        VARCHAR(255) NOT NULL  -- no longer unique (multi-school)
--   description TEXT
--   status      VARCHAR(50) DEFAULT 'active'
--   created_at  TIMESTAMP
--   updated_at  TIMESTAMP

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- KPI — Key Performance Indicator (altered: added description, owner, unique index)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Existing table with additions:
--   kpi_id             UUID PK (composite with version)
--   version            INTEGER PK
--   kra_id             UUID FK → kras.id
--   title              VARCHAR(255)
--   description        TEXT          ← NEW
--   owner              UUID FK → users.id  ← NEW (distinct from created_by)
--   target_value       NUMERIC
--   comparator         VARCHAR(10)   -- >=, <=, =, <, >
--   unit_of_measure    VARCHAR(50)
--   frequency_code     VARCHAR(50)   -- daily, weekly, monthly, etc.
--   formula_type       ENUM('threshold_comparison')
--   capture_type       ENUM('value_reading', 'event_time', 'value_and_event_time')
--   category_code      VARCHAR(100)
--   is_sensitive       BOOLEAN
--   evidence_required  BOOLEAN
--   amber_tolerance_band NUMERIC
--   working_days       JSONB
--   non_working_day_policy ENUM
--   status             VARCHAR(50)   -- active, deprecated
--   is_immutable       BOOLEAN
--   created_at         TIMESTAMP
--   created_by         UUID FK → users.id
--
-- UNIQUE INDEX (NEW): ix_kpis_kpi_id_unique ON kpis(kpi_id)
--   Enables kpi_entries FK to reference kpis.kpi_id alone (not composite PK)

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- KPI_ENTRY — Measurement/Check Log (NEW TABLE)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE kpi_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Foreign Keys
    kpi_id          UUID NOT NULL REFERENCES kpis(kpi_id) ON DELETE CASCADE,
    asset_id        UUID REFERENCES assets(id) ON DELETE SET NULL,
    department_id   UUID REFERENCES departments(id) ON DELETE SET NULL,
    school_id       UUID REFERENCES schools(id) ON DELETE SET NULL,
    recorded_by     UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Check Details
    check_name      VARCHAR(255),       -- e.g. "Morning Roll Call — Section A"
    check_type      VARCHAR(50),        -- e.g. "daily_inspection", "weekly_audit"
    
    -- Value
    value           NUMERIC,            -- numeric/percentage/boolean (1/0)
    value_text      TEXT,               -- free-text for text-type KPIs
    
    -- Timing
    "timestamp"     TIMESTAMPTZ NOT NULL DEFAULT now(),  -- when measured (editable for backdating)
    
    -- Workflow
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pass/fail/pending/under_review
    
    -- Optional
    notes           TEXT,               -- free-text notes
    evidence        JSONB,              -- attachment metadata array
    
    -- Traceability (Bug 2 fix)
    legacy_kpi_id   UUID,               -- optional: link to archive_kpis_v1.kpi_id
    
    -- Audit
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE UNIQUE INDEX ix_kpis_kpi_id_unique ON kpis(kpi_id);  -- Bug 3 fix: enables FK
CREATE INDEX ix_kpi_entries_kpi_id ON kpi_entries(kpi_id);
CREATE INDEX ix_kpi_entries_status ON kpi_entries(status);
CREATE INDEX ix_kpi_entries_timestamp ON kpi_entries("timestamp");
CREATE INDEX ix_kpi_entries_asset ON kpi_entries(asset_id);
CREATE INDEX ix_kpi_entries_department ON kpi_entries(department_id);
CREATE INDEX ix_kpi_entries_school ON kpi_entries(school_id);
CREATE INDEX ix_kpi_entries_kpi_status ON kpi_entries(kpi_id, status);
CREATE INDEX ix_kpi_entries_legacy_kpi ON kpi_entries(legacy_kpi_id);

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- MATERIALIZED VIEW: cross-period reporting (Bug gap fix — now implemented)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE MATERIALIZED VIEW v_kpi_activity_unified AS
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
  FROM kpi_entries ke;

-- Refresh after data changes:
-- REFRESH MATERIALIZED VIEW v_kpi_activity_unified;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- ASSET (unchanged — existing table preserved)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- Existing table. Columns: id, school_id, name, category_code, location_id,
-- status, created_at, updated_at
```

### 3.2 Entity Relationship Diagram

```
┌──────────────┐
│   schools    │
│──────────────│
│ id (PK)      │──────┐
│ name         │      │
│ code         │      │
│ status       │      │
│ ...          │      │
└──────────────┘      │
        │             │
        │ 1:N         │
        ▼             │
┌──────────────┐      │
│ departments  │      │
│──────────────│      │
│ id (PK)      │──────┤
│ school_id(FK)│      │
│ name         │      │
│ code         │      │
│ status       │      │
│ ...          │      │
└──────────────┘      │
        │             │
        │ 1:N         │
        ▼             │
┌──────────────┐      │
│     kras     │      │
│──────────────│      │
│ id (PK)      │      │
│ name         │      │
│ description  │      │
│ status       │      │  ← old rows: 'deprecated'
│ created_at   │      │  ← new rows: 'active'
│ updated_at   │      │
└──────────────┘      │
        │             │
        │ 1:N         │
        ▼             │
┌──────────────────────────────────┐
│              kpis                │
│──────────────────────────────────│
│ kpi_id (PK)                      │
│ version (PK)                     │
│ kpi_id UNIQUE INDEX (NEW)  ──────┤── enables kpi_entries FK
│ kra_id (FK) ──→ kras.id          │
│ title                            │
│ description         ← NEW        │
│ owner (FK) ──→ users.id  ← NEW   │
│ target_value                      │
│ comparator                       │
│ unit_of_measure                  │
│ frequency_code                   │
│ status                           │  ← old rows: 'deprecated'
│ ...                              │  ← new rows: 'active'
└──────────────────────────────────┘
        │
        │ 1:N (via unique index on kpi_id)
        ▼
┌──────────────────────────────────┐
│          kpi_entries  ← NEW      │
│──────────────────────────────────│
│ id (PK)                          │
│ kpi_id (FK) ──→ kpis.kpi_id     │  ← references unique index
│ check_name                       │
│ check_type                       │
│ value                            │
│ value_text                       │
│ "timestamp"                      │
│ asset_id (FK) ──→ assets.id     │
│ department_id (FK) ──→ depts    │
│ school_id (FK) ──→ schools      │
│ recorded_by (FK) ──→ users      │
│ status (pass/fail/pending)       │
│ notes                            │
│ evidence (JSONB)                 │
│ legacy_kpi_id        ← NEW      │  ← traceability to old KPIs
│ created_at                       │
│ updated_at                       │
└──────────────────────────────────┘
        │
        │ N:1 (optional)
        ▼
┌──────────────┐
│    assets    │
│──────────────│
│ id (PK)      │
│ school_id(FK)│
│ name         │
│ category_code│
│ location_id  │
│ status       │
│ ...          │
└──────────────┘

┌──────────────────────────────────────────────────┐
│  v_kpi_activity_unified  (MATERIALIZED VIEW)  ← NEW  │
│──────────────────────────────────────────────────│
│  UNION of:                                        │
│    observations (old schema — value_numeric etc.) │
│    kpi_entries  (new schema — value/value_text)   │
│  Columns: id, kpi_id, check_name, entry_type,    │
│    value, value_text, timestamp, department_id,   │
│    school_id, recorded_by, status, evidence,      │
│    legacy_kpi_id                                  │
└──────────────────────────────────────────────────┘
```

---

## PHASE 4 — INPUT VALIDATION RULES

### 4.1 kpi_entries Validation Constraints

| Field | Rule | Enforced By |
|---|---|---|
| `kpi_id` | **Required.** Must reference a valid, existing `kpis.kpi_id`. | FK constraint `REFERENCES kpis(kpi_id) ON DELETE CASCADE` + unique index |
| `timestamp` | Auto-generated on creation (`DEFAULT now()`). Editable for backdating. Application-layer validates not in future. | DB default + app validation |
| `value` | Supports **numeric** (including percentages as 0-100) and **boolean** (1.0 = pass, 0.0 = fail). Nullable for text-only entries. | Column type `NUMERIC` |
| `value_text` | Optional free-text. Used when `kpis.capture_type = 'event_time'` or text KPI. | Nullable column |
| `asset_id` | Optional unless KPI is asset-specific. FK to `assets.id`. | Nullable FK, app validation |
| `status` | Must be one of: `pass`, `fail`, `pending`, `under_review`. | Application-layer enum validation |
| `check_type` | Recommended values: `daily_inspection`, `weekly_audit`, `monthly_review`, `spot_check`, `scheduled_maintenance`. | Application-layer |
| `recorded_by` | Optional (system-generated entries may not have a user). FK to `users.id`. | Nullable FK |
| `legacy_kpi_id` | Optional. If set, must reference a valid deprecated KPI in `archive_kpis_v1`. | Application-layer validation |

### 4.2 Validation Flow

```
Entry Created
    │
    ├── kpi_id required → FK check → 404 if KPI not found
    │
    ├── value: if numeric KPI, must be NUMERIC
    │         if text KPI, use value_text instead
    │
    ├── status: defaults to 'pending'
    │           └── Approval workflow (optional):
    │               pending → under_review → pass/fail
    │
    ├── timestamp: auto = now(), but can be overridden
    │              └── App validates: timestamp <= now() + 1 hour (tolerance)
    │
    ├── asset_id: required if kpi.capture_type needs asset context
    │             app checks kpi.evidence_required flag
    │
    └── legacy_kpi_id: optional; set when migrating historical data
                       app validates: must reference deprecated KPI UUID
```

### 4.3 Approval Workflow (Optional)

The `status` field supports a simple workflow:

```
pending ──→ under_review ──→ pass
                          ──→ fail
pending ──→ pass (auto-approve for non-sensitive KPIs)
pending ──→ fail (auto-fail if value < target)
```

**Sensitive KPIs** (`kpis.is_sensitive = true`) always require `under_review` before `pass`/`fail`.

---

## PHASE 5 — OUTPUT

### 5.1 Final Schema Summary

| Table | Status | Key Changes |
|---|---|---|
| `departments` | **Unchanged** | — |
| `schools` | **Unchanged** | — |
| `kras` | **Altered** | Removed unique constraint on `name`; old rows marked deprecated |
| `kpis` | **Altered** | Added `description` (TEXT), `owner` (UUID FK → users), unique index on `kpi_id`; old rows marked deprecated |
| `kpi_entries` | **NEW** | Measurement/check log with FK to `kpis`, `assets`, `departments`, `schools`, `users`; includes `legacy_kpi_id` for traceability |
| `assets` | **Unchanged** | — |
| `kpi_event_time_points` | **Recreated** | Dropped and recreated (clean slate, same schema) |
| `department_kpi_assignments` | **Recreated** | Dropped and recreated (clean slate, same schema) |
| `v_kpi_activity_unified` | **NEW** | Materialized view unions old observations with new kpi_entries |

### 5.2 Sample Seed Data

The migration seeds:

```sql
-- School
INSERT INTO schools (id, name, code, status) VALUES
  ('a1b2c3d4-...', 'Greenfield International School', 'GIS001', 'active');

-- Department
INSERT INTO departments (id, school_id, name, code, status) VALUES
  ('e5f6a7b8-...', 'a1b2c3d4-...', 'Academic Quality Assurance', 'AQA', 'active');

-- KRA (NEW — alongside deprecated old ones)
INSERT INTO kras (id, name, description, status) VALUES
  ('i9j0k1l2-...', 'Academic Excellence & Compliance',
   'Ensuring all departments meet academic quality standards and regulatory compliance.', 'active');

-- KPI (NEW — alongside deprecated old ones)
INSERT INTO kpis (kpi_id, version, kra_id, title, description, target_value, comparator, unit_of_measure, frequency_code, status) VALUES
  ('m3n4o5p6-...', 1, 'i9j0k1l2-...', 'Student Attendance Rate >= 95%',
   'Percentage of students present on any given school day.', 95.0, '>=', 'percent', 'daily', 'active');

-- KPI Entry 1 (PASS)
INSERT INTO kpi_entries (id, kpi_id, check_name, check_type, value, department_id, school_id, status, notes) VALUES
  ('q7r8s9t0-...', 'm3n4o5p6-...', 'Morning Roll Call — Section A', 'daily_inspection',
   97.5, 'e5f6a7b8-...', 'a1b2c3d4-...', 'pass', 'All students present except 2 on approved leave.');

-- KPI Entry 2 (FAIL)
INSERT INTO kpi_entries (id, kpi_id, check_name, check_type, value, department_id, school_id, status, notes) VALUES
  ('u1v2w3x4-...', 'm3n4o5p6-...', 'Morning Roll Call — Section B', 'daily_inspection',
   91.2, 'e5f6a7b8-...', 'a1b2c3d4-...', 'fail', 'Multiple absences due to local festival. Below 95% threshold.');
```

### 5.3 Migration Notes — Linking Historical Data

**All three options from the original plan are now IMPLEMENTED in the migration:**

#### Option A: Archive Tables (Implemented)
After migration, archive tables preserve all original data:
```sql
-- Cross-reference old observations with archived KPIs:
SELECT o.id, o.kpi_id, o.kpi_version,
       ak.title AS old_kpi_title, ak.status AS old_kpi_status
FROM observations o
JOIN archive_kpis_v1 ak ON o.kpi_id = ak.kpi_id AND o.kpi_version = ak.version;
```

#### Option B: Legacy Reference Column (Implemented)
`kpi_entries.legacy_kpi_id` is a nullable UUID column that can link new entries to old KPI definitions:
```sql
-- Link a new entry to a deprecated KPI:
INSERT INTO kpi_entries (kpi_id, legacy_kpi_id, ...)
VALUES ('<new-kpi-uuid>', '<old-deprecated-kpi-uuid>', ...);
```

#### Option C: Materialized View (Implemented)
`v_kpi_activity_unified` unions old observations with new kpi_entries:
```sql
-- Query across old and new data:
SELECT * FROM v_kpi_activity_unified
WHERE "timestamp" >= '2026-01-01'
ORDER BY "timestamp" DESC;

-- Refresh after data changes:
REFRESH MATERIALIZED VIEW v_kpi_activity_unified;
```

#### Option D: Soft-Legacy KPI Definitions (Implemented)
Old KPIs are marked `status = 'deprecated'` but remain in the `kpis` table. Dashboards can filter:
```sql
-- Show only active (new) KPIs:
SELECT * FROM kpis WHERE status = 'active';

-- Show all KPIs including deprecated:
SELECT * FROM kpis;

-- Count entries per KPI (old and new):
SELECT kpi_id, status, COUNT(*) FROM kpi_entries
JOIN kpis USING (kpi_id)
GROUP BY kpi_id, status;
```

### 5.4 Post-Migration Checklist

- [ ] Run `alembic upgrade head` to apply the migration
- [ ] Verify archive tables exist: `SELECT COUNT(*) FROM archive_kpis_v1;`
- [ ] Verify old KPIs are deprecated: `SELECT status, COUNT(*) FROM kpis GROUP BY status;`
- [ ] Verify new seed data: `SELECT * FROM kpi_entries;`
- [ ] Verify materialized view: `SELECT * FROM v_kpi_activity_unified LIMIT 10;`
- [ ] Run application tests to confirm FK constraints are satisfied
- [ ] Verify observations table still has valid `kpi_id` references (they point to deprecated KPIs)
- [ ] Run scorecard generation job to confirm it works with new KPI IDs
- [ ] Update frontend KPI library component to support new `description` and `owner` fields
- [ ] Update frontend observation capture to support the new `kpi_entries` table
- [ ] Create a Grafana/alerting query for `kpi_entries WHERE status = 'fail'`
- [ ] Refresh materialized view on a schedule: `REFRESH MATERIALIZED VIEW CONCURRENTLY v_kpi_activity_unified;`

### 5.5 Alembic Migration File

The complete Alembic migration is at:
```
migrations/versions/20260830_kra_kpi_schema_v2_migration.py
```

Run with:
```bash
alembic upgrade head
```

To rollback:
```bash
alembic downgrade -1
```

The rollback:
1. Drops all new objects (kpi_entries, materialized view, unique index)
2. Restores archived data with explicit column lists (handles schema differences)
3. Drops archive tables
