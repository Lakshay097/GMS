# Assumptions Log — School Operations & Governance Platform

**Owner of this file: you, not Devin.** Update it as questions get resolved
by stakeholders, and paste the relevant row into a Devin prompt whenever a
new session touches that area, so every session builds against the same
decision instead of re-deriving its own.

Status values: `RESOLVED` (stakeholder-confirmed, binding) · `ASSUMED`
(Devin/you picked a default to keep moving — revisit before production) ·
`BLOCKING` (no safe default exists — do not let Devin guess).

**⚠️ VERIFICATION PASS (Aug 9, 2026):** A comprehensive Phase 1 exit criteria verification pass was conducted per phases.md §1.5. The verification confirmed that all item statuses in this log remain accurate - no items changed status during the build. The verification identified test coverage gaps (missing end-to-end workflow tests, partial BR/FR coverage) but these are testing gaps, not changes to underlying business assumptions or stakeholder decisions. See `verification-report-phase1-exit-criteria.md` for full details.

**PRS v1.5 note:** PRS §17 was renamed "Stakeholder Decisions Required
Before Phase 1 Sign-off" and renumbered **D1–D9**, replacing the old Q1–Q9
list. Every item that had a single defensible engineering answer (Lock
Period, ETA extension duration, self-service registration phasing, and all
seven v1.5 gap-closure items — Discrepancy Approval Chains, Holiday
Calendar, Asset Lifecycle, Compliance Scheduler, Duplicate Detection, Grace
Period, Evidence Retention) is now fully specified in-spec and does **not**
appear in D1–D9 — those are business/policy calls only. The table below
keeps the old Q-numbers for traceability to earlier Devin sessions, maps
each to its new D-number where one still exists, and adds the new D7–D9
items introduced in v1.2/v1.5.

---

## PRS Open Questions (PRS §17 → D1–D9 in v1.5)

| # (old→new) | Question | Recommendation in spec | Status | Decision / Notes |
|---|---|---|---|---|
| Q1 → *(resolved in-spec, v1.5)* | Default Observation Lock Period (BR-11) | 24–48 hours | RESOLVED | No longer a stakeholder decision — PRS v1.5 confirms this is fully config-driven with a documented default. Continue building against **24 hours** as the seeded default (Configuration Engine value); change via config, not code, if the actual number differs. |
| Q2 → *(resolved in-spec, v1.5)* | Default ETA extension duration — uniform vs. per task type (BR-10) | Pending | RESOLVED | PRS v1.5 confirms uniform extension length (not per-task-type) is the specified behavior — no longer open. Continue building **uniform** as already implemented. |
| Q3 → D1 | Marketing Manager / Telecaller KPIs: stay on-platform vs. separate CRM | Keep in-platform initially; future CRM syncs performance data rather than duplicating KPIs | RESOLVED | **Decision: In-platform for Phase 1.** Both manuals are already fully transcribed and fit the existing KRA/KPI/Department model with no structural changes needed. If a CRM is introduced later, it syncs performance data into this platform rather than maintaining a second KPI taxonomy. The two held role sections in `kpi-seed-data.md` are released for SME review and Prompt 6 import alongside the other 8 roles. |
| Q4 → D2 | Channel selection per notification event, incl. SMS/WhatsApp cost approval | Start with In-App + Email; add SMS/WhatsApp per event once cost is approved | BLOCKING (cost/vendor question) | Notification Matrix (PRS §49) defines *which* channels *should* fire; this is about whether SMS/WhatsApp vendor cost is approved. Building the dispatch mechanism regardless (Prompt 4/12) but SMS/WhatsApp sends should stay behind a feature flag until this is signed off. |
| Q5 → D3 | Minimum viable Global KPI Library taxonomy for schools without a supplied role manual | Finalize before development begins — highest-priority item on this list | RESOLVED | **Decision: 5-category core set, applied to any school without a matching role manual, with role-manual KPIs layered on top where one exists.** Categories: Safety, Academics, Facilities, Finance (basic), Staff Compliance — chosen because these recur across all 10 supplied role manuals regardless of role, so the set is derived from existing content rather than invented. See `kpi-seed-data.md` §"Core KRA Set" for the specific KRAs/KPIs. |
| Q6 → D4 | Escalation SLA durations — org-wide default vs. per-department override | Organization defaults with department override (already architecturally supported) — needs actual SLA numbers | ASSUMED | Building **per-department override with an org-wide default fallback** — this is what the Configuration Engine already supports structurally (Prompt 4), so it costs nothing extra and covers both outcomes. Actual SLA numbers still pending stakeholder confirmation (D4). |
| Q7 → *(resolved, out of scope)* | Target phase for self-service School registration | Confirms early vs. late Phase 2 | RESOLVED (for Phase 1 purposes) | Out of scope for Phase 1 either way (phases.md §1.2) — no action needed until Phase 2 planning. |
| Q8 → D5 | Performance/scalability hard targets (concurrent users, observation volume, availability SLA) | Confirm with infra stakeholders before engineering sizing | BLOCKING | Blocks AQ2 (partitioning strategy) and real load-test thresholds in Prompt 11. Building Prompt 1–12 without hard numbers; do not sign off Prompt 13's exit criteria without this. |
| Q9 → D6 | KPI Amber Tolerance Band — uniform default vs. per-category override | Per-category, with Safety at stricter/zero tolerance — needs stakeholder confirmation of exact bands | ASSUMED | Building **uniform global default with per-category override support** (same reasoning as Q6 — the Configuration Engine already supports scope tiers, so building the general case costs nothing and doesn't foreclose either answer). Exact bands, especially Safety = 0%, still pending (D6). |
| *(new, v1.2)* D7 | Event Time integration matrix: which Event Time Points get genuine Auto-Capture at go-live vs. Manual-only in Phase 1, and which (if any) are Auto-Capture-only with no Manual fallback | Decide before development — drives architecture (PRS §24.14) | BLOCKING | Directly affects Prompt 8/9 (Observation Capture) — do not let Devin assume every Event Time Point has an Auto-Capture integration available; default to Manual Entry (with mandatory Reason) for any point without a confirmed hardware/vendor integration. |
| *(new, v1.5)* D8 | Should individual KPI ownership exist beyond Department-level assignment? | Recommend deferring — Department-level assignment plus User→Department transfer history gives adequate accountability tracing for Phase 1 | ASSUMED | Building **Department-level ownership only** (no individual-KPI-owner field) per the spec's own recommendation — flag before Prompt 6 if this changes, since it would be a schema addition, not a config change. **Re-checked against the 10 source manuals (Aug 2026):** for 8 of 10 roles this is a non-issue — each maps to a department with effectively one accountable person, and per-building/per-floor variation (e.g., Facility Manager) is already handled by the existing Asset/Location-scoping column on the KPI itself, not by KPI ownership. The one real gap is **Principal and SOTC Head**, whose KRAs overlap (Transport, Security, Facilities all appear under SOTC Head's KRAs while also having their own dedicated role/department) — Department-level ownership could blur which of the two is accountable for an overlapping KPI. Not reopening D8 over this, but flagging it as a named exception worth a real answer from org design before Phase 1 sign-off, not something to silently resolve as "department-level is fine everywhere." |
| *(new, v1.5)* D9 | Should Asset Lifecycle expand beyond the Phase 1 minimal Active/Retired status (PRS §35.15)? | Recommend keeping full Asset Management in Phase 3 as planned; Phase 1 minimal status is sufficient for Event Time scoping safety | ASSUMED | Building **Active/Retired only** (no acquisition/maintenance/procurement workflow) per the spec's own recommendation — this is the default unless overridden before Prompt 8/9. |

**Also resolved and no longer tracked as open here (PRS §17 closing note,
v1.5):** all seven gap-closure items — Discrepancy Multi-Level Approval
(BR-21), Holiday Calendar (BR-22), Asset Lifecycle (BR-23), Compliance
Scheduler behavior (BR-24), Duplicate Observation Prevention (BR-25), Grace
Period & Reopen (BR-26), Evidence Retention (BR-27) — are fully specified
in PRS §9/12/23–26/35/37/41/46–47/50/54/57 and require no further
stakeholder input before Prompt 6 onward.

## Architecture Open Questions (Architecture §21)

| # | Question | Status | Decision / Notes |
|---|---|---|---|
| AQ1 | Application-tier compute hosting platform (container platform / PaaS) | ASSUMED | Neon + Cloudinary are resolved (v1.1). Building against a generic containerized deploy (any PaaS/K8s) so the choice is swappable — do not let Devin hardcode a specific host's SDK into application code. |
| AQ2 | Observation table partitioning: by calendar month or by School | ASSUMED, pending Q8 | Building **month-based partitioning** as the reversible default (Prompt 2). Revisit once Q8's volume targets and actual school count are known — by-School partitioning may be better at scale but is harder to change after data accumulates. |
| AQ3 | Message queue technology (affects escalation-timer ordering guarantees) | BLOCKING for production, ASSUMED for dev | Building against an abstract queue interface (Prompt 1) so the concrete choice is swappable. If escalation ordering guarantees matter (they likely do, given SLA timers — R-33/R-41), lean Kafka-class over SQS-class, but get engineering sign-off before production cutover. |
| AQ4 | DPDP erasure: true anonymization vs. retention exemption for audit-relevant records | BLOCKING | Do not implement a "delete on request" path for audit-relevant records until Legal confirms which model applies — this directly conflicts with R-19 (audit log append-only) if built wrong. Flag any GDPR/DPDP erasure feature request as blocked on this until resolved. |
| AQ5 | SSO provider/protocol ahead of Phase 2 ERP integration | ASSUMED | Neon Auth (Prompt 3) supports OAuth/SSO connectors out of the box per Architecture §18 — building Phase 1 auth so an SSO connector is an additive config, not a rebuild. No specific protocol pinned yet; confirm before Phase 2 ERP work starts. |
| AQ4a *(v1.5, related to AQ4)* | Whether Evidence deletion (BR-27, an explicit logged Admin action after the Retention Period) counts as satisfying a DPDP erasure request, or is a separate mechanism from whatever AQ4 resolves | BLOCKING | Do not conflate "evidence became deletion-eligible" with "a DPDP erasure request was fulfilled" — these are different triggers even if the resulting action (deletion) looks the same. Resolve alongside AQ4, not before it. |
| AQ6 *(new, discovered during Auth naming-fix session)* | Frontend framework: Next.js vs. Vite+React-Router | RESOLVED | **Decision: Vite + React Router.** Rationale: backend is FastAPI, and Next.js's Neon Auth integration (`@neondatabase/auth/next`, `createNeonAuth()`) is built around Next.js API routes acting as the auth server — pairing that with an already-separate FastAPI backend creates two overlapping backends and duplicated session/token handling for no benefit. Vite + React Router keeps a single-owner auth flow: the Vite client uses `@neondatabase/neon-js/auth` (`VITE_NEON_AUTH_URL`) to handle sign-in/sign-up UI and obtain a session token directly from Neon Auth; that token is sent as a Bearer token to FastAPI, which verifies it server-side via `NEON_AUTH_SECRET_KEY` — matching the existing `tenancy.py`/`permissions.py` middleware pattern exactly. FastAPI never independently checks a password; it only validates the token it's handed. This also resolves the flagged `auth.py` bug below — that skipped-password-verification code path was a leftover Next.js-style assumption and should be replaced with token-verification-only, not "finished." |

---

## KPI Seed Data — Field-Level SME Review (kpi-seed-data-SME-review-checklist)

| Item | Status | Decision / Notes |
|---|---|---|
| Field-level review of all 10 role tabs (Sensitive?, Capture Type, Event Time Point(s), Non-Working-Day Policy, Asset/Location Scoped?, Frequency) plus the new Evidence Required (Photo/Document)? field | RESOLVED | **Approved 2026-08-08.** Note: the workbook's own per-tab "Reviewed by" cells still read "Claude (AI first-pass review) — pending human SME sign-off" (or are blank on the School Principal, Telecaller, and Core tabs) — that label was not updated when sign-off happened. Treating this as approved per stakeholder confirmation, not per the workbook's internal metadata. **Correction path:** any row that turns out wrong is fixed later via the master dashboard (admin-editable config), not by re-opening this review pass or blocking Prompt 6 import. Import the checklist's SME-column values as-is. |
| Capture Type schema clarification (Instructions tab) | RESOLVED | Capture Type is a fixed 3-value platform enum — Value Reading, Event Time, Value + Event Time. Photo/document evidence, Location scoping, and Asset scoping are separate per-KPI config fields (evidence requirement, location_id, asset_id), not Capture Types. A "Done/Not-Done" KPI is a Value Reading with a text or 100%-threshold unit. Build Prompt 6 import against this 3-value enum. |
| Evidence Required (Photo/Document)? — new field | RESOLVED | Not present in any source manual; this is a first-draft recommendation now approved alongside the rest of the checklist. Add as a per-KPI boolean field in the schema (Prompt 6), correctable later via master dashboard same as everything else in this checklist. |
| Frequency field — most rows "not specified in manual" | ASSUMED (unchanged) | Rows where the manual didn't state a cadence are still marked with Claude's best-guess Frequency per the checklist, not a stakeholder-confirmed number. Approved for import per the above, but flag Frequency specifically as the field most likely to need master-dashboard correction post-launch, since it had the least source-manual grounding of the six reviewed fields. |

---

## How to use this during the build

- Before starting any Devin prompt that touches a row above, paste that row's
  current Status + Decision into the prompt so Devin builds against the
  pinned choice, not its own re-derivation.
- When a `BLOCKING` item gets resolved, update its row here immediately and
  re-check any already-built module that assumed a placeholder (e.g., if Q5
  resolves and the KPI taxonomy changes, check Prompt 6's output against it).
- Do not let a `BLOCKING` item sit unresolved past Prompt 13 (the exit-criteria
  QA pass) — that prompt is explicitly designed to surface any that snuck
  through.