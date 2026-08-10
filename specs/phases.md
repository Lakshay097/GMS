# Phases.md — School Operations & Governance Platform

Consolidated delivery roadmap combining the PRS Roadmap (§57), the Architecture Evolution Roadmap (§22), and the underlying scope/constraint sections. This is the single reference for "what ships when."

**v1.5 update note:** PRS v1.5 closed seven of the ten open gap-analysis items carried into Phase 1 scope: Multi-Level Discrepancy Approval, Holiday Calendar & Non-Working-Day Policy, Phase 1 Asset Lifecycle/Status, a Compliance Scheduler, Duplicate Observation Prevention, Missed-KPI Grace Period, and Evidence Retention Configuration (BR-21–27, FR-231–274). All seven are now fully specified and **remain in Phase 1** — none of them push scope into Phase 2/3. This revision updates Phase 1's functional/architecture/data scope, exit criteria, and the open-items table below accordingly.

---

## 0. How the Roadmap Is Structured

Three parallel tracks move together at each phase:

1. **Product/Functional track** — which modules and business capabilities are live (PRS §57).
2. **Architecture track** — which platform services and integration seams exist (Architecture §22).
3. **Data track** — which entities, versioning, and partitioning strategies are active (Data-Model §9–10).

Feature Flags (PRS §54) are the release mechanism used throughout — they decouple *deploy* from *release*, so later-phase code can merge early and be enabled per school without a redeploy.

---

## Phase 1 — Foundation (This Specification, Build Now)

**Goal:** Replace manual/paper/Excel KRA-KPI tracking with a fully digital, auditable governance platform for a single organization across multiple schools.

### 1.1 Functional Scope
- School, Department, User, Role Management (multi-school, strict data isolation).
- Global KPI Library — centrally governed, versioned (SuperAdmin-owned).
- KRA Management, with 1:1 KPI-to-KRA ownership.
- Observation Capture (Checker role) with configurable immutability lock period.
- Independent Audit/Verification workflow (Auditor role) — never edits Observations.
- Discrepancy Management: Discrepancy → Investigation → Resolution → Approval (category-driven, up to two sequential levels) → Closure. *(v1.5: multi-level, category-routed approval chains, BR-21.)*
- Holiday Calendar & Non-Working-Day Policy: Organization/School-scoped holiday calendar and per-KPI Working Days override, with Skip/Shift-Forward/Shift-Backward handling when a compliance due date falls on a non-working day. *(v1.5, BR-22.)*
- Compliance Scheduler: idempotent, timezone-aware, backfilling background generation of recurring KPI compliance records — never generated lazily at first access. *(v1.5, BR-24.)*
- Duplicate Observation Prevention: block/override detection for a second Observation against the same KPI/scope/Checker/occurrence within a configurable window. *(v1.5, BR-25.)*
- Missed-KPI Grace Period: late-but-still-submittable window after a due date, transitioning to Closed-Missed and a governed Reopen-Request/Approval flow once the window elapses. *(v1.5, BR-26.)*
- Phase 1 minimal Asset Lifecycle: Active/Retired status on Asset records, preventing new assignment of a Retired Asset without breaking historical Observation references. *(v1.5, BR-23.)*
- Task Management: multiple Primary Owners, configurable completion rules, ETA governance (3-extension cap, auto-escalation on breach).
- Configurable, per-department Escalation Matrix with SLA timers.
- Performance Reviews & Scorecards — periodic, immutable, versioned.
- Role-based Dashboards.
- Report Catalogue (full list — PRS §50) and export (Excel, CSV, PDF, REST API).
- Notification system — in-app, email, SMS, WhatsApp; fixed priority order; mandatory categories non-mutable.
- Full Audit Logging across all modules.
- English + Hindi localization.
- Documented REST API layer (no live external ERP integration yet — contract-ready only).
- Evidence Retention Configuration: configurable retention period (default 7 years) and archive-tier threshold (default 1 year) for Observation evidence, with deletion always an explicit, logged Admin/SuperAdmin action — never automated. *(v1.5, BR-27.)*

### 1.2 Explicitly Out of Scope for Phase 1
- Native iOS/Android apps (responsive web / PWA only).
- Offline data capture or sync (online-only, BR-16/C7).
- Weighted KPI scoring model (worst-status-wins only in Phase 1).
- Full ERP/HRMS integration (payroll, admissions, fees, master identity).
- Vendor/procurement financial workflows beyond basic vendor record-keeping.
- Self-service School registration (SuperAdmin-only creation in Phase 1).
- Asset Management, Visitor Management, Procurement, Leave Management, Maintenance, Incident Reporting, CAPA, full Vendor Management.

### 1.3 Architecture Delivered in Phase 1
- **Modular monolith**, service-oriented internally (ADR-01), deployed as a small number of horizontally scaled units (AP6).
- Six cross-cutting platform services live: Configuration Engine, Rule Engine, Workflow Engine, Notification Service, Audit Log Service, Master Data Service — plus the Checklist Scheduler (§5.7, v1.1 addition) and the Compliance Scheduler (§5.8, v1.5 addition) generating recurring KPI compliance records with the same idempotent, timezone-aware, backfilling pattern the Checklist Scheduler established.
- Workflow Engine's Discrepancy state machine now supports a category-driven, up to two-level Approval Chain (v1.5, BR-21) rather than a single fixed Approval state — still data-defined, no engine change required to add or reconfigure a chain.
- Shared database, row-level tenant isolation (ADR-02) — Neon (serverless Postgres) as primary datastore and identity provider (Neon Auth), Cloudinary for media/document evidence (ADR-07).
- REST API (`/v1/...`), OpenAPI-documented, permission-parity with UI, idempotency keys on write endpoints (mandatory for Observation submission).
- Immutability enforced at the DB grant/trigger layer for Observations, KPI versions, Scorecards, Audit Log (ADR-04).
- Data-defined (configurable) state machines via the Workflow Engine for Discrepancy, Task, and Checklist Instance lifecycles (ADR-03).
- Async job queue for notification dispatch, report exports, and scheduled jobs (reminders, escalation checks, scorecard generation, checklist generation).
- Dev/Staging/Production environment separation; CI/CD with automated acceptance-test execution; Feature Flags for phased rollout.

### 1.4 Data Delivered in Phase 1
- Core entities: `schools`, `departments`, `users`, `kras`, `kpis`, `observations`, `discrepancies`, `tasks`/`task_owners`, `scorecards`.
- Supporting entities: `roles`/`user_roles`, `escalation_rules`, `notifications`, `master_data_entries`, `user_school_grants`, `vendors`/`assets` (record-keeping, with an Active/Retired status field — v1.5, BR-23).
- Checklist & Recurring Task schema (`ChecklistTemplate`, `ChecklistInstance` and items) — v1.1 addition, generated by the Checklist Scheduler.
- Discrepancy Approval schema (`discrepancy_categories`, `discrepancy_approval_chains`, `discrepancy_approvals`) — v1.5 addition, replaces the single `approver_id` column with a per-level approval history child table (BR-21, FR-237).
- Holiday Calendar & Working Days schema (`holiday_calendar_entries`, per-School/per-KPI Working Days config) — v1.5 addition, feeding the Compliance Scheduler (BR-22).
- Observation schema extended with duplicate-detection fields (`duplicate_override_flag/justification/original_observation_id`), Compliance Status shell fields (`compliance_status`, `grace_period_elapsed_at`, `reopen_requested_by/reason/approved_by`, `reopened_flag`), and Evidence Storage Tier — v1.5 addition (BR-25, BR-26, BR-27).
- Cross-cutting tables: `configuration_items`/`configuration_overrides`, `audit_log_entries`, logical `search_index`.
- Versioning scheme active for KPIs, Scorecards, Checklist Templates/Instances, and Discrepancy Approval Chain Configuration (v1.5 — an in-progress Discrepancy binds to the chain version active when it entered Approval, BR-21/FR-235).

### 1.5 Phase 1 Exit Criteria
- All 27 Business Rules (BR-01–BR-27) have ≥1 automated test.
- All FR-001–FR-274 (FR-001–230 from v1.0–v1.4, plus FR-231–274 added in v1.5) traceable to ≥1 acceptance test.
- Every cross-module workflow (Observation→Audit→Discrepancy→Investigation→Approval Chain→Closure; Task→ETA→Escalation→Completion; KPI→Scheduler→Observation→Grace Period→Scorecard) completes end-to-end in staging without manual data patching.
- Success Metrics baseline captured at Pilot exit (PRS §4): audit prep time < 30 min, KPI submission rate > 98%, overdue tasks < 5%, discrepancy SLA adherence > 95%, Level-1 escalation response < 24h, user adoption ≥ 85% by Pilot exit.
- Stakeholder Decisions D1–D9 (PRS §17, renamed/renumbered from Open Questions Q1–Q10 in v1.5 — see below) and Architecture Open Questions AQ1–AQ5 resolved or explicitly deferred with sign-off.

---

## Phase 2 — Integration & Refinement

**Trigger:** Phase 1 exit criteria met, 90-day post-rollout metrics reviewed (PRS §4).

### 2.1 Functional Scope
- Weighted KPI scoring model (in addition to Phase 1's worst-status-wins).
- Self-service School registration with an approval workflow (supersedes SuperAdmin-only creation, BR-03 future phase).
- School-customizable role templates.
- School-level Master Data overrides.
- Scheduled/recurring report delivery.
- Procurement/PO management extension to the Vendor module.
- Live ERP integration activation for Users/Departments/Schools (BR-19 — ERP becomes master for these three entities; platform remains master for Tasks, Compliance, Audits, Discrepancies, KPIs, Performance).

### 2.2 Architecture Moves
- Activate ERP inbound sync as an **event-consuming integration** (Architecture §11) — built on the Phase 1 API/event contract, not a rebuild.
- Introduce weighted KPI scoring as a second Rule Engine strategy, alongside worst-status-wins (Architecture §5.2).
- Add school-level Master Data overrides as a new Configuration Engine scope tier (Architecture §5.1).
- Confirm SSO provider/protocol ahead of/at this phase (AQ5) to support ERP-integration authentication needs.

### 2.3 Dependencies Carried From Phase 1
- BR-19/A7 master-data ownership boundary must already be documented and enforced in the API contract.
- Feature Flags from Phase 1 are the mechanism for enabling Phase 2 capabilities per school without a full redeploy.

---

## Phase 3 — Expansion

**Trigger:** Phase 2 stable in production; real production load data available to justify service-extraction decisions.

### 3.1 Functional Scope (New Modules)
- Asset Management
- Visitor Management
- Procurement (full)
- Leave Management
- Maintenance
- Incident Reporting
- CAPA (Corrective and Preventive Action)
- Vendor Management (full, beyond Phase 1 record-keeping)
- Root-cause categorization and CAPA linkage for Discrepancies (PRS §26.13).
- AI-assisted audit queue prioritization (PRS §25.13).
- Comparative cross-school benchmarking scorecards (PRS §29.13).

### 3.2 Architecture Moves
- Evaluate **service extraction** for the highest-load modules — Observation Capture and Notification Service first, given expected volume — now backed by real production load data (module boundaries from Architecture §4 make this a deployment-topology change, not a redesign, per ADR-01).
- Add new Workflow Engine state machines for CAPA, Incident Reporting, and other new modules **without engine changes** — this is the payoff of the data-defined transition model chosen in ADR-03/Architecture §13.

---

## Cross-Phase (Architecture-Level, Not Phase-Bound)

These platform capabilities are designed in Phase 1 specifically so later phases don't require re-architecture (PRS §57.4 / Objective O7):

| Capability | Phase 1 State | Why It Doesn't Need Re-Architecture Later |
|---|---|---|
| Configuration Engine | Live, centralizes lock periods, SLA thresholds, ETA limits, tolerance bands | New config scope tiers (e.g., school-level overrides in Phase 2) are additive |
| Rule Engine | Live with worst-status-wins strategy | Weighted scoring (Phase 2) is a second strategy, not a rewrite |
| Workflow Engine | Live, data-defined state machines for Discrepancy/Task/Checklist | New entities (CAPA, Incident Reporting in Phase 3) plug into the same engine |
| Notification Service | Live, async, multi-channel | Extraction candidate in Phase 3 once volume justifies it |
| Audit Service | Live, single shared append-only sink | No change needed across phases — it's the constant |
| Master Data Service | Live, forward-only reference data | School-level overrides (Phase 2) are a new scope tier, not new logic |
| Integration Layer | REST API + event contract, no live consumers | Phase 2 ERP sync activates against the same contract |
| Feature Flags | Live from Phase 1 | The rollout mechanism for every subsequent phase |
| Compliance Scheduler *(v1.5)* | Live, idempotent, timezone-aware, holiday-aware recurring generation | Same pattern the Checklist Scheduler already established; no new generation model needed for future recurring-record types |
| Discrepancy Approval Chain (Workflow Engine) *(v1.5)* | Live, data-defined, up to 2 levels per Category | Additional levels or categories are configuration, not an engine change |

---

## Risk-to-Phase Mapping

| Risk (PRS §16) | Phase Where It's Most Live |
|---|---|
| Low Checker adoption | Phase 1 (training, vernacular UI, in-app champion model) |
| Missing/incomplete capture data | Phase 1 (mandatory-field validation) |
| No-offline network dependency | Phase 1 (client retry/resubmit pattern); revisit if offline is ever requested |
| ERP master-data conflicts | Phase 2 (BR-19 boundary, integration layer) |
| Scope creep toward Phase 2/3 | Phase 1 (explicit out-of-scope list + Feature Flags as the guardrail) |
| Sensitive/financial KPI exposure | Phase 1 ongoing (category-level permission overrides, encryption) |
| Scorecard/versioning trust | Phase 1 (data-layer immutability enforcement) |

---

## Open Items Gating Phase Entry

**v1.5 renumbering:** PRS Section 17 was rewritten from "Open Questions" (Q#) to "Stakeholder Decisions Required Before Phase 1 Sign-off" (D#) — every item with a single defensible engineering answer (including the former Q7 self-service-registration-phasing item, resolved to Phase 2 as recommended) is now resolved in-spec. The table below uses the current D# numbering; items without a D# are unchanged architecture questions (AQ#).

| Item | Blocks | Owner |
|---|---|---|
| D1 (was Q3) — Marketing/Telecaller KPIs stay on-platform vs. separate CRM | Phase 1 KPI Library scope | Product |
| D5 (was Q8) — performance/scalability hard targets | Phase 1 deployment sizing | Infra |
| D7 (was Q10) — Event Time Auto-Capture vs. Manual-only matrix | Phase 1 Event Time architecture | Product, hardware/vendor timeline |
| D9 (new, v1.5) — expand Asset Lifecycle beyond Phase 1 minimal Active/Retired? | Confirms Phase 1 vs. Phase 3 Asset Management boundary | Business stakeholders |
| AQ1 (partial) — application-tier compute hosting platform | Phase 1 deployment | Infra |
| AQ2 — Observation table partitioning strategy | Phase 1 performance tuning, informs Phase 3 extraction planning | Engineering, pending D5 |
| AQ3 — message queue technology | Phase 1 escalation-timer and Compliance Scheduler reliability | Engineering |
| AQ4 — DPDP erasure vs. retention exemption | Phase 1 compliance sign-off (now also governs Evidence Retention deletion workflow, BR-27) | Legal/Compliance |
| AQ5 — SSO provider/protocol | Phase 2 ERP integration auth | ERP integration owner |

**Resolved at v1.5, removed from this table:** self-service registration phasing (was Q7, resolved to Phase 2 per D-recommendation above), and all seven gap-analysis items (approval chains, holiday calendar, asset status, scheduler behavior, duplicate prevention, grace period, evidence retention) — fully specified in Sections 1.1, 1.3, and 1.4 above and require no further Phase 1 gating.
