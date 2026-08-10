# API Specification

**School Operations & Governance Platform**

| | |
|---|---|
| Document Type | REST API Endpoint Catalogue |
| Version | 1.5 |
| Derived From | PRS v1.5 (FR-001–FR-274, §12 Permission Matrix, §39 API Requirements, §40 Integration Strategy) · Architecture.md §9–11, §23–25 (API, Security, Integration, Checklist, Event-Time, Governance Architecture) · Data-Model.md §4.7–4.8 |
| Status | Draft for Engineering Review |
| Classification | Internal — Engineering |
| API Version | `/v1` |

---

## Document Control

| Version | Description |
|---|---|
| v1.0 | Initial endpoint catalogue covering all Part 2 functional modules. Markdown endpoint tables, not a machine-readable OpenAPI YAML/JSON file — see Section 12 for why, and what would be needed to generate one. |
| v1.1 | Added Section 10a (Checklist & Recurring Task Management) covering the frequency-based checklist system (Architecture.md §23, Data-Model.md §4.7): Checklist Template CRUD/versioning, Instance listing/completion/verification, Shift Pattern configuration, and a Checklist Compliance report. Updated auth endpoints (§2) to reflect **Neon Auth**, and file-upload endpoints (§8, §10a) to reflect **Cloudinary** as the storage provider with its expanded allowlisted format set (image/video/document). Updated Table of Contents, Endpoint-to-FR Traceability (§17), and Open API Questions (§19). |
| v1.2 | Extended Section 8 (Observation Capture) with Event Time capture on submission (`event_times`, `time_capture_mode`, `manual_time_reason`, `location_id`, `asset_id`) and added Section 14a (Locations) for per-floor/zone/wing Master Data (PRS §24.14, §37.10, FR-179–190). |
| v1.3 | No new endpoints (Security hardening, PRS §41, is a cross-cutting constraint on every endpoint, not a new resource). Added explicit rate-limiting, CORS, and security-header notes to Section 1 (Conventions) and Section 2 (Authentication). |
| v1.4 | Added Section 16a (Integration Partner Management) and rewrote Section 16 (Webhooks/Events) to distinguish the interactive `/v1/...` webhook surface from the new, separately-versioned, separately-rate-limited `/integrations/v1/...` server-to-server surface (PRS §39, §40, FR-211–230). |
| **v1.5 (this document)** | Full catch-up revision. Extended Section 9 (Audit & Discrepancy) with multi-level Discrepancy Category/Approval Chain endpoints, replacing the single `approve` call with a per-level approval action (BR-21, FR-231–237). Extended Section 8 with Duplicate Detection response/override handling and Grace Period/Reopen endpoints (BR-25, BR-26, FR-256–270). Added Section 14b (Holiday Calendar & Working Days) and Section 14c (Asset Lifecycle) (BR-22, BR-23, FR-238–249). Added Section 14d (Evidence Retention & Deletion) (BR-27, FR-271–274). Added Compliance Scheduler run-log read endpoint to Section 15a. Added seven new reports to Section 12 (Holiday Impact, Asset Status, Scheduler Run Log, Duplicate Observation, Grace Period/Reopen, Integration Sync, Sync Exception). Updated Endpoint-to-FR Traceability (§17) and Open API Questions (§19). Document version bumped 1.1 → 1.5 to realign with PRS v1.5. |

---

## Table of Contents

1. [Conventions](#1-conventions)
2. [Authentication & Authorization](#2-authentication--authorization)
3. [Error Response Contract](#3-error-response-contract)
4. [Pagination, Filtering, Field Selection](#4-pagination-filtering-field-selection)
5. [Idempotency](#5-idempotency)
6. [School / Department / User / Role](#6-school--department--user--role)
7. [KRA / KPI Library](#7-kra--kpi-library)
8. [Observation Capture](#8-observation-capture)
9. [Audit & Discrepancy](#9-audit--discrepancy)
10. [Task & Escalation](#10-task--escalation)
10a. [Checklist & Recurring Task Management](#10a-checklist--recurring-task-management)
11. [Performance & Scorecards](#11-performance--scorecards)
12. [Dashboards, Reports, Search](#12-dashboards-reports-search)
13. [Notifications](#13-notifications)
14. [Settings, Master Data, Configuration](#14-settings-master-data-configuration)
14a. [Locations](#14a-locations)
14b. [Holiday Calendar & Working Days](#14b-holiday-calendar--working-days)
14c. [Asset Lifecycle](#14c-asset-lifecycle)
14d. [Evidence Retention & Deletion](#14d-evidence-retention--deletion)
15. [Audit Log (Read)](#15-audit-log-read)
15a. [Compliance Scheduler Run Log (Read)](#15a-compliance-scheduler-run-log-read)
16. [Webhooks / Events](#16-webhooks--events)
16a. [Integration Partner Management](#16a-integration-partner-management)
17. [Endpoint-to-FR Traceability](#17-endpoint-to-fr-traceability)
18. [Next Step: Machine-Readable OpenAPI](#18-next-step-machine-readable-openapi)
19. [Open API Questions](#19-open-api-questions)

---

## 1. Conventions

- **Base path:** `https://api.<domain>/v1`
- **Format:** JSON request/response bodies; `Content-Type: application/json`.
- **Resource naming:** plural nouns, matching Data-Model.md table names (`/schools`, `/observations`, `/discrepancies`).
- **Permission notation:** each endpoint lists allowed roles using the same shorthand as PRS §12 — `Sc` means scoped to the caller's school/department, per Architecture.md §6's mandatory scope filter, applied *in addition to* the role check, not instead of it.
- **Timestamps:** ISO 8601, UTC, e.g. `2026-08-05T09:00:00Z`.
- **Every endpoint below enforces the identical Permission Matrix as the UI** (PRS §39) — there is no separate, looser API-only authorization path.

---

## 2. Authentication & Authorization

| Aspect | Detail |
|---|---|
| Scheme | Bearer token (`Authorization: Bearer <token>`), issued by **Neon Auth** at login (Architecture.md §10) | 
| MFA | Enforced at login for Admin/SuperAdmin via Neon Auth's MFA enrollment before a token is issued (§41) — not an API-layer concern beyond honoring the login flow's result |
| Token lifetime | Configurable inactivity timeout (Configuration Engine, §54) layered over Neon Auth's session lifetime; expired tokens return `401` |
| Scope enforcement | Every request is filtered by `school_id`/`department_id` derived from the token's granted scope (Architecture.md §6) — a request cannot widen its own scope via query parameters. Neon Auth resolves *who* the caller is; this platform's own `user_roles`/scope tables (Data-Model.md §4.1) resolve *what* they can do |
| Multi-role | Token carries the union of the user's roles (BR-02); endpoint-level checks evaluate against the full role set, with documented exceptions (self-audit block, investigation/approval separation) evaluated per-request, not at token-issuance time |

```
POST /v1/auth/login              — proxies to Neon Auth; returns platform-scoped bearer token
POST /v1/auth/mfa/verify         — Neon Auth MFA challenge verification
POST /v1/auth/logout
POST /v1/auth/token/refresh
POST /v1/auth/sso/{provider}     — Phase 2, reserved: Neon Auth SSO/OAuth connector
```

---

## 3. Error Response Contract

Per PRS §53.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Target Value must be numeric.",
    "field": "target_value"
  }
}
```

| HTTP Status | Meaning |
|---|---|
| 400 | Validation error (structured, field-referenced) |
| 401 | Missing/expired auth token |
| 403 | Authenticated but not permitted (role or scope failure) |
| 404 | Resource not found *or* not visible within caller's scope (these are intentionally indistinguishable to avoid leaking cross-tenant existence) |
| 409 | Conflict (duplicate name, concurrent audit action, immutability violation) |
| 422 | Well-formed request that violates a business rule (e.g., 4th ETA extension attempt) |
| 500 | Unhandled server error, always logged to Audit Log per §53 |

---

## 4. Pagination, Filtering, Field Selection

All list endpoints (`GET` on a collection) support:

```
GET /v1/observations?page=1&page_size=50&from=2026-07-01&to=2026-07-31&department_id=...&status=locked&fields=observation_id,value_numeric,submitted_at
```

- `page` / `page_size` (default 50, max 200) — required to protect the §46 performance targets.
- Date-range bounding (`from`/`to`) is **mandatory** on high-volume endpoints (Observations, Audit Log) per §31.6 — an unbounded query is rejected with `400`.
- `fields` — optional sparse fieldset selection.
- Response envelope:
```json
{
  "data": [ /* ... */ ],
  "pagination": { "page": 1, "page_size": 50, "total_count": 4213, "has_next": true }
}
```

---

## 5. Idempotency

Write endpoints that create records accept `Idempotency-Key` header. **Mandatory** for Observation submission (FR-069):

```
POST /v1/observations
Idempotency-Key: <client-generated-uuid>
```
A retry with the same key returns the original `201` response body (not a duplicate `409`), matching PRS's "prevent duplicate Observations on retry" requirement rather than merely blocking the retry.

---

## 6. School / Department / User / Role

PRS §18–21, FR-001–FR-046 (School/Dept/User/Role sections).

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `POST` | `/schools` | SuperAdmin | Create school; auto-creates default departments + imports current KPI Library | FR-001, FR-002 |
| `GET` | `/schools` | SuperAdmin, Viewer(granted) | List schools | — |
| `GET` | `/schools/{school_id}` | SuperAdmin, Admin(Sc), Viewer(granted) | School detail | — |
| `PATCH` | `/schools/{school_id}` | SuperAdmin | Update school (status transitions) | — |
| `POST` | `/schools/{school_id}/departments` | SuperAdmin, Admin(Sc) | Create department | — |
| `GET` | `/schools/{school_id}/departments` | All roles (Sc) | List departments | — |
| `PATCH` | `/departments/{department_id}` | SuperAdmin, Admin(Sc) | Update/archive department | — |
| `POST` | `/users` | SuperAdmin, Admin(Sc) | Create/invite user | — |
| `GET` | `/users` | SuperAdmin, Admin(Sc) | List users, filterable by role/department/status | — |
| `GET` | `/users/{user_id}` | Self, SuperAdmin, Admin(Sc) | User detail | — |
| `PATCH` | `/users/{user_id}` | SuperAdmin, Admin(Sc) | Update user (roles, department, language pref) | — |
| `POST` | `/users/{user_id}/archive` | SuperAdmin, Admin(Sc) | Archive user (no hard delete) | BR-08 |
| `POST` | `/users/{user_id}/roles` | SuperAdmin, Admin(Sc) | Grant additional role (BR-02) | — |
| `DELETE` | `/users/{user_id}/roles/{role_code}` | SuperAdmin, Admin(Sc) | Revoke role (last role cannot be revoked — `422`) | — |
| `POST` | `/users/{user_id}/school-grants` | SuperAdmin | Grant Viewer multi-school access | C1 |

---

## 7. KRA / KPI Library

PRS §22–23, FR-047–FR-060, FR-175–FR-177.

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `POST` | `/kras` | SuperAdmin | Create KRA | — |
| `GET` | `/kras` | All roles | List KRAs | — |
| `PATCH` | `/kras/{kra_id}` | SuperAdmin | Update / deprecate KRA | — |
| `POST` | `/kpis` | SuperAdmin | Create KPI (v1), must reference one non-deprecated KRA | FR-047, FR-048 |
| `GET` | `/kpis` | All roles | List current-version KPIs, filterable by KRA/department | — |
| `GET` | `/kpis/{kpi_id}` | All roles | Current KPI version detail | — |
| `GET` | `/kpis/{kpi_id}/versions` | All roles | Full version history | FR-051 |
| `GET` | `/kpis/{kpi_id}/versions/{version}` | All roles | Specific historical version | FR-051 |
| `PATCH` | `/kpis/{kpi_id}` | SuperAdmin | Edit Target/Comparator/Unit → **creates new version**, never mutates prior (returns new version in response) | FR-049, FR-050 |
| `POST` | `/kpis/{kpi_id}/deprecate` | SuperAdmin | Deprecate KPI | — |
| `POST` | `/departments/{department_id}/kpi-assignments` | SuperAdmin, Admin(Sc) | Assign KPI to Department | FR-055 |
| `DELETE` | `/departments/{department_id}/kpi-assignments/{kpi_id}` | SuperAdmin, Admin(Sc) | Unassign | — |
| `POST` | `/kpis/import` | SuperAdmin | Bulk import KPI catalogue (CSV/Excel template) | FR-058 (v3.0 numbering) |

---

## 8. Observation Capture

PRS §24, FR-061–FR-069, FR-179–190 (Event Time, v1.2), FR-256–274 (Duplicate Detection / Grace Period / Evidence, v1.5).

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `POST` | `/observations` | Checker | Submit observation against an assigned KPI. Requires `Idempotency-Key`. Body includes `event_times[]`, `time_capture_mode`, `manual_time_reason` when the KPI's `capture_type` requires it (v1.2), and `location_id`/`asset_id` for scoped KPIs. | FR-064, FR-069, FR-179–188 |
| `GET` | `/observations` | All roles (Sc), bounded date range required | List observations, filterable by KPI, department, checker, lock status, location, asset, compliance status | §31.6 |
| `GET` | `/observations/{observation_id}` | All roles (Sc) | Observation detail, including `compliance_status`, `event_times`, `duplicate_override_flag`, `reopened_flag` (v1.5 fields) | — |
| `PATCH` | `/observations/{observation_id}` | Checker (original submitter only, pre-lock) | Edit prior to lock; returns `409` if already locked | BR-11 |
| `POST` | `/observations/{observation_id}/corrections` | Checker | Post-lock correction — creates a **new** Observation referencing the original; original untouched | §24, BR-11 |
| `POST` | `/observations/{observation_id}/evidence` | Checker (pre-lock) | Upload/replace evidence file | §41 |
| `POST` | `/observations/{observation_id}/override-duplicate` *(v1.5)* | Checker with Override permission | Confirms submission of an Observation flagged as a likely duplicate by `POST /observations` (which returns `409 DUPLICATE_DETECTED` with the prior matching Observation's summary). Requires a mandatory `justification` field. | BR-25, FR-256–259 |
| `GET` | `/observations/pending-compliance` *(v1.5)* | Checker (own scope), Admin(Sc) | List compliance-shell records (`compliance_status IN ('open','late_submittable')`) awaiting submission — the Checker's "still-due" work queue | §23.16, §24.16 |
| `POST` | `/observations/{observation_id}/reopen-request` *(v1.5)* | Checker, Auditor, Admin (on a `closed_missed` record) | Submit a Reopen Request with mandatory `reason` | BR-26, FR-266 |
| `POST` | `/observations/{observation_id}/reopen-approve` *(v1.5)* | Admin(Sc), SuperAdmin | Approve/reject a Reopen Request; approval flips `compliance_status` back to `late_submittable`, enabling `PATCH`/`POST /observations` for that shell | BR-26, FR-266, FR-270 |

**Duplicate Detection response contract (v1.5):** `POST /observations` runs the duplicate check (FR-256) before the idempotency-key check completes acceptance. A detected duplicate returns:
```json
{
  "error": {
    "code": "DUPLICATE_DETECTED",
    "message": "A matching Observation was already submitted within the Duplicate Detection Window.",
    "original_observation_id": "..."
  }
}
```
The caller must resubmit via `POST /observations/{observation_id}/override-duplicate` (with `justification`) rather than retrying `POST /observations` directly — this keeps duplicate-override an explicit, auditable action distinct from an ordinary retry (FR-260).

---

## 9. Audit & Discrepancy

PRS §25–26, FR-070–FR-100 range (illustrative; exact numbers per PRS body), FR-231–237 (Multi-Level Approval, v1.5).

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `GET` | `/audit-queue` | Auditor, Admin(Sc) | List Observations pending verification | — |
| `POST` | `/observations/{observation_id}/verify` | Auditor (not the submitting Checker) | Mark Observation Verified | FR-026, FR-085 |
| `POST` | `/observations/{observation_id}/discrepancies` | Auditor | Raise a Discrepancy against an Observation. Body requires `category_id` (immutable thereafter). | FR-085, FR-231 |
| `GET` | `/discrepancies` | Admin(Sc), Auditor(Sc), SuperAdmin | List discrepancies, filterable by state/age/category | — |
| `GET` | `/discrepancies/{discrepancy_id}` | Admin(Sc), Auditor(Sc), SuperAdmin | Detail incl. full state history and per-level approval history (`approvals[]`) | — |
| `POST` | `/discrepancies/{discrepancy_id}/assign-investigator` | Admin(Sc) | Assign Investigation Owner | — |
| `POST` | `/discrepancies/{discrepancy_id}/investigate` | Investigation Owner | Submit findings, transitions to next state | FR-091 |
| `POST` | `/discrepancies/{discrepancy_id}/resolve` | Investigation Owner | Submit resolution note; transitions to Pending Approval and snapshots the Category's current Approval Chain version | §26.6, FR-235 |
| `POST` | `/discrepancies/{discrepancy_id}/approvals/{level}/approve` *(v1.5, replaces v1.1's single `/approve`)* | Role resolved from the snapshotted Approval Chain Configuration for that level — **must differ from the Investigation Owner and from every Approver at a prior level** | Approve the specified level; `403` if approver conflicts with FR-233's segregation-of-duties rule; advances to the next level or, if this was the final configured level, to Closed | FR-232–234 |
| `POST` | `/discrepancies/{discrepancy_id}/approvals/{level}/reject` *(v1.5)* | Same role resolution as approve | Reject the level; Discrepancy returns to Under Investigation, prior investigation notes preserved | FR-093 |
| `POST` | `/discrepancies/{discrepancy_id}/close` | System-triggered once every configured level is Approved — no direct user-facing call in v1.5 (superseded by the last level's `approve` action) | Final close | BR-13, FR-234 |

All state-changing calls above route through the Workflow Engine (Architecture.md §13) — a request for a transition not valid from the current state returns `422`, not a silent no-op (FR-090). The chain length (1 or 2 levels, Phase 1 cap) is resolved per-Discrepancy from its snapshotted `approval_chain_version_id`, so `{level}` is validated against that specific Discrepancy's configured levels, not a hardcoded range.

**Discrepancy Categories & Approval Chain Configuration** *(v1.5, Master Data — see also Section 14)*

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `GET` | `/discrepancy-categories` | All roles | List categories | — |
| `POST` | `/discrepancy-categories` | SuperAdmin | Create category (name, allow_delegate) | — |
| `GET` | `/discrepancy-categories/{category_id}/approval-chain` | Admin(Sc), SuperAdmin | Current Approval Chain Configuration (levels, roles, auto-escalation SLA) | — |
| `PATCH` | `/discrepancy-categories/{category_id}/approval-chain` | SuperAdmin | Publish a new Approval Chain Configuration version; in-progress Discrepancies are unaffected (FR-235) | FR-232, FR-236 |

---

## 10. Task & Escalation

PRS §27, FR-101–FR-113.

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `POST` | `/tasks` | Admin, Dept Head(Sc), Checker(peer, if enabled) | Create task; requires ≥1 Primary Owner, future ETA, completion rule set (immutable after) | FR-101, FR-104, FR-107 |
| `GET` | `/tasks` | All roles (Sc) | List tasks, filterable by status/owner/department/priority | — |
| `GET` | `/tasks/{task_id}` | All roles (Sc) | Task detail incl. owners and completion state per owner | — |
| `PATCH` | `/tasks/{task_id}` | Admin, Dept Head(Sc) | Update mutable fields (title, description, tags) — completion rule rejected with `409` if attempted | FR-104 |
| `POST` | `/tasks/{task_id}/owners` | Admin, Dept Head(Sc) | Add Primary Owner | FR-101 |
| `DELETE` | `/tasks/{task_id}/owners/{user_id}` | Admin, Dept Head(Sc) | Remove Primary Owner (blocked if it would leave zero owners — `422`) | — |
| `POST` | `/tasks/{task_id}/complete` | Assigned Primary Owner | Mark complete for calling owner; task-level status transitions per completion rule (ANY/ALL) | FR-103 |
| `POST` | `/tasks/{task_id}/approve` | Admin(Sc), Dept Head(Sc) | Approve completion where rule requires it | — |
| `POST` | `/tasks/{task_id}/eta-extension` | Admin, Dept Head(Sc), assigned Owner | Request ETA extension; 4th request auto-escalates instead of extending (`422` + escalation event) | BR-10, FR-105 |
| `GET` | `/departments/{department_id}/escalation-rules` | Admin(Sc), SuperAdmin | List escalation chain | — |
| `POST` | `/departments/{department_id}/escalation-rules` | Admin(Sc), SuperAdmin | Configure ordered escalation levels + SLA | — |

---

## 10a. Checklist & Recurring Task Management

Architecture.md §23, Data-Model.md §4.7. Formalizes the frequency-based, recurring compliance checklists evidenced across all 10 role-based KRA/KPI manuals (daily/weekly/monthly/quarterly/per-shift checks) as a first-class resource family, distinct from ad-hoc Task (Section 10) but reusing its remediation/escalation machinery on a miss.

**Templates** (versioned definitions — SuperAdmin/Admin author these; Checkers/role-holders never create a Template directly)

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `POST` | `/checklist-templates` | SuperAdmin, Admin(Sc) | Create checklist template (v1): title, Frequency, Role/Department scope, optional KRA/KPI link, items | — |
| `GET` | `/checklist-templates` | All roles (Sc) | List current-version templates, filterable by Role, Department, Frequency | — |
| `GET` | `/checklist-templates/{template_id}` | All roles (Sc) | Current template version + items | — |
| `GET` | `/checklist-templates/{template_id}/versions` | Admin(Sc), SuperAdmin | Full version history | — |
| `PATCH` | `/checklist-templates/{template_id}` | SuperAdmin, Admin(Sc) | Edit items/frequency/scope → **creates new version**, never mutates prior (mirrors `PATCH /kpis/{id}`) | — |
| `POST` | `/checklist-templates/{template_id}/deprecate` | SuperAdmin, Admin(Sc) | Deprecate template (stops future generation; existing Instances unaffected) | — |
| `POST` | `/checklist-templates/{template_id}/items` | SuperAdmin, Admin(Sc) | Add item to the next version (implicitly versions the template) | — |

**Shift Patterns** (backs `Frequency = Per-Shift` templates — Security Guard, Transport Manager)

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `POST` | `/departments/{department_id}/shift-patterns` | Admin(Sc), SuperAdmin | Define a shift window (start/end time, active weekdays) | — |
| `GET` | `/departments/{department_id}/shift-patterns` | All roles (Sc) | List shift patterns for a department | — |
| `PATCH` | `/shift-patterns/{shift_pattern_id}` | Admin(Sc), SuperAdmin | Update/archive a shift pattern | — |

**Instances** (system-generated by the Checklist Scheduler, Architecture.md §5.7 — no direct user-facing create endpoint, matching the `POST /scorecards/generate` pattern in Section 11)

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `GET` | `/checklist-instances` | All roles (Sc), bounded date range required | List instances, filterable by template, status, department, assignee, period | §31.6 (pattern) |
| `GET` | `/checklist-instances/{instance_id}` | All roles (Sc) | Instance detail incl. items and per-item responses | — |
| `POST` | `/checklist-instances/{instance_id}/items/{template_item_id}/respond` | Assigned user | Submit response for one item (boolean/numeric/text + optional evidence upload); rolls up `pct_items_complete` | — |
| `POST` | `/checklist-instances/{instance_id}/complete` | Assigned user | Mark instance complete once all items are responded; `422` if any item unanswered | — |
| `POST` | `/checklist-instances/{instance_id}/verify` | Admin(Sc), Dept Head(Sc) | Verify a completed instance (optional verification step per template configuration) | — |
| `GET` | `/checklist-instances/{instance_id}/audit-log` | Admin(Sc), SuperAdmin, Auditor(Sc) | Full transition history for the instance | — |

All state-changing calls above route through the Workflow Engine (Architecture.md §13, `ChecklistInstance` state machine) — a request for a transition not valid from the current state returns `422`, same contract as Section 9's Discrepancy endpoints. A `Missed` instance auto-populates `remediation_task_id` (and `remediation_discrepancy_id` for a critical-item failure) — these are surfaced read-only via `GET /checklist-instances/{instance_id}`, not created by a separate call.

**Reporting**

| Method | Path | Roles | Description |
|---|---|---|---|
| `GET` | `/reports/checklist-compliance` | Admin, Dept Head, SuperAdmin | Compliance % by template/department/period — generated vs. completed vs. missed, feeding Scorecards (Section 11) alongside KPI compliance |

---

## 11. Performance & Scorecards

PRS §28–29, FR-114–FR-151 range.

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `GET` | `/scorecards` | Admin(Sc), SuperAdmin, self(User) | List current scorecards, filterable by subject type/cycle | — |
| `GET` | `/scorecards/{scorecard_id}` | Admin(Sc), SuperAdmin, self, Auditor(own) | Scorecard detail | FR-128 |
| `GET` | `/scorecards/{scorecard_id}/versions` | Admin(Sc), SuperAdmin | Full version history for a subject/cycle | BR-14 |
| `POST` | `/scorecards/generate` | System-triggered (scheduled job); no direct user-facing create endpoint | Regenerates create a new version, never mutate | BR-14 |
| `GET` | `/performance-reviews` | Admin(Sc), SuperAdmin | List review cycles | — |
| `PATCH` | `/performance-reviews/{review_id}` | Admin(Sc), SuperAdmin | Update review cadence config (routes through Configuration Engine) | — |

---

## 12. Dashboards, Reports, Search

PRS §30–31, §33, §50.

| Method | Path | Roles | Description |
|---|---|---|---|
| `GET` | `/dashboards/{dashboard_type}` | Role-dependent per §30 | Pre-aggregated dashboard payload (read-optimized, Architecture.md §14) |
| `GET` | `/reports/compliance` | Admin, SuperAdmin | Compliance Report |
| `GET` | `/reports/kpi-performance` | Admin, SuperAdmin | KPI Performance Report |
| `GET` | `/reports/kpi-trend` | Dept Head, SuperAdmin | KPI Trend Report |
| `GET` | `/reports/school-scorecard` | SuperAdmin | School-level scorecard aggregation |
| `GET` | `/reports/department-scorecard` | Admin, SuperAdmin | Department-level scorecard aggregation |
| `GET` | `/reports/audit` | Auditor, SuperAdmin | Audit actions/outcomes |
| `GET` | `/reports/pending-audits` | Auditor, Admin | Open audit queue by age |
| `GET` | `/reports/task-aging` | Admin, Dept Head | Open tasks by age |
| `GET` | `/reports/open-discrepancies` | Admin, SuperAdmin | Open discrepancies by stage/age |
| `GET` | `/reports/discrepancy-sla` | Admin, SuperAdmin | SLA adherence |
| `GET` | `/reports/overdue-kpi` | Dept Head, Admin | Overdue/breaching KPIs |
| `GET` | `/reports/user-performance/{user_id}` | Admin, self | Individual scorecard history |
| `GET` | `/reports/user-productivity` | Admin | Task/KPI throughput per user |
| `GET` | `/reports/school-comparison` | SuperAdmin | Cross-school benchmarking |
| `GET` | `/reports/department-comparison` | Admin, SuperAdmin | Cross-department benchmarking |
| `GET` | `/reports/escalation-summary` | Admin, SuperAdmin | SLA breaches, escalation history |
| `GET` | `/reports/integration-sync` *(v1.4)* | SuperAdmin, Admin(Sc) | Per-partner sync status, last successful sync, failure history |
| `GET` | `/reports/sync-exceptions` *(v1.4)* | SuperAdmin, Admin(Sc) | Inbound ERP records pending manual resolution |
| `GET` | `/reports/holiday-impact` *(v1.5)* | Admin, SuperAdmin | Compliance cycles Skipped/Shifted due to holidays, by School |
| `GET` | `/reports/asset-status` *(v1.5)* | Admin, SuperAdmin | Active vs. Retired Assets by School, with last-referenced-Observation date |
| `GET` | `/reports/duplicate-observations` *(v1.5)* | Admin, SuperAdmin | Blocked duplicates and Override actions, by School/Department/Checker |
| `GET` | `/reports/grace-period-reopen` *(v1.5)* | Admin, SuperAdmin | Closed-Missed records with reopen requests, approvals, and outcomes |
| `GET` | `/reports/event-time` *(v1.2)* | Admin, SuperAdmin | Event Time readings by Location/Asset with Capture Mode and Reason breakdown |
| `POST` | `/reports/{report_type}/export` | Per report's role list, plus Viewer(granted) | Async export (Excel/CSV/PDF); returns `202` + job ID, never blocks (§31.12) |
| `GET` | `/exports/{job_id}` | Requesting user | Poll export job status / download link |
| `GET` | `/search` | All roles (Sc) | Global cross-entity search, `q`, `entity_type`, `date_range` params (§33) |
| `POST` | `/search/saved-filters` | All roles | Save a filter (private by default) |

All report/export endpoints enforce the same bounded-date-range and pagination rules as Section 4.

---

## 13. Notifications

PRS §32, §49, FR-150, FR-165.

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `GET` | `/notifications` | Self | List own notifications, filterable by tier/read-status | — |
| `POST` | `/notifications/{notification_id}/read` | Self | Mark read | — |
| `GET` | `/notification-preferences` | Self | View own channel preferences per event category | — |
| `PATCH` | `/notification-preferences` | Self | Update preferences — **server rejects any attempt to mute Tier 1/2 (mandatory), regardless of payload** | FR-165 |

---

## 14. Settings, Master Data, Configuration

PRS §34–35, §54, FR-163–FR-174.

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `GET` | `/settings/me` | Self | Personal settings (language, notification defaults) | FR-163 |
| `PATCH` | `/settings/me` | Self | Update personal settings, applies immediately | FR-164 |
| `GET` | `/master-data?category=` | All roles | List reference entries by category | — |
| `POST` | `/master-data` | SuperAdmin | Create entry | FR-169, FR-171 |
| `POST` | `/master-data/{code}/deprecate` | SuperAdmin | Deprecate (blocked if in active use, unless deprecate-but-retain) | §35.12 |
| `GET` | `/configuration` | SuperAdmin, Admin(Sc, own subset) | List configuration items + current resolved values | §54 |
| `PATCH` | `/configuration/{config_key}` | SuperAdmin, or Admin where `editable_by` permits (Sc) | Update global default or school/department override; logged to Audit Log | §48 |
| `GET` | `/feature-flags` | SuperAdmin | List feature flags | — |
| `PATCH` | `/feature-flags/{flag_key}` | SuperAdmin | Toggle flag (phased rollout, §56) | — |

---

## 14a. Locations *(v1.2)*

PRS §37.10, FR-189. Per-floor/zone/wing scoping used by Event-Time-scoped Observations.

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `POST` | `/locations` | SuperAdmin, Admin(Sc) | Create a Location (floor/zone/wing) within own School | FR-189 |
| `GET` | `/locations` | All roles (Sc) | List Locations | — |
| `PATCH` | `/locations/{location_id}` | SuperAdmin, Admin(Sc) | Update/archive a Location | — |

---

## 14b. Holiday Calendar & Working Days *(v1.5)*

PRS §35, §23.17, BR-22, FR-238–243.

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `GET` | `/holiday-calendar` | All roles (Sc) | List holiday dates — organization defaults plus school-scoped overrides, merged | — |
| `POST` | `/holiday-calendar` | SuperAdmin (organization-level), Admin(Sc, school-scoped additions) | Add a holiday date (label, recurrence type) | FR-238 |
| `DELETE` | `/holiday-calendar/{holiday_id}` | Same as create scope | Remove a future holiday date; past dates are not editable | — |
| `GET` | `/schools/{school_id}/working-days` | All roles (Sc) | School-level Working Days default | FR-239 |
| `PATCH` | `/schools/{school_id}/working-days` | SuperAdmin, Admin(Sc) | Update School-level Working Days default | FR-239 |
| `PATCH` | `/kpis/{kpi_id}/working-days` | SuperAdmin | Set a per-KPI Working Days override and/or Non-Working-Day Policy — **creates a new KPI version** (immutable once set, FR-241) | FR-239–241 |

---

## 14c. Asset Lifecycle *(v1.5)*

PRS §35.15, §37.12, BR-23, FR-244–249.

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `GET` | `/assets` | All roles (Sc) | List Assets, filterable by status/category/location | — |
| `GET` | `/assets/{asset_id}` | All roles (Sc) | Asset detail, incl. current Status | — |
| `POST` | `/assets/{asset_id}/retire` | Admin(Sc), SuperAdmin | Transition Status → Retired; blocked from new assignment thereafter but historical Observations unaffected | FR-244–247 |
| `POST` | `/assets/{asset_id}/reactivate` | Admin(Sc), SuperAdmin | Transition Status → Active | §35.12 |

No `DELETE` endpoint is exposed for `/assets/{asset_id}` — an Asset with linked Observations cannot be hard-deleted (FR-248); Retirement is the only offered lifecycle-end action.

---

## 14d. Evidence Retention & Deletion *(v1.5)*

PRS §47, BR-27, FR-271–274.

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `GET` | `/observations/{observation_id}/evidence/status` | Admin(Sc), SuperAdmin | Returns `evidence_storage_tier` (Active/Archived) and deletion-eligibility flag (whether the Evidence Retention Period has elapsed) | FR-271, FR-272 |
| `POST` | `/observations/{observation_id}/evidence/delete` | Admin(Sc), SuperAdmin only | Explicit, logged deletion of an evidence file that has passed its Evidence Retention Period. `403` if the file is not yet eligible for deletion. **No scheduled/automated equivalent exists** — this is the only path by which evidence is ever removed. | FR-273, FR-274 |

---

## 15. Audit Log (Read)

PRS §45. Read-only surface — there is intentionally no write endpoint; all writes happen internally via the Audit Log Service (Architecture.md §5.5).

| Method | Path | Roles | Description |
|---|---|---|---|
| `GET` | `/audit-log?entity_type=&entity_id=&from=&to=` | SuperAdmin, Admin(Sc), Auditor(Sc, verify/discrepancy actions only) | Query audit trail; bounded date range mandatory |
| `GET` | `/audit-log/{audit_log_id}` | Same as above | Single entry detail |

---

## 15a. Compliance Scheduler Run Log (Read) *(v1.5)*

PRS §23.16, FR-255. Read-only — the Scheduler itself is a background service (Architecture.md §5.7a), not user-invoked.

| Method | Path | Roles | Description |
|---|---|---|---|
| `GET` | `/scheduler-runs?from=&to=` | SuperAdmin | List Compliance Scheduler run history: status, records generated, records backfilled, per-timezone batch |
| `GET` | `/scheduler-runs/{run_id}` | SuperAdmin | Single run detail incl. error detail on partial failure |

---

## 16. Webhooks / Events

Per PRS §39 ("webhook/event support SHALL be available for state-transition events") and Architecture.md §9. **v1.4 note:** this section covers the interactive-side webhook subscription surface only — server-to-server ERP/third-party sync uses the separate `/integrations/v1/...` surface in Section 16a, which has its own authentication, rate limits, and deprecation policy (§39, §41.6).

| Method | Path | Roles | Description |
|---|---|---|---|
| `POST` | `/webhooks` | SuperAdmin, Admin(Sc) | Register a webhook subscription (URL + event types) |
| `GET` | `/webhooks` | SuperAdmin, Admin(Sc) | List own subscriptions |
| `DELETE` | `/webhooks/{webhook_id}` | Owner, SuperAdmin | Remove subscription |

**Published event types (Phase 1):** `discrepancy.state_changed`, `discrepancy.approval_level_actioned` *(v1.5)*, `task.escalated`, `scorecard.generated`, `observation.locked`, `observation.compliance_status_changed` *(v1.5, e.g. → closed_missed, → reopened)*, `kpi.version_published`, `asset.status_changed` *(v1.5)*.

**Delivery contract:** at-least-once delivery, signed payload (HMAC), consumer expected to de-duplicate via the event's `event_id`.

---

## 16a. Integration Partner Management *(v1.4)*

PRS §40, §41.3, FR-211–230. Server-to-server ERP/third-party surface, namespaced separately from the interactive API (`/integrations/v1/...` vs. `/v1/...`), per §39's "secured integration surface" requirement.

**Partner registry (interactive-side administration)**

| Method | Path | Roles | Description | FR Ref |
|---|---|---|---|---|
| `POST` | `/integration-partners` | SuperAdmin | Register a new Integration Partner (name, auth type, scopes, school_scope, environment) | — |
| `GET` | `/integration-partners` | SuperAdmin, Admin(Sc, own school's partners only) | List Integration Partners | — |
| `GET` | `/integration-partners/{integration_partner_id}` | SuperAdmin, Admin(Sc) | Detail incl. `last_successful_sync_at`, `status` | — |
| `POST` | `/integration-partners/{integration_partner_id}/credentials/rotate` | SuperAdmin | Rotate Client Secret/API Key; old credential invalidated per Configuration Engine's rotation policy | §41.3 |
| `POST` | `/integration-partners/{integration_partner_id}/suspend` | SuperAdmin | Suspend (blocks further sync without revoking registration) | — |
| `POST` | `/integration-partners/{integration_partner_id}/revoke` | SuperAdmin | Revoke (permanent; a new registration is required to reconnect) | — |
| `POST` | `/integration-partners/{integration_partner_id}/certify` | SuperAdmin | Promote Sandbox → Production once certification passes (§40.7) | — |

**Server-to-server sync surface** (called by the ERP/third-party itself, authenticated via OAuth 2.0 Client Credentials, scoped API Key, or optional mTLS — never a human bearer token)

| Method | Path | Auth | Description | FR Ref |
|---|---|---|---|---|
| `POST` | `/integrations/v1/oauth/token` | Client Credentials grant | Issue a scoped, short-lived access token for a registered Integration Partner | §40.2 |
| `POST` | `/integrations/v1/schools/upsert` | Partner token | Upsert School records (idempotency key required) | §40.1, §40.3 |
| `POST` | `/integrations/v1/departments/upsert` | Partner token | Upsert Department records | §40.1 |
| `POST` | `/integrations/v1/users/upsert` | Partner token | Upsert User records — platform-owned fields (Role, School-internal Status) are ignored if present in the payload, not overwritten (§40.4) | §40.1, §40.4 |
| `GET` | `/integrations/v1/scorecards/export` | Partner token, scope=`scorecards:read` | Pollable, read-only Scorecard/Performance export | §40.1 |
| `GET` | `/integrations/v1/sync-exceptions` | Partner token or SuperAdmin (interactive) | List this partner's unresolved Sync Exceptions | §40.4 |
| `POST` | `/sync-exceptions/{sync_exception_id}/resolve` *(interactive side)* | Admin(Sc), SuperAdmin | Manually resolve a Sync Exception | §40.4 |

**Rate limits and deprecation:** every `/integrations/v1/...` endpoint enforces a rate limit scoped to the calling Integration Partner, independent of interactive-user limits, and carries a longer minimum deprecation-notice window than `/v1/...` given the operational cost of ERP re-certification (§39, §41.6). Outbound webhooks from this surface are HMAC-signed with a timestamp and nonce to prevent replay.

---

## 17. Endpoint-to-FR Traceability

A sample mapping — full traceability should be maintained as a living spreadsheet/table alongside this document as endpoints are implemented, matching PRS §55's acceptance-criteria requirement that all FRs trace to a test.

| FR | Endpoint(s) |
|---|---|
| FR-069 (idempotent Observation submission) | `POST /observations` |
| FR-090 (no skipped Discrepancy states) | All `/discrepancies/{id}/*` transition endpoints |
| FR-092 (Approver ≠ Investigation Owner) | `POST /discrepancies/{id}/approve` |
| FR-104 (Completion Rule immutable) | `PATCH /tasks/{id}` |
| FR-107 (≥1 Primary Owner) | `POST /tasks`, `DELETE /tasks/{id}/owners/{user_id}` |
| FR-165 (mandatory notification non-mutability) | `PATCH /notification-preferences` |
| FR-175–177 (KPI RAG/rounding/missing-data) | `GET /kpis/{id}`, `GET /scorecards/{id}` (response fields, computed by Rule Engine, not a distinct endpoint) |
| FR-110 (subtasks/checklist items, completion roll-up) *(v1.1)* | `POST /checklist-instances/{id}/items/{item_id}/respond`, `GET /checklist-instances/{id}` (`pct_items_complete`) |
| FR-111 (recurring generation) *(v1.1)* | System-triggered (Checklist Scheduler, Architecture.md §5.7); no direct create endpoint — mirrors `POST /scorecards/generate`'s system-triggered pattern |
| FR-179–188 (Event Time capture) *(v1.2)* | `POST /observations` (body fields), `GET /reports/event-time` |
| FR-191–210 (Security hardening) *(v1.3)* | Cross-cutting — enforced on every endpoint per §1/§2 (rate limiting, CORS, headers, TLS); not endpoint-specific |
| FR-211–230 (ERP/third-party integration) *(v1.4)* | Section 16a (`/integrations/v1/...`, `/integration-partners`) |
| FR-231–237 (Multi-Level Discrepancy Approval) *(v1.5)* | `POST /discrepancies/{id}/approvals/{level}/approve`, `PATCH /discrepancy-categories/{id}/approval-chain` |
| FR-238–243 (Holiday Calendar) *(v1.5)* | Section 14b (`/holiday-calendar`, `/schools/{id}/working-days`) |
| FR-244–249 (Asset Lifecycle) *(v1.5)* | Section 14c (`/assets/{id}/retire`, `/reactivate`) |
| FR-250–255 (Compliance Scheduler) *(v1.5)* | Section 15a (`/scheduler-runs`), `GET /observations/pending-compliance` |
| FR-256–262 (Duplicate Detection) *(v1.5)* | `POST /observations` (409 contract), `POST /observations/{id}/override-duplicate`, `GET /reports/duplicate-observations` |
| FR-263–270 (Grace Period & Reopen) *(v1.5)* | `POST /observations/{id}/reopen-request`, `POST /observations/{id}/reopen-approve`, `GET /reports/grace-period-reopen` |
| FR-271–274 (Evidence Retention/Deletion) *(v1.5)* | Section 14d (`/observations/{id}/evidence/status`, `/evidence/delete`) |

---

## 18. Next Step: Machine-Readable OpenAPI

This document is a markdown endpoint catalogue — sufficient for architecture review and developer onboarding, but not directly importable into API tooling (Postman, codegen, contract testing). If useful, the natural next artifact is an `openapi.yaml` (OpenAPI 3.1) generated from these same endpoints, with full request/response schemas pulled from Data-Model.md's field definitions. That's a larger, more mechanical artifact worth generating separately once the endpoint shapes here are reviewed and stable — no point generating detailed schemas for an endpoint list that's still likely to shift in review.

---

## 19. Open API Questions

| # | Question | Owner |
|---|---|---|
| AQ-API1 | Confirm whether Checker peer-level task creation ("Checker (peer, if enabled)" in PRS §12) is a Configuration Engine flag or a fixed permission — affects whether `POST /tasks` authorization is static or config-resolved per request. | Product |
| AQ-API2 | Confirm export job polling vs. webhook-notify-on-completion for `/exports/{job_id}` — polling is simpler for Phase 1, webhook is more consistent with Section 16's event model. | Engineering |
| AQ-API3 | Confirm rate-limit thresholds per endpoint class (list vs. write vs. export) — not specified in PRS §46, needed before this becomes a binding contract. | Engineering + Infra |
| AQ-API4 | Confirm whether `GET /search` should be scope-restricted identically to direct module access (PRS §51 says yes) even for SuperAdmin's cross-school search — i.e., does "identical scope enforcement" mean SuperAdmin's search still respects an explicit school filter if provided, or always searches all schools by default. | Product |
| AQ-API5 *(v1.1)* | Confirm whether `POST /checklist-instances/{id}/verify` is mandatory for all templates or only those flagged as safety-critical (e.g., Fire Safety, Electrical) — affects whether `verify` is a universal step or a per-template-configured optional one. | Product |
| AQ-API6 *(v1.1)* | Confirm whether item-level responses (`.../items/{id}/respond`) can be submitted individually as the Checker progresses through the checklist, or must be submitted as one batched payload with `POST /checklist-instances/{id}/complete` — affects offline-resilience given BR-16/C7's online-only constraint (Architecture.md §17). | Product + Engineering |
| AQ-API7 *(v1.5)* | Confirm the exact HTTP status/contract for `POST /discrepancies/{id}/approvals/{level}/approve` when called out of order (e.g., Level 2 attempted before Level 1 is Approved) — this doc assumes `422` consistent with other out-of-order Workflow Engine transitions (§9), but the PRS doesn't state it explicitly for the multi-level case. | Engineering |
| AQ-API8 *(v1.5)* | Confirm whether `POST /observations/{id}/override-duplicate` should accept a fresh `Idempotency-Key`/full observation payload, or should reference the originally-rejected submission by a short-lived token returned in the `DUPLICATE_DETECTED` error body — affects whether the client needs to resend the full payload or just confirm. | Engineering |
| AQ-API9 *(v1.5)* | Confirm whether `/integrations/v1/...` should be a fully separate API Gateway deployment from `/v1/...` (stronger isolation, matches §41.6's "independent" rate limiting) or the same deployment with path-based routing and separate rate-limit buckets — affects infra sizing, not the contract itself. | Engineering + Infra |

---

*End of Document.*
