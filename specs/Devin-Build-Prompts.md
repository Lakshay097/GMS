# DevinAI Build Prompts — School Operations & Governance Platform (Phase 1)

Source documents (all must be in Devin's repo/context before Prompt 0 runs):
`PRS_School_Governance_Platform_v1_5.md`, `Architecture.md`, `Data-Model.md`,
`API-Spec.md` (v1.5), `Design.md` (v1.5), `phases.md`, `rules.md`, plus the
six supporting files: `assumptions-log.md`, `kpi-seed-data.md`,
`coding-standards.md`, `env-and-secrets.md`, `test-plan.md`,
`ui-copy-and-glossary.md`.

## Document Control

| Version | Description |
|---|---|
| v1.1 | Original 14-prompt pack (Prompt 0–13), aligned to PRS v1.1. Closing section recommended six supporting `.md` files as not-yet-created. |
| **v1.5 (this document)** | Realigned to PRS v1.5 and API-Spec/Design.md v1.5. The six previously-recommended supporting files now exist and are added to every prompt's required context, not just described at the end. Added Prompt 6a (Discrepancy Category/Approval Chain, Holiday Calendar & Working Days, Asset Lifecycle, Compliance Scheduler — BR-21/22/23/24) between Prompt 6 and Prompt 7. Extended Prompt 7 (Observation Capture) with Event Time Capture, Duplicate Detection, and Grace Period/Reopen (BR-25, BR-26). Extended Prompt 8 (Discrepancy) with multi-level Approval Chain resolution (BR-21). Added Evidence Retention/Deletion to Prompt 12 (BR-27). Extended Prompt 13's traceability scope from BR-01–20/FR-001–177 to BR-01–27/FR-001–274 and added two new cross-module workflow tests. Updated Prompt 0's open-items reference from Q1–Q9/AQ1–5 to PRS v1.5's D1–D9/AQ1–5, and pointed it at `assumptions-log.md` as the binding source rather than re-deriving assumptions from scratch.

## How to use this pack

1. Create a new repo. Commit all thirteen spec/support files into a top-level
   `/specs` folder before writing any code — Devin should treat them as the
   source of truth, not your chat messages. The six supporting files
   (`assumptions-log.md`, `kpi-seed-data.md`, `coding-standards.md`,
   `env-and-secrets.md`, `test-plan.md`, `ui-copy-and-glossary.md`) go in
   `/specs` alongside the original seven — populate `kpi-seed-data.md` with
   the real KRA/KPI manuals and resolve `env-and-secrets.md`'s pinned choices
   **before** Prompt 1, or Devin has nothing concrete to build against for
   those two.
2. Send **Prompt 0** first, alone, in a fresh Devin session. Let it finish and
   confirm its understanding before sending Prompt 1.
3. Send the rest **in order**, one per Devin session/task, only after the prior
   prompt's acceptance checklist is green. They build on each other (schema →
   platform services → modules → API → QA) — running them out of order will
   produce rework. Prompt 6a is not optional or skippable — Prompt 7's
   Duplicate/Grace-Period logic and Prompt 8's multi-level approval both
   depend on schema and Master Data it introduces.
4. Every prompt below ends with an **Acceptance check** — paste that back to
   Devin verbatim at the end of the session and don't move on until it can
   answer yes to all of it.
5. Rule IDs (BR-xx, R-xx, AP#, ADR-xx) and FR-xxx numbers refer to `rules.md`
   and the PRS — tell Devin to cite the rule ID in code comments/tests where it
   implements one, so traceability (exit criterion in `phases.md` §1.5) stays
   provable. As of PRS v1.5, Business Rules run BR-01–BR-27 and Functional
   Requirements run through FR-274 — don't let Devin assume an ID above
   BR-20/FR-190 is a typo and silently drop it.
6. Before sending any prompt, paste in the current `Status`/`Decision` row
   from `assumptions-log.md` for every open item that prompt touches, so
   Devin builds against your pinned answer instead of re-deriving its own
   (this is the whole point of that file existing).

---

## Prompt 0 — Ingestion & Plan

```
You have thirteen files in /specs: PRS_School_Governance_Platform_v1_5.md,
Architecture.md, Data-Model.md, API-Spec.md, Design.md, phases.md, rules.md,
assumptions-log.md, kpi-seed-data.md, coding-standards.md, env-and-secrets.md,
test-plan.md, ui-copy-and-glossary.md.

Read all thirteen fully before writing any code. rules.md is the binding rulebook
(BR-xx, R-xx, AP#, ADR-xx, C#) — every rule in it must be enforced in the code you
write, not just described. phases.md defines what is IN and explicitly OUT of
scope for Phase 1 (see §1.1/§1.2) — build only Phase 1 scope; anything in the
"Explicitly Out of Scope" list should not be built, but should not be architected
against either (per rules.md R-41/AP1, Phase 2/3 items must slot into the same
Configuration/Rule/Workflow engines without rework). assumptions-log.md is the
binding source for every open item's current answer — where it conflicts with a
"Pending"/recommendation note in the PRS itself, assumptions-log.md wins, since
it reflects the latest stakeholder decision.

Do the following and stop for my review before writing code:
1. Produce a component/module inventory mapping each PRS Part 2 functional area
   (§18-35) to the architecture components in Architecture.md §4-5 that will
   implement it.
2. Produce a build-order dependency graph (what must exist before what) —
   I will use it to sequence the prompts I send you next.
3. List every open item from phases.md's "Open Items Gating Phase Entry" table
   and PRS §17 (D1-D9) and Architecture §21 (AQ1-AQ5). For each, state the
   assumption you will build against, sourced from assumptions-log.md's current
   Status/Decision column, not re-derived from the PRS's own recommendation text
   — flag any item assumptions-log.md itself marks BLOCKING as a hard stop, not
   a default to guess past.
4. Propose the repo structure (monorepo layout, folder names) consistent with
   Architecture §2/§4 (modular monolith, service-oriented internally, ADR-01),
   coding-standards.md §1's module boundary rule, and the technology stack
   pinned in env-and-secrets.md (Neon serverless Postgres + Neon Auth,
   Cloudinary for media, REST/OpenAPI, async job queue, Redis-class cache,
   OpenSearch-class index).

Do not scaffold or install anything yet. Just report back.
```

**Acceptance check:** Devin has read all 7 specs; produced the inventory,
dependency graph, and assumptions list; assumptions are explicitly labeled;
no code written yet.

---

## Prompt 1 — Repo Scaffolding, Environments, CI/CD

```
Scaffold the project per the repo structure we agreed in the ingestion step.

Requirements:
- Modular monolith, service-oriented internally (Architecture §2, ADR-01),
  not a microservices split — this is a hard architectural constraint, not a
  starting point to refactor away from.
- Provision Neon (serverless Postgres) as the primary datastore and identity
  provider (Neon Auth) per Architecture §18. Provision Cloudinary for media/
  evidence storage (ADR-07). Use the exact variable names and pinned choices
  in `env-and-secrets.md` (including §4a's `DEFAULT_SCHOOL_TIMEZONE` and §6a's
  Compliance Scheduler/Duplicate/Grace-Period config seed values) — do not
  let Devin invent its own env-var names or implicitly pick the async queue
  provider (§5 of that file is a pinned decision, not an open choice).
- Dev / Staging / Production environment separation (rules.md, Architecture §17).
- CI/CD pipeline that runs automated tests on every PR and blocks merge on
  failure — phases.md §1.5 exit criteria requires "no manual data patching"
  and "all rules have automated tests," so the pipeline is not optional
  scaffolding, it's a gating requirement from day one.
- Feature flag infrastructure stood up now, even though nothing uses it yet —
  every later module ships behind a flag (rules.md, PRS §54/§56), named per
  `coding-standards.md` §2's `<phase>.<module>.<capability>` convention.
  Don't wait until a later prompt to add this; retrofitting flags is expensive.
- REST API skeleton at `/v1/...`, OpenAPI spec file checked in and building
  from source annotations (not hand-maintained separately) — API-Spec.md §1
  defines conventions to follow, and `coding-standards.md` §3-4 defines the
  exact error envelope and list-endpoint response shape every module must use.
- Set up the async job queue (Architecture §5.4/§18, provider pinned in
  `env-and-secrets.md` §5) now as empty scaffolding — later prompts will
  register jobs against it (notification dispatch, report export, escalation
  checks, checklist generation, and the Compliance Scheduler from Prompt 6a).

Do NOT implement any business entity yet. This prompt is infrastructure only.
```

**Acceptance check:** repo builds and deploys to a Dev environment; CI runs on
a trivial PR and blocks on a deliberately broken test; Neon + Cloudinary
connections work end-to-end with a health-check endpoint; OpenAPI doc
generates from code; feature-flag service exists with a working on/off toggle
even if unused.

---

## Prompt 2 — Core Schema & Immutability Enforcement

```
Implement the Phase 1 data model exactly as specified in Data-Model.md §3-9,
using its entity definitions, field lists, and relationships as the schema
source of truth (do not invent fields it doesn't list without flagging it as
an addition).

Build, as migrations:
- Core entities (Data-Model §3): schools, departments, users, kras, kpis,
  observations, discrepancies, tasks/task_owners, scorecards.
- Supporting entities (§4): roles/user_roles, escalation_rules, notifications,
  master_data_entries, user_school_grants, vendors/assets (record-keeping
  fields only — no procurement workflow, that's Phase 2/3).
- Checklist & Recurring Task schema (§4.7): ChecklistTemplate, ChecklistInstance
  and items.
- Cross-cutting tables (§5): configuration_items/configuration_overrides,
  audit_log_entries, and the logical search_index.
- **(v1.5)** Governance schema (Data-Model §4.9-ish / PRS §37.12, added for
  BR-21–27 — flag as an addition if Data-Model.md hasn't been updated with
  matching section numbers): `discrepancy_categories`,
  `discrepancy_approval_chain_configurations` (versioned, forward-only),
  `discrepancy_approval_history` (Approval ID, Level, Assigned Role/User,
  Status, Approved At, Comments — FR-237, NOT fixed columns on `discrepancies`),
  `organization_holiday_calendar`, `school_working_days`, `assets` extended
  with a `status` enum (Active/Retired only — BR-23, no procurement/
  maintenance fields), `compliance_scheduler_run_log`,
  `duplicate_observation_overrides`, `observation_reopen_requests`,
  `evidence_retention_config` and `evidence_deletion_log`.

Enforce at the database layer (not the application layer — this is the
non-negotiable part, per rules.md R-15/AP2/ADR-04):
- Row-level tenant isolation on every tenant-scoped table via school_id/
  department_id (rules.md R-02/R-03, Architecture §6). Write a test that
  proves a query without a school_id filter cannot return cross-school rows.
- No UPDATE/DELETE grants for the audit_log_entries table for ANY application
  role, in any environment (R-19) — this is the strongest guarantee in the
  system; get this one exactly right.
- Observations: mutable only until the configured lock period elapses;
  post-lock, no UPDATE possible at the grant/trigger level; corrections
  create a NEW observation referencing the original (R-16, Data-Model §8.1).
- KPIs, Scorecards, Checklist Templates/Instances: version-forward only, prior
  versions never updated once referenced (R-17, R-18, R-20, Data-Model
  §8.2/8.3/8.5, §9 versioning scheme).
- No hard deletes anywhere in business data — every entity lifecycle ends in
  Archived/Deprecated/Superseded (R-09/AP7/C4). Enforce this as an absence of
  DELETE grants, not just "we don't call delete in the app code."
- Forward-only Master Data: existing records keep referencing the enumeration
  value active at creation time, never retroactively repointed (R-14).
- Unique constraint on (template_id, template_version, school_id, department_id,
  period_start) for checklist instance idempotency (R-55).
- **(v1.5)** A matching, but distinct, uniqueness constraint for the
  Compliance Scheduler's *own* idempotency (BR-24) on
  (kpi_id, kpi_version, scope_department_id/asset_id/location_id, due_date)
  — do not reuse the checklist-instance constraint above; these are two
  separate schedulers generating two separate record types (Prompt 4/6a).
- **(v1.5)** `discrepancy_approval_chain_configurations` versions forward-only,
  same pattern as Master Data (R-14); `discrepancy_approval_history` has no
  UPDATE grant once a level's Status is set to Approved/Rejected — an
  approval action is append-only, mirroring the audit_log_entries pattern.
- **(v1.5)** No DELETE grant on `assets` — retirement is a `status` update to
  Retired, never a row removal (BR-23); no DELETE grant on evidence-backing
  rows either — deletion of the underlying Cloudinary asset only happens via
  the explicit, logged Admin/SuperAdmin action built in Prompt 12, never a
  cascading delete from anywhere else in the schema (BR-27).

Write the indexing/partitioning approach per Data-Model §6-7, flagging any
place where AQ2 (partitioning: month vs. school) needs a decision before
production sizing — default to month-based partitioning as a reversible
starting point and note this as an ASSUMPTION.

Every immutability rule above needs an automated test that attempts the
forbidden operation (e.g., UPDATE a locked observation) and asserts it is
rejected at the DB layer, not just that the app layer doesn't call it.
```

**Acceptance check:** all migrations run clean on a fresh Dev database; a
grants audit (`\dp` or equivalent) shows zero UPDATE/DELETE grants on
audit_log_entries for every app role; a test suite exists that attempts and
fails to hard-delete a School/User/Observation/Discrepancy/Task/Scorecard,
attempts and fails to UPDATE a locked Observation, and attempts and fails a
cross-school read.

---

## Prompt 3 — Auth, Tenancy, Roles & Permission Matrix

```
Implement authentication and authorization using Neon Auth.

Requirements:
- Five system roles: SuperAdmin, Admin, Checker, Auditor, Viewer (PRS §11).
  Implement the full Permission Matrix from PRS §12 — API-layer permission
  checks must be identical to UI-layer, not a looser superset (rules.md R-47/
  AP5). There is no "trusted internal API" shortcut.
- A user belongs to exactly one School, except SuperAdmin (all schools) and
  Viewer (may be granted multiple schools) — model multi-school access as
  explicit scope-grant records (user_school_grants), never as a bypass of the
  scope filter (R-01/R-04, C1).
- Scope isolation (School/Department) is a mandatory query-layer filter applied
  BEFORE and INDEPENDENT of role-permission checks (R-02) — implement this as
  a single shared middleware/interceptor every endpoint goes through, not a
  per-endpoint convention that's easy to forget.
- A user may hold multiple roles concurrently within their one school (R-08,
  e.g. Principal = Admin + Viewer).
- MFA required at login for Admin and SuperAdmin roles (R-56).
- Every request re-evaluates permission and scope at execution time — never
  cached/assumed from session start (R-48).
- Data encrypted in transit and at rest (R-57).

Write a permission-matrix test suite: for every (role, module, action) cell
in PRS §12, assert the expected allow/deny outcome at the API layer.
Write a scope-isolation test: same role, two different schools, assert zero
data leakage in either direction.
```

**Acceptance check:** login works with MFA gating for Admin/SuperAdmin;
permission-matrix test suite passes for all PRS §12 cells; scope-isolation
tests pass; a manual attempt to call an API endpoint outside a user's granted
school/department returns a permission error, not partial/filtered data.

---

## Prompt 4 — Cross-Cutting Platform Services

```
Build the six cross-cutting platform services plus the Checklist Scheduler
and the Compliance Scheduler, per Architecture §5/§6.8 and Data-Model §5.
These are shared infrastructure that every later module prompt will call
into — build them generically now so Phase 2/3 additions (weighted scoring,
new state machines, new config scope tiers) are additive, not rewrites (this
is the point of phases.md's "Cross-Phase" table — don't defeat it by
hardcoding module-specific logic into these services).

1. Configuration Engine (§5.1): centralizes Observation Lock Period, Max ETA
   Extensions (fixed at 3, NOT overridable — R-42/R-33), Escalation SLA per
   level, Reminder Frequency, Performance Review Cadence, Session Timeout,
   File Upload Limits, Locales, Feature Flags, KPI Amber Tolerance Band
   (R-41, PRS §54), and **(v1.5)** Duplicate Detection Window, Grace Period,
   and Evidence Retention Period (seed values in `env-and-secrets.md` §6a).
   Support scope tiers (global default + school override) even though only
   global is used in Phase 1 — Phase 2 adds a school-level tier as pure
   config, not new code.
2. Rule Engine (§5.2): pluggable strategy interface. Implement ONE strategy
   for Phase 1 — worst-status-wins — but design the interface so Phase 2's
   weighted-scoring strategy can be added alongside it later without touching
   calling code (rules.md R-36, phases.md §2.1).
3. Workflow Engine (§5.3, ADR-03): data-defined (configurable) state machine
   engine, not per-module hardcoded transitions. Build it to support a
   **parameterized N-level approval sub-stage** (level count and assigned
   role read from configuration, not hardcoded as a single "Approve" step)
   — this is what Prompt 8's Discrepancy Approval Chain (BR-21) will
   configure on top of it; don't build a second, Discrepancy-specific
   approval mechanism later (ADR-09). Don't implement the Discrepancy/Task/
   Checklist state machines themselves here — just the generic engine
   they'll be defined on top of in later prompts.
4. Notification Service (§5.4): async dispatch via the job queue scaffolded
   in Prompt 1. Channels: in-app, email, SMS, WhatsApp. Fixed priority order
   (1 Escalation, 2 Audit Failure, 3 Task Assignment, 4 Due Today, 5 KPI
   Reminder, 6 Comments, 7 Informational — R-38/BR-15). Categories 1 and 2
   cannot be muted by users under any client request path, enforced
   server-side, not just hidden in the UI (R-39/C9). Dispatch must never be
   synchronous/inline with the triggering request (R-40/ADR-05) — write a
   test that a slow/failing notification provider does not block the
   triggering API call.
5. Audit Log Service (§5.5): single shared append-only sink used by every
   module. Confirm it writes through the append-only grants from Prompt 2.
   Confirm it also captures the v1.5 event types added in Prompt 2/6a/7/8:
   blocked duplicate attempts, Override actions, Reopen Requests/Approvals,
   Compliance Scheduler run logs, and Evidence deletion actions.
6. Master Data Service (§5.6): central, forward-only reference data (R-14),
   including **(v1.5)** Discrepancy Category, Organization Holiday Calendar
   entries, Working Days calendars, and Asset.
7. Checklist Scheduler (§5.7, v1.1 addition): generates ChecklistInstances.
   Idempotent and deterministic — re-running after a crash or double-fire
   produces zero duplicate instances, relying on the uniqueness constraint
   built in Prompt 2 (R-55).
8. **Compliance Scheduler (v1.5, PRS §23.16-23.17, BR-24)**: a distinct
   service from the Checklist Scheduler above — generates KPI compliance
   records, not ChecklistInstances. Requirements: idempotent (uses the
   distinct uniqueness constraint from Prompt 2); timezone-aware (computes
   due dates using each School's configured timezone, never server-local/
   UTC — read from the School record, seeded from `DEFAULT_SCHOOL_TIMEZONE`
   in `env-and-secrets.md`); backfilling (a missed run is detected and
   caught up by the next successful run, each record dated to its correct
   original due date); holiday-aware (resolves Working Days + Organization
   Holiday Calendar via the Master Data Service and applies the KPI's
   Non-Working-Day Policy — Skip/Shift Forward/Shift Backward — before
   generating a record). Every run (success or failure, with generated/
   backfilled counts) writes to `compliance_scheduler_run_log`, distinct
   from per-record Audit Log entries.

Each service needs its own unit tests plus one integration test proving a
caller module can use it without knowing its internals (interface contract
test) — later prompts will assume these interfaces are stable.
```

**Acceptance check:** all eight services have passing unit tests; the
notification-blocking test (slow provider ≠ blocked request) passes; the
checklist scheduler idempotency test (double-run → no duplicates) passes;
the Compliance Scheduler idempotency, timezone, backfill, and holiday-policy
tests all pass (double-run → no duplicate compliance records; a School with
a non-UTC timezone gets due dates in its own local time; a simulated outage
backfills every missed occurrence at its correct original due date; a
Skip/Shift-Forward/Shift-Backward policy each produce the documented
outcome); Max ETA Extensions is provably not configurable (attempt to
override it via the Configuration Engine API fails).

---

## Prompt 5 — School / Department / User / Role Management

```
Implement PRS §18-21 using the services from Prompt 4 and the schema from
Prompt 2.

- Only SuperAdmin can create Schools in Phase 1 (R-05/BR-03/C2). Self-service
  registration (Phase 2) should NOT be built or stubbed — it's explicitly out
  of scope (phases.md §1.2); don't add a half-built approval workflow.
- Schools cannot be deleted, only Deactivated; historical data stays
  read-only and reportable (R-10).
- School Name unique within the organization; a School cannot go Active until
  its departments and KPI library import succeed (PRS §52 validation table).
- Departments belong to exactly one School (R-07); Department Name unique
  within a School; cannot Archive with open Tasks or unresolved Discrepancies
  (R-11, PRS §52).
- Users are never hard-deleted — archived, login disabled, full audit history
  retained permanently (R-12/BR-08/C4).
- Employee transfer between departments updates the CURRENT assignment;
  historical records stay attributed to the prior department (R-45/BR-07).
- User validation: unique email/phone, ≥1 active Role, single-School
  constraint unless SuperAdmin/Viewer (PRS §52).
- Only SuperAdmin manages Global Configuration; school-scoped subsets are
  delegable to Admin only where PRS §54's table explicitly says so (R-44).

Build the full CRUD + lifecycle UI and API for these four entities, wired
through the tenancy/permission middleware from Prompt 3.
```

**Acceptance check:** archival is blocked when a Department has open
Tasks/unresolved Discrepancies (test it); School activation is blocked
without departments + KPI import (test it); a deactivated School's historical
data is still readable but not editable; a User "delete" action results in
archived+disabled, never a DB row removal.

---

## Prompt 6 — KRA/KPI Library

```
Implement PRS §22-23 (KRA and KPI Management).

- Global KPI Library is centrally governed and versioned, SuperAdmin-owned
  only — Schools cannot create their own KPI libraries (R-43/BR-04/C3).
- One KPI maps to exactly one KRA (R-17/BR-06) — never multiple.
- Any edit to a KPI's Target/Comparator/Unit creates a new version/ID; the
  prior version is never updated once any Observation references it (R-17/
  BR-05). Historical reports must resolve against the KPI version active at
  the time of the reading, not the current version.
- Comparator must be one of {≥, ≤, =, <, >} (PRS §52 validation).
- Frequency drawn from a supported enumeration (Master Data Service).
- A submission against a Deprecated KPI version is blocked at validation
  (R-21/PRS §52).
- KPI calculation: implement PRS §23.14-15 formula types via the Rule Engine
  from Prompt 4, not hardcoded per-KPI logic. Missing-data handling and
  rounding are Configuration-Engine-driven, not hardcoded (R-36).
- RAG status uses the configurable KPI Amber Tolerance Band from the
  Configuration Engine, with per-category override support (R-37) — build
  against the Status/Decision currently recorded for D6 in
  `assumptions-log.md` (uniform global default with per-category override
  support), not a fresh guess.
- **(v1.5)** Each KPI carries a Capture Type — Value, Event Time, or
  Value + Event Time (PRS §23.6) — and, where it has a recurring compliance
  cycle, a Non-Working-Day Policy (Skip / Shift Forward / Shift Backward,
  default Skip, immutable per KPI version — PRS §23.17/BR-22). These are
  schema/validation additions here in Prompt 6; the Scheduler that actually
  *acts* on them is built in Prompt 6a, and Event Time capture itself is
  built in Prompt 7.
- Populate the Global KPI Library from `kpi-seed-data.md` once it has been
  filled in with the real role-manual content (see that file's own
  blocking-items section) — do NOT invent plausible-looking KPI rows to
  fill gaps in an unpopulated seed file; if it's still template-only, build
  the import mechanism and leave the library empty pending real data,
  exactly as that file instructs.

Write tests: editing a KPI's Target creates a new version and the prior
version becomes immutable once an Observation references it; a submission
against a Deprecated version is rejected with a structured error.
```

**Acceptance check:** KPI versioning test passes; deprecated-version-blocked
test passes; RAG computation is driven by config values, not literals in
code (prove it by changing a config value and observing the RAG output
change without a code deploy).

---

## Prompt 6a — Holiday Calendar, Asset Lifecycle, Discrepancy Category & Approval Chain Master Data, Compliance Scheduler Activation (v1.5)

```
Implement the remaining v1.5 Master Data and activate the Compliance
Scheduler service built in Prompt 4 against real KPI data (PRS §23.16-23.17,
§26, §35.15, BR-21/22/23/24).

1. Holiday Calendar & Working Days (PRS §23.17, §35, BR-22):
   - Organization Holiday Calendar (School-scoped, inheriting organization
     defaults) and per-School Working Days, with an optional per-KPI
     Working Days override.
   - CRUD for both, SuperAdmin/Admin(Sc)-gated per the Permission Matrix.
   - Wire the Compliance Scheduler (Prompt 4) to actually consult these when
     generating the next occurrence for every Active KPI: check the target
     due date against the applicable Working Days calendar and Holiday
     Calendar, apply the KPI's Non-Working-Day Policy (Skip / Shift Forward
     / Shift Backward), and confirm Skip generates zero records for that
     occurrence, Shift Forward/Backward generates exactly one record on the
     shifted date (never one record per skipped day).
2. Asset Lifecycle (PRS §35.15, BR-23) — Phase 1 minimal scope only, do NOT
   build acquisition/procurement/maintenance workflows (that's Phase 3,
   phases.md §1.2):
   - Asset CRUD with `status` Active/Retired (no other states in Phase 1).
   - Retiring an Asset blocks its future assignment to new KPIs/Event Time
     Points/Tasks but leaves every historical Observation/report referencing
     it fully intact.
   - No hard delete — enforced at the DB grant layer from Prompt 2.
3. Discrepancy Category & Approval Chain Configuration (PRS §26, BR-21):
   - Discrepancy Category CRUD (SuperAdmin/Admin(Sc)).
   - Approval Chain Configuration per Category: up to two sequential
     levels, each with an assigned Role, versioned forward-only (never
     edited in place — a change creates a new version).
   - This configures the generic N-level approval sub-stage built into the
     Workflow Engine in Prompt 4 — do not build a second approval mechanism;
     Prompt 8 consumes this configuration.

Write tests: a KPI due date landing on a Holiday with policy=Skip produces
zero compliance records for that occurrence; the same KPI with policy=Shift
Forward produces exactly one record dated to the next working day; a
Retired Asset cannot be assigned to a new KPI/Task but its historical
Observations remain fully readable; changing an Approval Chain
Configuration's level count does not alter any Discrepancy already
in-flight (this last test can be a stub here — Prompt 8 will exercise it
end-to-end once Discrepancy itself exists).
```

**Acceptance check:** Skip/Shift-Forward/Shift-Backward tests all pass;
Asset retire-then-reassign-blocked test passes with historical references
intact; Approval Chain Configuration CRUD works and versions forward-only,
verified by a test that edits a chain and confirms the prior version row is
unchanged, not updated in place.

---

## Prompt 7 — Observation Capture

```
Implement PRS §24 (Observation Capture, Checker role).

- Checkers capture Observations only — they never edit any other business
  record and cannot edit audit data (R-22/BR-11).
- An Observation is always captured against a specific KPI (transitively its
  KRA); an Observation with no linked KPI is never permitted (R-23/BR-20).
- Observation value required and type-matched to the KPI's declared Unit;
  evidence format/size validated at submission (R-28, PRS §52). Route
  evidence uploads through Cloudinary (Architecture §18/ADR-07).
- Mutable only until the configured Lock Period elapses (Configuration
  Engine); after lock, only a NEW Observation referencing the original is
  possible, never an edit (R-16 — this was enforced at the DB layer in
  Prompt 2; wire the application flow to match, don't add an app-layer
  edit path that the DB then silently rejects with a confusing error).
- Auto-Result (Met/Not Met/N/A) is a SYSTEM computation via the Rule Engine
  comparing Observation value to KPI Target via its Comparator — never a
  manual entry field (R-29, PRS §15/§52).
- Idempotency keys are MANDATORY on the Observation submission endpoint
  specifically (R-54/FR-069) — a client retry after a network failure must
  not create a duplicate Observation. Write a test that fires the same
  request twice with the same idempotency key and asserts exactly one
  Observation exists.
- No offline capture or sync — online-only (R-34/BR-16/C7). Client should use
  a retry/resubmit pattern on failure, not local queuing.

**(v1.5) Event Time Capture (PRS §24.14, FR-179–188)** — for any KPI with
Capture Type Event Time or Value + Event Time (from Prompt 6):
- Capture one or more Event Times per Observation, one per defined Event
  Time Point, distinct from and in addition to Submitted At.
- Two capture modes: Auto-Captured (from an integrated signal — GPS/geofence,
  RFID/biometric/QR, IoT/NFC — treated as authoritative, no Reason required)
  and Manual Entry (requires a mandatory Reason from a configurable
  enumeration; blocked entirely where the KPI/Event Time Point is configured
  Auto-Captured-only).
- Persist and surface Time Capture Mode (Auto/Manual) everywhere Event Time
  is displayed — never merge the two without indicating which was used.
- Where the Event Time Point is per-Asset/per-Location scoped, reference the
  relevant Asset/Location record (from Prompt 6a's schema).
- Same lock-period immutability as every other Observation field.

**(v1.5) Duplicate Observation Detection (PRS §24.6, BR-25, FR-256–262)**:
- Before accepting an Observation, check for an existing Observation on the
  same KPI version + scope (Department/Asset/Location) + Event Time Point
  (if applicable) + Checker, submitted within the configured Duplicate
  Detection Window (Configuration Engine, `env-and-secrets.md` §6a default).
- Default: same-Checker-scoped (a different Checker submitting for the same
  occurrence is NOT blocked by default — this is deliberate, to avoid
  false-blocking legitimate shift handoffs); make Checker-agnostic checking
  a per-School config option, off by default.
- On a match: block by default, return the prior Observation's summary in
  the response body (`DUPLICATE_DETECTED`, per `coding-standards.md` §3).
  Only a user holding Override permission may proceed, and only after
  providing a mandatory justification — record the justification, the
  overriding user, and a reference to the original Observation.
- This check is independent of, and in addition to, the FR-069 submission-
  token idempotency above — both apply, addressing different failure modes;
  do not conflate them into one check.
- Log every blocked attempt and every Override action to the Audit Log.

**(v1.5) Grace Period & Reopen (PRS §24.16, BR-26, FR-263–270)**:
- A late Observation (past due date) is still accepted normally, flagged
  Late, within the configured Grace Period — no Admin action required.
- Once the Grace Period elapses without a submission, the compliance record
  transitions Late-Submittable → Closed-Missed; direct Checker submission is
  then rejected.
- A Reopen Request (mandatory reason) from the Checker/Auditor/Admin, plus
  Admin/SuperAdmin approval (single level, Phase 1), restores submittability;
  the resulting submission is flagged both Late and Reopened.
- A backfilled compliance record's (Prompt 6a's Scheduler) Grace Period is
  calculated relative to its original due date, extended by the outage
  duration — do not penalize a Checker for scheduler downtime that wasn't
  their fault.
- Log every Reopen Request and Approval/Rejection to the Audit Log.
```

**Acceptance check:** post-lock edit attempts are rejected end-to-end with a
clear error directing the user to submit a correction, not a raw DB error;
Auto-Result is never client-settable; idempotency-key duplicate test passes;
evidence upload round-trips through Cloudinary correctly; a Manual Event
Time entry without a Reason is rejected, an Auto-Captured one requires no
Reason, and Manual Entry is blocked on an Auto-Captured-only Event Time
Point; a duplicate Observation within the window is blocked by default and
accepted only via a justified Override, verified by test; a Late submission
within the Grace Period is accepted with no Admin action, and a submission
attempted after Grace Period elapses is rejected until an approved Reopen
Request exists.

---

## Prompt 8 — Audit & Discrepancy Management

```
Implement PRS §25-26 (Audit/Verification and Discrepancy Management) using the
Workflow Engine from Prompt 4.

- Auditors never edit Observations — they may only Verify or raise a
  Discrepancy against one; the original Observation is never altered
  (R-24/BR-12/C5).
- Discrepancy lifecycle is a strictly linear, data-defined state machine on
  the Workflow Engine: Raised → Under Investigation → Resolved → Pending
  Approval (Level 1..N, per the Approval Chain Configuration from Prompt 6a)
  → Closed. No skipped states (R-25/BR-13/FR-090).
- Investigation findings are required before a Discrepancy can move to
  Resolved (R-26, PRS §52).
- **(v1.5) Multi-Level Approval (PRS §26, BR-21, FR-231–237)**: a Discrepancy
  requires a Discrepancy Category at creation (immutable thereafter — from
  Prompt 6a). Approval resolves the level count and assigned Role per level
  from that Category's Approval Chain Configuration — do not hardcode a
  single "Approve" step; Phase 1 supports up to two sequential levels. Each
  level's Approver must be distinct from the Investigation Owner AND from
  every Approver at a prior level on the same Discrepancy (segregation of
  duties extended across levels, not just Investigation-vs-Approval). A
  Discrepancy cannot Close until every configured level has reached Approved
  status. Record every approval action as a row in a Discrepancy Approval
  History entity (Level, Assigned Role/User, Status, Approved At, Comments —
  built in Prompt 2/6a), not as fixed columns on the Discrepancy record. An
  in-progress Discrepancy binds to the Approval Chain Configuration version
  active when it entered Approval — a later config change must NOT alter it
  (FR-235). Rejection at any level reopens to Under Investigation, preserving
  prior investigation notes.
- Segregation of duties: the Discrepancy Approver at each level must NOT be
  the same person as the Investigation Owner or any prior-level Approver —
  enforce this as a Workflow Engine guard, not a UI hint (R-27/R-49, PRS §52).

Write tests: attempting to skip a lifecycle state is rejected; attempting to
move to Resolved without Investigation findings is rejected; attempting to
have the same user both investigate and approve (at any level) is rejected;
an Auditor attempting to edit (not verify/raise-discrepancy-against) an
Observation is rejected at the API layer, mirroring the R-24 rule;
attempting Level 2 approval before Level 1 is Approved is rejected;
attempting Closure with only Level 1 Approved on a 2-level chain is
rejected; changing an Approval Chain Configuration mid-flight does not
alter a Discrepancy already in the Approval stage (this exercises the
Prompt 6a stub end-to-end).
```

**Acceptance check:** all tests above pass; the state machine is defined
declaratively (data-driven), and adding a hypothetical new intermediate state
would be a config/data change, not a code change — verify this by pointing to
where the state machine is defined; a Discrepancy Approval History query
returns one row per approval level with correct Role/User/Status/Comments,
not fixed columns.

---

## Prompt 9 — Task Management & Escalation

```
Implement PRS §27 (Task Management) and the Escalation Matrix, using the
Workflow Engine and Configuration Engine from Prompt 4.

- A Task must have ≥1 Primary Owner; there are no "collaborators." Every
  Primary Owner receives notifications, reminders, escalations (R-30/BR-09).
- Task completion rule is set at creation and IMMUTABLE after: ANY owner
  completes / ALL owners must complete / completion requires post-completion
  approval (R-31/BR-09, PRS §52).
- ETA must be in the future at Task creation (R-32, PRS §52).
- Maximum of THREE ETA extensions per Task instance — fixed, not configurable
  (R-33/BR-10/C8/R-42). A fourth extension request automatically triggers
  escalation instead of being granted.
- Configurable, per-department Escalation Matrix with SLA timers, sourced
  from the Configuration Engine (escalation_rules table from Prompt 2).
- Escalation checks run as a scheduled job on the async queue from Prompt 1
  (not inline with any user request).

Write tests: a 4th extension attempt is auto-converted to an escalation
rather than granted; a Task's completion rule cannot be changed after
creation (attempt returns a structured rejection); ETA in the past at
creation is rejected.
```

**Acceptance check:** all three tests above pass; escalation timers fire via
the scheduled job, verified with a fast-forwarded/mocked clock in tests
rather than a real-time wait.

---

## Prompt 10 — Performance Reviews & Scorecards

```
Implement PRS §28-29 (Performance Reviews & Scorecards).

- Scorecards are generated, never updated. Recalculation produces a new
  version (v2); the prior version (v1) is retained and marked
  superseded_by; no application role holds UPDATE/DELETE grants on generated
  scorecard rows (R-18/BR-14/C6 — this grant restriction was set up in
  Prompt 2; confirm the application never attempts an UPDATE path here).
- Periodic generation is driven by Performance Review Cadence from the
  Configuration Engine (per Role/Department), via the async job queue.
- Scorecard computation pulls from the Rule Engine's worst-status-wins
  strategy (Prompt 4) — do not reimplement scoring logic locally.

Write a test: regenerating a Scorecard for the same period produces a new
version, the old version is retained and marked superseded, and no code
path attempts to mutate the old row.
```

**Acceptance check:** versioning test passes; a grants check confirms no
UPDATE/DELETE on scorecard rows for any role.

---

## Prompt 11 — Dashboards, Reports, Search

```
Implement PRS §30-31 and §33 (Dashboards, Report Catalogue, Search) plus the
export pipeline.

- Role-based dashboards per PRS §12 permission matrix — reuse the middleware
  from Prompt 3, do not build parallel permission logic here.
- Full Report Catalogue from PRS §50 (Compliance, KPI Performance, KPI Trend,
  School/Department Scorecard, Audit, Pending Audits, Task Aging, Open
  Discrepancies, Discrepancy Resolution SLA, Overdue KPI, User Performance,
  User Productivity, School/Department Comparison, Escalation Summary,
  Inventory, Vendor, Compliance Dashboard export, Trend Analysis).
- Export formats: Excel, CSV, PDF, REST API (R-59/BR-17).
- Heavy report/dashboard generation must be architecturally separated from
  the write-path — route through read replicas or a dedicated read path so
  report generation cannot degrade transactional (Observation/Task/etc.)
  response times (R-61, Architecture §14). Prove this isn't just "the same
  DB pool" by load-testing a heavy report export concurrently with normal
  writes and confirming write latency doesn't regress.
- Global search: cross-entity, permission-scoped identically to direct
  module access (R-60/PRS §51). Saved filters private by default.
  Indexing lag target < 60 seconds — wire indexing into the OpenSearch-class
  index from the Prompt 1 scaffolding, feeding off the same write path (not
  a nightly batch).
- Category-level export/view overrides (e.g., financial KPIs restricted from
  Viewer export) are configurable per BR-04/BR-19 (R-50).
```

**Acceptance check:** the write-latency-under-report-load test passes;
search indexing lag test (write → searchable within 60s) passes; a Viewer
role cannot export a category flagged as restricted, verified by test.

---

## Prompt 12 — Notification Delivery Wiring, Localization, Settings

```
Two remaining Phase 1 items:

1. Wire every module built so far (Tasks, Discrepancies, Observations, KPIs,
   Schools, Users, Scorecards) to actually fire events into the Notification
   Service from Prompt 4, per the Notification Matrix (PRS §49). Confirm the
   fixed priority order and the un-mutable mandatory categories (Escalation,
   Audit Failure) hold end-to-end, not just in the service's own unit tests.

2. English + Hindi localization (phases.md §1.1) across all UI surfaces and
   notification templates. Supported Locales is a Configuration Engine value
   (PRS §54) — switching locale should not require a redeploy.

3. Settings module (PRS §34) exposing the Configuration Engine's items to
   SuperAdmin (all items) and Admin (school-scoped subset per PRS §54's
   table) through the permission middleware from Prompt 3.

4. **(v1.5) Evidence Retention & Deletion (PRS §47, BR-27, FR-271–274)**:
   surface each evidence file's retention-eligibility status (Retention
   Period elapsed or not — Configuration Engine value, `env-and-secrets.md`
   §4) to Admin/SuperAdmin. Deletion is ALWAYS an explicit, individually
   logged Admin/SuperAdmin action — do not build any automated purge job,
   scheduled cleanup, or cascading delete anywhere in the system. Reject
   deletion attempts on files not yet past their Retention Period, even from
   Admin/SuperAdmin. Log every deletion with actor identity and timestamp
   to the Audit Log.
```

**Acceptance check:** triggering a Discrepancy end-to-end produces an actual
Escalation-priority notification via the real dispatch path, not just a
service-level test double; switching locale to Hindi changes UI copy and
notification templates without a deploy; Admin can only edit the
Configuration items PRS §54 marks as delegable, nothing else; a deletion
attempt on an evidence file before its Retention Period elapses is rejected
even for SuperAdmin; a deletion after the Retention Period elapses succeeds
only via an explicit action and is logged, and no scheduled job exists
anywhere in the codebase that deletes evidence automatically.

---

## Prompt 13 — Full Traceability & Exit-Criteria QA Pass

```
This is a verification pass, not a feature-build prompt.

Go through phases.md §1.5 (Phase 1 Exit Criteria) line by line:

1. Produce a traceability matrix mapping every Business Rule BR-01 through
   BR-27 to at least one automated test file/name that exercises it —
   cross-check against `test-plan.md`'s test names for BR-21–27 specifically,
   since those are the most recently added and most likely to have gaps.
   Flag any rule with zero matching tests.
2. Produce a traceability matrix mapping every Functional Requirement
   FR-001 through FR-274 (per PRS Part 2/3, §23.15/§23.16/§24.15/§24.16's
   additions, and §26.14/§35.15/§47's v1.5 additions) to at
   least one acceptance test. Flag any FR with no coverage.
3. Run (or write, then run) an end-to-end staging test for each of the five
   cross-module workflows named in phases.md §1.5 and rules.md §15:
   - Observation → Audit → Discrepancy → Investigation → Closure
   - Task → ETA → Escalation → Completion
   - KPI → Observation → Scorecard
   - KPI → Compliance Scheduler → Observation → Grace Period → Scorecard (v1.5)
   - Observation → Audit → Discrepancy → multi-level Approval Chain → Closure (v1.5)
   Confirm each completes without any manual data patching.
4. Re-list the open items from `assumptions-log.md` (covering PRS §17's
   D1-D9 and Architecture §21's AQ1-AQ5), and for each, state whether it was
   (a) resolved during build, (b) still an open ASSUMPTION that needs
   stakeholder sign-off before this is truly release-ready, or (c) blocking
   and unresolved. Update `assumptions-log.md` itself with the outcome for
   any item that changed status during the build — don't leave the
   authoritative log stale relative to what actually got built.

Output the three matrices and the open-items status as a single report. Do
not silently mark anything "done" that doesn't have a passing test backing it.
```

**Acceptance check:** both traceability matrices exist with zero unexplained
gaps (every gap is either filled or explicitly flagged); all five end-to-end
workflow tests pass in staging; the open-items report distinguishes clearly
between resolved / assumed / blocking, and `assumptions-log.md` is updated
to match.

---

# Supporting Files (Now Created)

The v1.1 version of this pack recommended six supporting `.md` files that
didn't exist yet — they've since been created and are referenced by prompt
throughout this document rather than left as a closing suggestion. Keep them
in `/specs` alongside the original seven, and keep `assumptions-log.md` in
particular updated as decisions land (it's the one file you own, not Devin):

1. **`assumptions-log.md`** — the binding record of every decision made
   against an open item (PRS §17 D1-D9, Architecture §21 AQ1-AQ5). Referenced
   by Prompt 0, Prompt 6, and Prompt 13. This is still the single
   highest-leverage file in the pack — without it, a long multi-session build
   quietly diverges (e.g., a different Observation Lock Period assumed in
   session 3 vs. session 9). Its own v1.5 update also folds in the
   PRS's Q→D renumbering and the seven gap-closure items' resolved status.

2. **`kpi-seed-data.md`** — the actual KRA/KPI content, now with v1.5's added
   columns (Capture Type, Event Time Point, Non-Working-Day Policy,
   Asset/Location scoping). Referenced by Prompt 6. **Still template-only
   until you populate it with the real ~10 role manuals** — Prompt 6 is
   explicitly instructed not to invent plausible-looking KPIs to fill that
   gap, so this remains the one true launch blocker in the whole pack until
   real content lands.

3. **`coding-standards.md`** — naming conventions, module boundaries (now
   including `/compliance-scheduler` as distinct from `/checklist-scheduler`,
   per Prompt 4/6a), and the exact error-response shape (including the v1.5
   `DUPLICATE_DETECTED` code). Referenced by Prompt 0, 1, and throughout.

4. **`env-and-secrets.md`** — pinned environment variables including v1.5's
   `DEFAULT_SCHOOL_TIMEZONE` (Compliance Scheduler) and the Duplicate
   Detection Window / Grace Period / Evidence Retention Period Configuration
   Engine seed values. Referenced by Prompt 1 and Prompt 4.

5. **`test-plan.md`** — concrete Given/When/Then scenarios per BR-xx/R-xx,
   now including the six new BR-21–27 rule blocks and two new v1.5 e2e
   workflows. Referenced by Prompt 13 for cross-checking the traceability
   matrix.

6. **`ui-copy-and-glossary.md`** — English+Hindi strings, now including the
   eleven new v1.5 terms/statuses/labels (Discrepancy Category, Approval
   Chain, Grace Period, Closed-Missed, Reopen, Duplicate Observation,
   Override, Evidence Retention Period, Asset/Retired, plus the
   `DUPLICATE_DETECTED` error copy). Not directly referenced by a numbered
   prompt above, but should be handed to whichever session builds each
   module's UI layer so terminology doesn't drift module-to-module.
