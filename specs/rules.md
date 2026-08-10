# Rules.md — School Operations & Governance Platform

Consolidated rulebook derived from the PRS (v1.5), Architecture Specification, Data Model Specification, and API Specification. This is the single reference for "what must always be true" — business rules, validation rules, permission rules, and data/architecture enforcement rules — grouped by theme rather than by document section, so engineering, QA, and product can use one source when implementing or testing.

**v1.5 update note:** PRS v1.5 closed seven gap-analysis items (Q12–Q15, Q17–Q19) that were open at v1.1/v1.4: Multi-Level Discrepancy Approval (BR-21), Holiday Calendar & Non-Working-Day Policy (BR-22), Phase 1 Asset Lifecycle/Status (BR-23), Compliance Scheduler (BR-24), Duplicate Observation Prevention (BR-25), Missed-KPI Grace Period (BR-26), and Evidence Retention Configuration (BR-27). This revision adds Sections 9a–9g (rules R-62–R-89 below) and updates every count/total that referenced "20 Business Rules" or "FR-001–FR-177" elsewhere in this document. Rule numbers R-01–R-61 are unchanged from v1.1 and keep their original source citations.

---

## 1. How to Read This Document

- **BR-xx** = Business Rule (PRS §9) — final, approved, binding.
- **C#** = Constraint (PRS §8).
- **AP#** = Architecture Principle (Architecture §1).
- **ADR-xx** = Architecture Decision Record (Architecture §20).
- Every rule below is traceable back to its source document/section so it can be re-verified against the originals.
- Where a rule is enforced in more than one layer (UI + API + DB), all layers are listed — the platform's core acceptance criterion is that **immutability and scope rules are never UI-only** (PRS §55, AP2).

---

## 2. Tenancy & Scope Rules

| Rule | Statement | Source |
|---|---|---|
| R-01 | A user belongs to exactly one School, except SuperAdmin (all schools) and Viewer (may be granted multiple schools). | BR-01, C1 |
| R-02 | Scope isolation (School/Department) is enforced as a mandatory query-layer filter, applied **before and independent of** role-permission checks. | AP4, Architecture §6 |
| R-03 | Tenancy model is shared application, shared database, row-level isolation (`school_id`, `department_id` on every tenant-scoped table) — not database-per-school. | Architecture §6, ADR-02 |
| R-04 | SuperAdmin/Viewer multi-school access is modeled as explicit scope-grant records, not a bypass of the scope filter — the filter always runs. | Architecture §6 |
| R-05 | Only SuperAdmin can create Schools in Phase 1. | C2, BR-03 |
| R-06 | A School cannot see another School's data by default. | PRS §13 |
| R-07 | A Department belongs to exactly one School. | PRS §19.5 |
| R-08 | A user may hold multiple roles concurrently within their one school (e.g., Principal = Admin + Viewer). | BR-02 |

## 3. Lifecycle & Deletion Rules

| Rule | Statement | Source |
|---|---|---|
| R-09 | **No hard deletes, anywhere.** Every entity lifecycle ends in Archived, Deprecated, or Superseded — never a DELETE statement against business data. | AP7, C4, PRS §47/§55 |
| R-10 | Schools cannot be deleted — only Deactivated; historical data remains read-only and reportable. | PRS §18.5, §18.11 |
| R-11 | Departments cannot be deleted once historical Observation/Task records exist — Archive only. Archival is blocked while open Tasks or unresolved Discrepancies exist. | PRS §19.5–19.6 |
| R-12 | Users are never hard-deleted; they are archived, login is disabled, full audit history is retained permanently. | BR-08, C4 |
| R-13 | Archived records remain searchable and read-only; never editable. | BR-18 |
| R-14 | Master Data changes are forward-only: existing records keep referencing the enumeration value active at their creation time (never retroactively repointed). | PRS §35.5, Architecture §5.6 |

## 4. Immutability & Versioning Rules

| Rule | Statement | Source |
|---|---|---|
| R-15 | Immutability is enforced **at the data layer** (DB grants/triggers/constraints), never solely in the UI or application conditionals. | AP2, ADR-04, PRS §55 |
| R-16 | **Observations**: mutable only until the configured Lock Period elapses; after lock, no UPDATE is possible. Corrections after lock create a *new* Observation referencing the original — never an edit. | BR-11, C5, Data-Model §8.1 |
| R-17 | **KPIs** are version-controlled: any edit to Target/Comparator/Unit creates a new version/ID; the prior version is never updated once any Observation references it. Historical reports always resolve against the KPI version active at the time of the reading. | BR-05, BR-06 (one KPI ↔ one KRA, never multiple), Data-Model §8.2 |
| R-18 | **Scorecards** are generated, never updated. Recalculation produces a new version (`v2`); the prior version (`v1`) is retained and marked `superseded_by`; no application role holds UPDATE/DELETE grants on generated scorecard rows. | BR-14, C6, Data-Model §8.3 |
| R-19 | **Audit Log** is append-only at the database grant level — no UPDATE/DELETE grants exist for any application role, on any environment. This is the strongest immutability guarantee in the system, since it underwrites every other immutability claim. | Architecture §5.5, §8.4 |
| R-20 | **Checklist Templates/Instances** follow the same versioning philosophy as KPIs: template edits version forward; instances reference the template version active at generation time. | Architecture §8.5, ADR-06 |
| R-21 | A submission against a Deprecated KPI version is blocked at validation. | PRS §52 |

## 5. Observation, Audit & Discrepancy Rules

| Rule | Statement | Source |
|---|---|---|
| R-22 | Checkers never edit business records — they only capture Observations. They cannot edit audit data. | BR-11 |
| R-23 | An Observation is always captured against a specific KPI (and transitively its owning KRA); an Observation with no linked KPI is never permitted. | BR-20 |
| R-24 | Auditors never edit Observations. An Auditor may only Verify an Observation or raise a Discrepancy against it — the original Observation is never altered. | BR-12, C5 |
| R-25 | Discrepancy lifecycle is strictly linear: **Discrepancy → Investigation → Resolution → Approval → Closed.** No skipped states. | BR-13, FR-090, Architecture §13 |
| R-26 | Investigation findings are required before a Discrepancy can move to Resolved. | PRS §52 |
| R-27 | Segregation of duties: the Discrepancy Approver must not be the same person as the Investigation Owner. | PRS §52, Architecture §10/§13 |
| R-28 | Observation values must be type-matched to the KPI's declared Unit; evidence format/size is validated at submission. | PRS §52 |
| R-29 | Auto-Result (Met / Not Met / N/A) is a system computation comparing Observation value to KPI Target via its Comparator (∈ {≥, ≤, =, <, >}) — never a manual entry. | PRS §15 glossary, §52 |

## 6. Task & Escalation Rules

| Rule | Statement | Source |
|---|---|---|
| R-30 | A Task must have ≥1 Primary Owner; there are no "collaborators." Every Primary Owner receives notifications, reminders, and escalations. | BR-09 |
| R-31 | Task completion rule is configurable per task at creation and is **immutable after creation**: ANY owner completes / ALL owners must complete / completion requires post-completion approval. | BR-09, PRS §52 |
| R-32 | ETA must be in the future at Task creation. | PRS §52 |
| R-33 | Maximum of **three** ETA extensions per Task instance. A fourth extension request automatically triggers escalation instead of being granted — this cap is a fixed governance rule, not configurable. | BR-10, C8, PRS §54 |
| R-34 | No offline mode is designed or supported; the system requires an active internet connection at all times. | BR-16, C7, A1 |

## 7. KPI Calculation Rules (§23.14 / FR-175–177)

| Rule | Statement | Source |
|---|---|---|
| R-35 | KPI results are computed via one of the platform's supported formula types, using the Comparator and Target defined on the active KPI version. | PRS §23.14–15 |
| R-36 | Missing-data handling and rounding behavior are defined per KPI and resolved through the Configuration Engine / Rule Engine — not hardcoded per module. | PRS §23.14, AP1, Architecture §5.2 |
| R-37 | RAG (Red/Amber/Green) status uses a configurable **KPI Amber Tolerance Band** — global default, overridable per KPI category (e.g., stricter/zero tolerance for safety-related KPIs, pending Q9 confirmation). | PRS §54, Q9 |

## 8. Notification Rules

| Rule | Statement | Source |
|---|---|---|
| R-38 | Fixed priority order, always: (1) Escalation, (2) Audit Failure, (3) Task Assignment, (4) Due Today, (5) KPI Reminder, (6) Comments, (7) Informational. | BR-15 |
| R-39 | Mandatory categories (1 — Escalation, 2 — Audit Failure) **cannot be muted** by users, regardless of client request path — enforced server-side. | BR-15, C9, FR-165, PRS §52 |
| R-40 | Notification dispatch is asynchronous via a job queue — never synchronous/inline with the triggering request, so a slow SMS/WhatsApp provider cannot block unrelated requests. | ADR-05, Architecture §5.4 |

## 9. Configuration & Governance Rules

| Rule | Statement | Source |
|---|---|---|
| R-41 | Configurable governance values (Observation Lock Period, Escalation SLA per level, Reminder Frequency, Performance Review Cadence, Session Timeout, File Upload Limits, Locales, Feature Flags, KPI Amber Tolerance Band) live in the Configuration Engine, not hardcoded per module. | AP1, PRS §54 |
| R-42 | Max ETA Extensions (3, per R-33/BR-10) is the one governance value that is **not overridable** — fixed by business rule, not configuration. | PRS §54 |
| R-43 | Only SuperAdmin can modify the Global KPI Library; Schools cannot create their own KPI libraries. | BR-04, C3 |
| R-44 | Only SuperAdmin manages Global Configuration; school-scoped subsets are delegable to Admin only where explicitly noted (e.g., Lock Period, Escalation SLA, Reminder Frequency, Review Cadence — see PRS §54 table). | PRS §54 |
| R-45 | Employee transfer between departments updates the *current* assignment; historical records remain attributed to the prior department. | BR-07 |
| R-46 | ERP (once integrated, Phase 2+) becomes master for Users, Departments, Schools; this platform remains master for Tasks, Compliance, Audits, Discrepancies, KPIs, and Performance. | BR-19, A7 |

## 9a. Discrepancy Multi-Level Approval Rules *(v1.5, Q15)*

| Rule | Statement | Source |
|---|---|---|
| R-62 | A Discrepancy carries a Discrepancy Category (FK to Master Data), set at creation and immutable thereafter. | BR-21 |
| R-63 | The Discrepancy's Approval stage follows the Approval Chain configured for its Category (1–2 sequential levels in Phase 1); the chain's Role-per-level is resolved at runtime, never hardcoded in the workflow engine. | BR-21, FR-232 |
| R-64 | An in-progress Discrepancy binds to the Approval Chain Configuration version active when it entered the Approval stage; later configuration changes never retroactively apply to it. | BR-21, FR-235 |
| R-65 | Each approval level's Approver must differ from the Investigation Owner and from every Approver at a prior level on the same Discrepancy (segregation of duties extended across levels, generalizing R-27). | FR-233 |
| R-66 | A Discrepancy cannot Close until every configured approval level has reached Approved status. | FR-234 |

## 9b. Holiday Calendar & Non-Working-Day Rules *(v1.5, Q18)*

| Rule | Statement | Source |
|---|---|---|
| R-67 | Compliance-cycle generation respects an Organization Holiday Calendar (org-level default, School-scoped override) and, where configured, a per-KPI Working Days override. | BR-22 |
| R-68 | A KPI due on a non-working day is handled per its configured Non-Working-Day Policy — Skip, Shift Forward, or Shift Backward — never silently generating a due/overdue record on a day the school is closed. | BR-22, FR-240 |
| R-69 | The Non-Working-Day Policy is set per KPI at creation and is immutable for that KPI version, consistent with KPI versioning (R-17). | FR-241 |
| R-70 | No more than one compliance record is ever generated for a single logical occurrence, regardless of how many consecutive non-working days precede or follow it. | FR-242 |
| R-71 | A School with no Holiday Calendar configured falls back to the organization-level default; if that is also empty, all days are treated as working days (fail-open). | PRS §23.12 |

## 9c. Asset Lifecycle Rules (Phase 1 Minimal) *(v1.5, Q19)*

| Rule | Statement | Source |
|---|---|---|
| R-72 | An Asset is never hard-deleted. Decommissioning sets Status = Retired, preserving all historical Observations, Event Time records, and reports referencing it. | BR-23 |
| R-73 | A Retired Asset cannot be newly assigned to a KPI's Event Time Point scoping or to a new Observation; re-activation (Status → Active) is permitted and does not affect historical continuity. | BR-23, FR-245 |
| R-74 | An in-flight Observation binds to the Asset Status active when data entry began (mirrors R-17's version-binding pattern). | FR-249 |

## 9d. Compliance Scheduler Rules *(v1.5, Q17)*

| Rule | Statement | Source |
|---|---|---|
| R-75 | Recurring KPI compliance records are generated automatically by a background scheduler, never on-demand at first user access. | BR-24 |
| R-76 | Scheduler generation is idempotent: a given logical occurrence (KPI version + scope + due date) is never generated more than once, across retries, backfills, or overlapping runs — enforced by a database-level uniqueness constraint, not application-level locking alone. | BR-24, FR-252 |
| R-77 | Generation computes due dates and cycle boundaries using each School's configured timezone, never server-local time or UTC. | BR-24, FR-251 |
| R-78 | If the scheduler misses a run, the next successful run detects and backfills all missed occurrences, each dated to its correct original due date, without degrading normal-day generation performance. | FR-253 |

## 9e. Duplicate Observation Prevention Rules *(v1.5, Q14)*

| Rule | Statement | Source |
|---|---|---|
| R-79 | A duplicate Observation — same KPI version, scope, Event Time Point (if applicable), and Checker, submitted within a configurable Duplicate Detection Window of a prior Observation for that occurrence — is blocked by default. | BR-25 |
| R-80 | A user holding Override permission may submit past a detected duplicate block only after providing a mandatory justification, which is retained with the record along with a reference to the original Observation. | BR-25, FR-258–259 |
| R-81 | Duplicate detection is independent of, and in addition to, submission-token idempotency (R-54/FR-069) — the two checks catch different failure modes (a retried request vs. a genuinely second, distinct submission). | FR-260 |
| R-82 | Duplicate detection is scoped to the same Checker by default (to avoid false-blocking legitimate shift handoffs); a School may configure it to be Checker-agnostic for stricter control. | PRS §24.12 |

## 9f. Missed-KPI Grace Period Rules *(v1.5, Q12)*

| Rule | Statement | Source |
|---|---|---|
| R-83 | A compliance record whose due date has passed without a submitted Observation remains submittable, flagged Late, until a configurable Grace Period elapses — no Admin action required within the window. | BR-26 |
| R-84 | Once the Grace Period elapses, the record transitions to Closed-Missed; direct Checker submission is blocked, and only an Admin/SuperAdmin-approved Reopen Request restores submittability. | BR-26, FR-264–266 |
| R-85 | A post-reopen submission is distinctly flagged as both Late and Reopened, separate from an ordinary within-window Late submission. | FR-267 |
| R-86 | For a backfilled record, the Grace Period is evaluated relative to the record's original due date, extended by the scheduler-outage duration (configurable) so a scheduler failure never penalizes a Checker. | FR-269 |

## 9g. Evidence Retention Rules *(v1.5, Q13)*

| Rule | Statement | Source |
|---|---|---|
| R-87 | Evidence files are retained for a configurable Evidence Retention Period, defaulting to 7 years from the Observation's Submitted At date. | BR-27, FR-271 |
| R-88 | After a configurable Archive Tier Threshold (default 1 year), evidence files move to lower-cost archival storage but remain retrievable on demand under the same access-control and encryption-at-rest requirements as active-tier files. | FR-272, PRS §41 |
| R-89 | Evidence files are never automatically deleted. After the Evidence Retention Period elapses, files become eligible for deletion, but actual deletion requires an explicit, logged Admin/SuperAdmin action — the platform runs no automated purge process. | BR-27, FR-273–274 |

## 10. Permission & Authorization Rules

| Rule | Statement | Source |
|---|---|---|
| R-47 | The Permission Matrix (PRS §12) applies identically at the API layer as at the UI layer — there is no separate, looser API permission model. | AP5, PRS §39/§43, Architecture §9 |
| R-48 | Every request re-evaluates permissions and scope at the point of execution (not cached/assumed from session start). | Architecture §9 |
| R-49 | Segregation-of-duties rules (e.g., Discrepancy Approver ≠ Investigation Owner, R-27) are enforced as workflow-engine guards, not UI hints. | FR-026, FR-092, Architecture §10/§13 |
| R-50 | Category-level export/view overrides (e.g., financial KPIs restricted from Viewer export) are configurable, per BR-04/BR-19. | PRS §12, §43 |

## 11. Validation Rules (PRS §52 Summary)

| Domain | Rule |
|---|---|
| Observation | Value required; type-matched to KPI Unit; evidence format/size validated; blocked against a Deprecated KPI version. |
| Task | ≥1 Primary Owner; ETA future at creation; Completion Rule immutable after creation. |
| KPI | Comparator ∈ {≥,≤,=,<,>}; exactly one KRA reference; Frequency from supported enumeration. |
| Discrepancy | Investigation findings required before Resolved; Approver ≠ Investigation Owner. |
| User | Unique email/phone; ≥1 active Role; single-School constraint unless SuperAdmin/Viewer. |
| Notification | Mandatory categories cannot be disabled server-side, regardless of client request path. |
| School | Name unique within the organization; cannot go Active until departments + KPI library import succeed. |
| Department | Name unique within a School; cannot archive with open Tasks/unresolved Discrepancies. |

## 12. Error Handling & Idempotency Rules

| Rule | Statement | Source |
|---|---|---|
| R-51 | Every rejected operation returns a structured, machine-readable error (code, message, field reference). | PRS §53 |
| R-52 | Conflict errors (duplicate School name, concurrent audit action) return HTTP 409-equivalent semantics with a clear resolution path. | PRS §53 |
| R-53 | All error events affecting data integrity are logged to the Audit/Error Log. | PRS §53 |
| R-54 | Idempotency keys prevent duplicate record creation on client retry after a network failure; **required** for Observation submission specifically. | FR-069, PRS §53, Architecture §9 |
| R-55 | Checklist Instance generation is idempotent and deterministic: re-running the scheduler after a crash or double-fire produces zero duplicate instances, enforced by a uniqueness constraint on `(template_id, template_version, school_id, department_id, period_start)`. | Architecture §5.7 |

## 13. Security & Compliance Rules

| Rule | Statement | Source |
|---|---|---|
| R-56 | MFA is required at login for Admin and SuperAdmin roles. | PRS §41–42, Architecture §9 |
| R-57 | Data is encrypted in transit and at rest. | PRS §41, Risk mitigation table §16 |
| R-58 | The platform must support DPDP Act data-governance obligations (subject to legal confirmation of erasure vs. retention-exemption for audit-relevant records — AQ4). | PRS Stakeholders §5, Architecture AQ4 |

## 14. Export, Search & Reporting Rules

| Rule | Statement | Source |
|---|---|---|
| R-59 | Supported export formats: Excel, CSV, PDF, REST API. | BR-17 |
| R-60 | Search is permission-scoped identically to direct module access; saved filters are private by default; indexing lag target < 60 seconds. | PRS §51 |
| R-61 | Heavy report/dashboard generation is architecturally separated from write-path (transactional) workloads so it cannot degrade transactional response times. | Architecture §2, §14 |

## 15. Acceptance-Level Rules (Platform Gate)

These must hold true for the platform to be considered release-ready (PRS §55):

- No module permits a hard delete of School, User, Observation (post-lock), Discrepancy, Task (with history), Scorecard, or Asset with linked Observations.
- Every immutability rule (Observation lock, Scorecard version, KPI version, in-progress Discrepancy's Approval Chain version) is enforced at the data layer, not solely the UI.
- Every cross-module workflow (Observation → Audit → Discrepancy → Investigation → Approval Chain → Closure; Task → ETA → Escalation → Completion; KPI → Scheduler → Observation → Grace Period → Scorecard) completes end-to-end in staging without manual data patching.
- All 27 Business Rules (BR-01–BR-27) have at least one automated test case.
- All Functional Requirements (FR-001–FR-230, plus FR-231–FR-274 added in v1.5) are traceable to at least one acceptance test.

---

## 16. Open Rule Confirmations (Not Yet Final)

**v1.5 update:** PRS Section 17 was renamed and rewritten from "Open Questions" to "Stakeholder Decisions Required Before Phase 1 Sign-off" (D1–D9), because Q12–Q15 and Q17–Q19 — all items with a single defensible engineering answer — are now resolved in-spec (BR-21–27, Sections 9c–9g above). Only genuine business/policy decisions remain open, renumbered D1–D9. The table below is updated to match; engineering-facing architecture questions (AQ#) are unchanged and still pending.

| # | Open Item | Current Recommendation |
|---|---|---|
| D1 *(was Q3)* | Marketing/Telecaller KPIs: stay on-platform or integrate with a separate CRM | Keep in-platform initially |
| D2 *(was Q4)* | Notification channel approval — which events get SMS/WhatsApp, cost approval | Start with In-App + Email; add SMS/WhatsApp per event once cost approved |
| D3 *(was Q5)* | Minimum viable Global KPI Library taxonomy for schools without a supplied role manual | Finalize before development begins — highest priority |
| D4 *(was Q6)* | Escalation SLA durations — org-wide default vs. per-department override | Org defaults with department override (architecturally supported); needs actual SLA numbers |
| D5 *(was Q8)* | Performance/scalability hard targets (concurrent users, observation volume, availability SLA) | Pending infra confirmation |
| D6 *(was Q9)* | KPI Amber Tolerance Band — uniform default vs. per-category (e.g., zero tolerance for safety KPIs) | Per-category, Safety stricter/zero — needs stakeholder confirmation of exact bands |
| D7 *(was Q10)* | Event Time integration matrix — which Event Time Points get genuine Auto-Capture at go-live vs. Manual-only, and which are Auto-Capture-only | Decide before development — drives architecture |
| D8 *(new, v1.5)* | Should individual KPI ownership exist beyond Department-level assignment? | Recommend deferring — Department-level assignment + transfer history (FR-025) is adequate for Phase 1 |
| D9 *(new, v1.5)* | Should Asset Lifecycle expand beyond the Phase 1 minimal Active/Retired status (R-72–74)? | Recommend keeping full Asset Management in Phase 3 |
| — *(resolved, v1.5)* | ~~Q1 — Default Observation Lock Period~~ | Resolved: 24–48 hours confirmed |
| — *(resolved, v1.5)* | ~~Q2 — Default ETA extension duration~~ | Resolved: uniform default confirmed at sign-off |
| — *(resolved, v1.5)* | ~~Q12–Q15, Q17–Q19 — the seven gap-analysis items~~ | Resolved: BR-21–27 and Sections 9a–9g above |
| AQ2 | Observation table partitioning: by calendar month or by School | Pending D5 resolution |
| AQ3 | Message queue technology (affects escalation-timer ordering guarantees) | Pending engineering |
| AQ4 | DPDP erasure: true anonymization vs. retention exemption for audit-relevant records | Pending Legal/Compliance |
| AQ5 | SSO provider/protocol ahead of Phase 2 ERP integration | Pending ERP integration owner |
