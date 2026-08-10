# Coding Standards — School Operations & Governance Platform

Purpose: give Devin (and any human engineer) one place to check conventions
instead of re-deriving them per session, so a 13+ prompt build stays
consistent. Everything here is downstream of Architecture.md and API-Spec.md
— where this file is silent, those documents win.

---

## 1. Repo / Module Structure

Follow Architecture §4's component table exactly — one top-level module per
row, no more, no fewer:

```
/modules
  /school-dept-user-role      (PRS §18-21)
  /kra-kpi-library             (PRS §22-23)
  /observation-capture         (PRS §24, incl. Duplicate Detection §24.6, Grace Period §24.16)
  /audit-discrepancy           (PRS §25-26, incl. multi-level Approval Chain §26)
  /task-escalation              (PRS §27)
  /checklist-recurring          (PRS §23-new, §27 extension)
  /performance-scorecards       (PRS §28-29)
  /dashboards-reports-search     (PRS §30-31, §33)
  /notifications                 (PRS §32, module-facing prefs only)
  /settings-master-data           (PRS §34-35, incl. Discrepancy Category, Holiday Calendar, Working Days, Asset §35.15)
/platform_services
  /configuration_engine
  /rule_engine
  /workflow_engine
  /notification_service
  /audit_log_service
  /master_data_service
  /checklist_scheduler
  /compliance_scheduler        (v1.5, PRS §23.16-23.17 — distinct from checklist-scheduler above; generates KPI compliance-cycle records, not ChecklistInstances)
/shared
  /middleware        (tenancy filter, permission checks — Prompt 3)
  /errors            (structured error contract, see §3 below)
  /idempotency
/specs               (the 7 source .md files + these supporting docs, read-only)
```

**Module boundary rule (Architecture §4, restated):** a module writes only to
its own tables. To read/write another module's data, call that module's
service interface — never query its tables directly. This is what lets
Phase 3 service extraction be a deployment change, not a rewrite. Treat any
cross-module raw query as a code-review blocker, not a style nit.

## 2. Naming

- Table names: snake_case, plural (`observations`, `task_owners`) — matches
  Data-Model.md's own naming, don't introduce a second convention.
- Rule references: every place code enforces a BR-xx/R-xx/AP#/ADR-xx rule,
  add a comment citing it, e.g. `// R-33/BR-10: max 3 ETA extensions, not configurable`.
  This is what makes the Prompt 13 traceability matrix generatable instead of
  manually reconstructed. As of PRS v1.5, Business Rules run BR-01–BR-27
  and Functional Requirements run through FR-274 (not just the original
  FR-001–174 range) — don't assume a rule ID above BR-20/FR-190 is a typo.
- Test names: `<rule-id>_<scenario>` where applicable, e.g.
  `test_R16_observation_locked_after_period_rejects_update`. For FR-only
  coverage without a rule ID, use `test_FR069_idempotent_observation_submit`.
- Feature flag names: `<phase>.<module>.<capability>`, e.g.
  `phase2.kpi-library.weighted-scoring` — encodes which phase gates it,
  matching phases.md's Feature Flag rollout mechanism.

## 3. Error Response Shape

Every rejected request returns exactly the shape in API-Spec §3 — no
module invents its own error envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Target Value must be numeric.",
    "field": "target_value"
  }
}
```

HTTP status mapping is fixed (API-Spec §3): 400 validation, 401 auth,
403 permission/scope, 404 not-found-or-not-visible (deliberately
indistinguishable — never leak cross-tenant existence via a different code),
409 conflict/immutability violation — including a detected duplicate
Observation (`DUPLICATE_DETECTED`, BR-25), which carries the prior matching
Observation's summary in the response body so the client can render the
Block/Override prompt — 422 business-rule violation (e.g. 4th ETA
extension, closure attempted before every Discrepancy Approval level is
Approved), 500 always logged to Audit Log.

Put the error contract in `/shared/errors` as a single shared type/class;
every module imports it rather than constructing error JSON inline.

## 4. API Conventions

- All endpoints under `/v1/...`, OpenAPI-documented from source annotations
  (API-Spec §1) — never hand-maintain a separate spec file that can drift.
- List endpoints: `page`/`page_size` (default 50, max 200), mandatory
  `from`/`to` date bounding on high-volume endpoints (Observations, Audit
  Log) — reject unbounded queries with 400 (API-Spec §4). Response envelope:
  `{ "data": [...], "pagination": {...} }` — every list endpoint uses this
  shape, no ad hoc arrays.
- `Idempotency-Key` header support on all record-creating write endpoints;
  mandatory (not optional) on Observation submission (R-54/FR-069). A retry
  with the same key returns the *original* response body, not a fresh 409.
  This is submission-retry idempotency and is distinct from the Compliance
  Scheduler's generation-idempotency (BR-24) and from Duplicate Observation
  detection (BR-25) — all three checks apply independently; implementing
  one is not a substitute for the others.

## 5. Tests

- Every BR-xx/R-xx that describes a forbidden operation gets a test that
  attempts the forbidden operation and asserts rejection — not just a test
  that the happy path works. ("The app never calls UPDATE" is not proof;
  "the DB grant rejects UPDATE" is.)
- Grants/permissions checks (e.g., audit_log_entries has no UPDATE/DELETE
  grant for any role) are asserted programmatically in CI, not verified by
  eyeballing a migration file once.
- Cross-module workflow tests (Observation→Audit→Discrepancy→Investigation→
  Closure; Task→ETA→Escalation→Completion; KPI→Observation→Scorecard) live
  in a dedicated `/tests/e2e` folder, run against staging, not mocked
  end-to-end.

## 6. What "done" means for a module

A module is not done when its happy-path CRUD works. It's done when:
1. Every rule in rules.md tagged to that module (see Architecture §4's
   dependency column) has a passing rejection test.
2. It only touches its own tables (module boundary rule, §1 above).
3. It goes through the shared tenancy/permission middleware, not a local
   reimplementation.
4. Its errors use the shared contract (§3).
5. Its feature flag exists and defaults to off in Production until
   explicitly enabled per school.
