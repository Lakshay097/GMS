# KPI Seed Data — Global KPI Library

**Status: SME-REVIEWED (2026-08-08) — ready for Prompt 6 import.** All six
reviewed columns (Sensitive?, Capture Type, Event Time Point(s),
Non-Working-Day Policy, Asset/Location Scoped?, Frequency) have been
corrected below per the SME-approved
`kpi-seed-data-SME-review-checklist_filled__2__FIXED.xlsx` sign-off pass,
and a new **Evidence Required (Photo/Document)?** column has been added
(not present in any source manual — first-draft recommendation, approved
alongside the rest of the checklist). See `assumptions-log.md` for the
approval record. Any row that turns out wrong post-launch is corrected via
the master dashboard (admin-editable config), not by re-opening this file.

**Capture Type is a fixed 3-value platform enum** (per confirmed schema,
PRS v1.5): `Value Reading`, `Event Time`, `Value + Event Time`. Photo/
document evidence, Location scoping, and Asset scoping are separate
per-KPI configuration fields (evidence requirement, location_id, asset_id),
not Capture Types — reflected in the `Value Reading` naming below
(previously shown as plain `Value`).

**Transcription-artifact fix pass (this revision):** the mechanical
sentence-splitter used to build the first-pass version of this file broke
on the string "YoY" (and, in two cases, "CapEx" and "WhatsApp"), which it
mistook for row boundaries. This produced 9 garbage rows (bare fragments
like `Y`, `Yo`, `Y improvement`) and 4 rows that were really one KPI split
across two lines. All 13 have been corrected: garbage rows removed, split
rows merged back into a single KPI with the original wording restored
(cross-checked against the source `.docx` manuals). This was a mechanical
data-quality fix, not a content decision — it does not touch or resolve
the SME review items below.

This file is seeded from **9 of the 10** role-based KRA/KPI manuals supplied
in `drive-download-20260805T060828Z-1-001.zip`
(TGS Accountant, Facility Manager, IT Manager, Marketing Manager, Principal,
SOTC Head, Security Guard [bilingual], Store In-Charge, Telecaller). The
**Transport Manager** manual (`TGS_Transport_Manager_KRA_KPI.docx`, 28 KPIs)
is excluded — the standalone Transport Manager role is not being built for
Phase 1. SOTC Head's own "Transport Operations" and "Transport Compliance"
KRAs (7 KPIs) are **retained** — that's SOTC-level oversight of transport
as one of several operational areas, distinct from a dedicated Transport
Manager role/module, and was not part of this exclusion. Every KRA and KPI
row below is transcribed from those nine manuals —
nothing has been invented to fill a gap.

**How this file was built, and what was reviewed:**

- The source manuals give each KPI as a single free-text sentence (e.g.
  *"Budget variance: ≤ ±5%"*), not as separate Unit / Comparator / Target /
  Frequency / Capture-Type columns. This file was built by mechanically
  splitting each sentence into those columns using pattern-matching
  (percentage/comparator symbols, frequency keywords, sensitive-topic
  keywords). That mechanical split is **reliable for the KRA/KPI names and
  the target text themselves**. The following columns started as
  best-effort inference and have now been through the SME review pass
  (2026-08-08) — the values below are the SME-approved result, per column:
  - **Sensitive/financial (yes/no)** — originally flagged via keyword match
    (budget, payroll, tax, fee, fund, asset register, etc.); SME-reviewed
    per row, with one flip applied (School Principal — "Maintain accurate
    records, reports, and documentation" corrected to `yes`, since it
    involves records/documentation handling worth an R-50 category check).
  - **Capture Type / Event Time Point(s)** — the v1.5 Capture Type field is
    a fixed 3-value enum (`Value Reading`, `Event Time`,
    `Value + Event Time`), confirmed against platform schema and applied
    below (previously shown as plain `Value`). Event Time Point labels are
    SME-approved as-is.
  - **Non-Working-Day Policy** — SME-confirmed per row; `Skip` remains the
    default where no manual states otherwise (BR-22).
  - **Asset/Location Scoped?** — SME-confirmed per row. BR-23 still means
    the underlying Asset records must already exist before any Asset-scoped
    row can be imported as such.
  - **Frequency** — SME-confirmed per row, including a second-pass review
    on several tabs (IT Manager, Store In-Charge, Security Guard, Marketing
    Manager) that filled in cadences beyond what the manual stated
    verbatim. Still confirm against Master Data's supported enumeration
    before import.
  - **Evidence Required (Photo/Document)?** — new column, not present in
    any source manual. First-draft recommendation, approved alongside the
    rest of the checklist.
  - **Unit** — inferred as `%` where the target is a percentage; left
    blank/`n/a` where the manual's target is a TAT, count, or qualitative
    statement rather than a clean unit+number. Out of scope for this
    review pass (unchanged).

**This file is approved for Prompt 6 import.** Any row that turns out
wrong in practice gets corrected via the master dashboard post-launch, not
by re-opening this file.

---

## 1. What needs to go here

For each of the ~10 role-based KRA/KPI manuals referenced in the PRS:

- Role/title the manual applies to (e.g., "Transport In-Charge", "Front
  Office Executive", "Academic Coordinator"). **Every row below now carries
  this as an explicit `Role` column**, not just a section heading — added
  because all 10 source manuals frame each KRA/KPI as belonging to a named
  position, and D8 (Department-level KPI ownership) collapses that down to
  Department at the platform-schema level. Keeping Role on the row
  preserves the source manual's actual accountability language for
  traceability, without changing the ownership model D8 already settled.
- Each KRA (Key Result Area) name and a one-line description.
- For each KRA, its KPIs: name, Unit, Comparator (one of ≥ ≤ = < >), Target
  value, Frequency (from the supported enumeration — daily/weekly/monthly/
  termly/annual, confirm against Master Data), and whether it's
  sensitive/financial (affects R-50 category-level export restrictions).
- **(v1.5 additions)** Capture Type — Value, Event Time, or Value + Event
  Time (PRS §23.6/§24.14); for any KPI with an Event Time component, the
  Event Time Point(s) it tracks (e.g., Departure Time, Return Time,
  Check-In Time) and whether each is Auto-Captured, Manual, or
  Manual-fallback-permitted. Non-Working-Day Policy — Skip, Shift Forward,
  or Shift Backward (PRS §23.17/BR-22; default Skip if not specified per
  manual). Whether the KPI is scoped per-Asset and/or per-Location (PRS
  §24.14) rather than only per-Department.

## 2. Role manuals (transcribed)

### Role: `School Principal`

*Source manual: `TGS_Principal_KRA_KPI.docx`*

**Role overview:** The Principal is the ex-officio Member Secretary of the School Management Committee and the Head of the school office, carrying out all academic and administrative duties of a head of institution. The Principal provides leadership, direction, and coordination within the school, and is responsible for the detailed organisation of the school, the development of the instructional programme, the supervision of staff, and the general operation of the school facility.

**Reporting line:** School Management Committee / Managing Trust — governance oversight; Regional Director / Academic Director / CBO — administrative and operational reporting; CBSE / State Board — statutory and examination-related compliance

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| School Principal | Academic Standards & Achievement | Ensure high academic standards and student achievement | _n/a_ | ≥ | defined target | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Academic Standards & Achievement | Year-on-year improvement in average academic performance | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Academic Programme Monitoring | Monitor and improve the school's academic programmes | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Teaching & Learning Strategies | Implement effective teaching and learning strategies | % | _n/a_ | 100% | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Assessment & Examination Oversight | Oversee assessment and examination processes | % | _n/a_ | 100% | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Timetable & Academic Planning | Plan the year's academic work in consultation with staff | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Timetable & Academic Planning | Hold staff meetings at least monthly to review progress | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Classroom Supervision & Coordination | Supervise classroom teaching and secure inter/intra-subject coordination | _n/a_ | ≥ | defined frequency | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Remedial & Individual Attention | Arrange remedial teaching for students needing extra support | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Direct Teaching Involvement | Devote at least one period per day to teaching pupils | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| School Principal | Recruitment & Evaluation | Recruit, train, and evaluate teaching and non-teaching staff | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Positive Work Environment | Foster a positive work environment and professional development opportunities | _n/a_ | ≥ | defined target | quaterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Conflict & Disciplinary Handling | Handle staff conflicts and disciplinary issues | % | _n/a_ | 100% | event-triggered | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Staff Supervision | Daily supervision of school staff, facilitators, volunteers, and outside-agency personnel | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | No |
| School Principal | Staff Supervision | Ensure staff punctuality (on duty ahead of session start as per policy) | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| School Principal | Orientation & Substitute Planning | Conduct orientation for staff new to the school | % | _n/a_ | 100% | event-triggered | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Orientation & Substitute Planning | Instructions prepared for substitute teachers | % | _n/a_ | 100% | event-triggered | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Regulatory Compliance | Ensure compliance with Affiliation and Examination Bye-Laws and all Board directions | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Records, Registers & Returns | Maintain accounts, service books, stock registers, and statutory returns | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Records, Registers & Returns | Furnish returns/information to the State Government/Board within specified dates | % | _n/a_ | 100% | event-triggered | yes | Value + Event Time | TAT/Response Time (point not named in manual) | Skip (default — not specified per manual) | none | No |
| School Principal | Procurement & Stock Verification | Make purchases per governing rules, maintain stock register, scrutinise bills | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Procurement & Stock Verification | Conduct physical verification of school property and stock at least once a year | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Financial Administration (Drawing & Disbursing) | Act as drawing and disbursing officer per Society/Board instructions | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Financial Administration (Drawing & Disbursing) | Responsible utilisation of the Pupils Fund | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Correspondence & Records Management | Handle official correspondence relating to the school | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value + Event Time | Response Time | Not Applicable on non-working days | Location | No |
| School Principal | Correspondence & Records Management | Maintain accurate records, reports, and documentation | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Budget & Resource Management | Manage school budgets and resources efficiently | _n/a_ | ≤ | defined threshold | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Safe & Inclusive Environment | Create a safe and inclusive school environment | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quaterly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Discipline Policy Enforcement | Implement and enforce discipline policies | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Discipline Policy Enforcement | Disciplinary authority exercised over students on premises, in transit, and during school activities | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | No |
| School Principal | Student Concerns | Address student concerns and issues | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Health & Well-Being | Promote physical well-being, cleanliness, and health habits; arrange periodical medical examinations | % | _n/a_ | 100% | quaterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School Principal | Health & Well-Being | Refer any child with a suspected communicable disease or health concern to appropriate medical support | % | _n/a_ | 100% | event-triggered | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Visitor & Access Control | Establish procedures to monitor and control visitor access | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| School Principal | Errand/Leave-Premises Control | No student permitted to leave school grounds without express permission | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | No |
| School Principal | Parent & Community Relationships | Foster strong relationships with parents, guardians, and the local community | _n/a_ | ≥ | defined target | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Events & Outreach | Organise and participate in school events, meetings, and outreach programmes | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Community Partnerships | Seek support and partnerships with community organisations | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | School Improvement Plan | Develop and execute a school improvement plan | % | ≥ | 80% milestones achieved | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Goal Setting | Set short-term and long-term goals for the school's growth | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Plan Review & Adjustment | Continuously assess and adjust the strategic plan | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Trend & Technology Awareness | Stay updated with educational trends and technology | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Innovative Methods | Introduce innovative teaching methods and tools | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Research & Development | Encourage research and development initiatives | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Infrastructure Maintenance | Maintain and upgrade school infrastructure | % | ≥ | 95% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| School Principal | Infrastructure Maintenance | Ensure drinking water, fixtures, furniture, equipment, lavatories, playgrounds are properly maintained | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Asset/Location | Yes |
| School Principal | Clean & Safe Environment | Ensure a clean and safe learning environment | % | ≥ | 90% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | Yes |
| School Principal | Clean & Safe Environment | Direct the Caretaker's routine cleaning work | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | Yes |
| School Principal | Sustainability Practices | Implement energy-efficient and eco-friendly practices | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Hazard Inspection | Inspect grounds/buildings for hazards and notify authorities of conditions needing remedy | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| School Principal | Enrolment Strategy | Develop strategies to attract and retain students | % | ≥ | defined % | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Marketing to Target Audience | Market the school to the target audience | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Retention Monitoring | Monitor enrolment/attrition trends and adapt recruitment efforts | _n/a_ | ≥ | defined target | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Admission Oversight | Be in-charge of admissions, timetable preparation, and duty allocation to teachers | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Budget Creation & Management | Create and manage the school's budget | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Financial Sustainability | Ensure financial sustainability and responsible spending | % | ≥ | 95% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Funding & Sponsorship | Seek out and secure funding opportunities, grants, and sponsorships | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Activity/Student Fund Accounting | System of accounting for student activity funds, fees, and gifts | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Staff Training Promotion | Promote ongoing training and development for staff | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Currency in Field | Encourage staff to stay current in their fields | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Mentorship Programmes | Establish mentorship programmes for career growth | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Emergency Plans | Develop emergency plans and procedures | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Fire Drills & Safety Training | Conduct fire drills as required by regulation; ensure all personnel know procedures | % | ≥ | 95% | annual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Crisis Response | Respond effectively to crises (natural disasters, security incidents) | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | event-triggered | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Incident Reporting | Report accidents/injuries to the appropriate authority (Superintendent/Central Team) | % | _n/a_ | 100% | event-triggered | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Incident Reporting | Serious/deliberate damage reported to police in addition to internal reporting | % | _n/a_ | 100% | event-triggered | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School Principal | Medication & Health Controls | Establish controls governing use of medication by students | % | _n/a_ | 100% | daily | yes | Value Reading | n/a | Not Applicable on non-working days | none | No |
| School Principal | Academic Performance Tracking | Ensure high academic performance through standards, resources, and progress tracking | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Holistic Development | Promote social, emotional, and extracurricular growth | _n/a_ | ≥ | defined target | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Communication Channels | Establish effective, regular communication channels with parents | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Grievance Resolution Process | Develop and operate a grievance resolution process | % | _n/a_ | 100% | event-triggered | no | Value + Event Time | Resolution Time | Skip (default — not specified per manual) | none | No |
| School Principal | Feedback Collection & Analysis | Regularly collect and analyse parent feedback | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | termly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Leading by Example | Demonstrate the school's vision and values through actions, decisions, and interactions | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | No |
| School Principal | Culture Alignment | Foster a school culture aligned with stated vision and values | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Principal | Board Examination Duties | Send teachers for evaluation of Board examination answer scripts and related duties as required | % | _n/a_ | 100% | event-triggered | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Board Examination Duties | Act as Centre Superintendent when appointed by the Board, without delegating this responsibility | % | _n/a_ | 100% | event-triggered | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Principal | Non-Refusal of Board-Assigned Duties | Board-assigned duties (examination conduct, evaluation, result processing) not refused | % | _n/a_ | 100% | event-triggered | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |

---

**Performance review cadence:** The Principal's performance against this KRA/KPI set is reviewed at least twice yearly by the Regional Director / Management Committee.

**Manual review cadence:** This manual is reviewed at least once every academic year, or earlier where a regulatory change or major incident requires an update.

---

### Role: `SOTC Head (Safety, Operations, Transport & Compliance)`

*Source manual: `TGS_SOTC_Head_KRA_KPI_Complete.docx`*

**Role overview:** The SOTC Head (Safety, Operations, Transport & Compliance) is the single point of accountability for campus operations, residential life, and statutory compliance. The role reports to the Principal for day-to-day campus matters and to the Central Operations / SOTC Central team for MIS, budget, and compliance oversight.

**Reporting line:** Principal (campus administration) — day-to-day escalation and sign-off; Central Operations / SOTC Central — MIS, budget, and compliance oversight; Compliance Officer — dotted-line coordination on statutory and audit matters

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SOTC Head (Safety, Operations, Transport & Compliance) | Daily Operations & Uptime | Daily operations uptime | % | ≥ | 99% operational continuity | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Daily Operations & Uptime | Inter-department issue resolution TAT | hours | ≤ | 24 hours | monthly | no | Value + Event Time | Resolution Time | Not Applicable on non-working days | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Daily Operations & Uptime | Operational escalations | _n/a_ | ≤ | defined monthly threshold | monthly | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Daily Operations & Uptime | SOP adherence score | % | ≥ | 95% compliance | monthly | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Infrastructure & Facilities Management | Preventive maintenance compliance | % | ≥ | 95% planned tasks completed | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Infrastructure & Facilities Management | Utility downtime (power/water/AC) | _n/a_ | ≤ | defined hours/month | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Infrastructure & Facilities Management | Infrastructure audit score | % | ≥ | 90% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Infrastructure & Facilities Management | Infrastructure project completion | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value + Event Time | TAT/Response Time (point not named in manual) | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Housekeeping & Campus Cleanliness | Housekeeping audit | % | ≥ | 90% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Housekeeping & Campus Cleanliness | Daily cleanliness checklist compliance | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Housekeeping & Campus Cleanliness | Student/staff cleanliness complaints | _n/a_ | ≤ | X/month | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Housekeeping & Campus Cleanliness | Response time | hours | ≤ | 2 hours | monthly | no | Value + Event Time | Response Time | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Security & Safety Management | Safety audit compliance | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Security & Safety Management | Fire & electrical drills | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | biannual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Security & Safety Management | Safety incidents | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Security & Safety Management | Hazard rectification TAT | hours | ≤ | 24 hours | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Transport Operations | Route optimization efficiency | % | ≥ | 95% on-time | monthly | no | Value Reading | n/a | Not Applicable on non-working days | Location | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Transport Operations | Vehicle fitness & compliance | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Asset | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Transport Operations | Transport-related parent complaints | _n/a_ | ≤ | X/month | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Transport Operations | Vehicle breakdown incidents | _n/a_ | ≤ | defined threshold | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Asset | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Vendor & Contract Management | Vendor SLA compliance | % | ≥ | 95% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Vendor & Contract Management | Vendor performance review | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Vendor & Contract Management | Cost savings through negotiation | % | ≥ | X% YoY | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Vendor & Contract Management | YContract renewal timeliness | % | _n/a_ | 100% | quarterly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Financial & Budget Control | Budget variance | % | ≤ | ±5% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Financial & Budget Control | Monthly expense reporting accuracy | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Financial & Budget Control | Identified cost optimization initiatives | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Financial & Budget Control | Vendor payment cycle adherence | % | ≥ | 95% on-time | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | MIS & Reporting | Daily MIS submission | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | MIS & Reporting | Weekly critical issues report | % | _n/a_ | 100% | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | MIS & Reporting | MIS data accuracy | % | ≥ | 98% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | MIS & Reporting | Action closure from reports | % | ≥ | 90% within timeline | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Event & Logistics Management | Event readiness compliance | % | _n/a_ | 100% | Event-driven (per event; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Event & Logistics Management | Event-related incidents | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (per event; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Event & Logistics Management | Budget adherence for events | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (per event; not on a fixed calendar cadence) | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Event & Logistics Management | Stakeholder satisfaction score | _n/a_ | ≥ | 4/5 | Event-driven (per event; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Training, Performance & Process Improvement | Performance reviews completion | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Training, Performance & Process Improvement | Training sessions conducted | _n/a_ | ≥ | X per quarter | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Training, Performance & Process Improvement | Process improvement initiatives | _n/a_ | ≥ | X implemented annually | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Training, Performance & Process Improvement | Technology adoption success rate | % | ≥ | 90% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Continuous Improvement & Innovation | Identified inefficiencies resolved | % | ≥ | 80% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Continuous Improvement & Innovation | Automation / digitization initiatives | _n/a_ | ≥ | X per year | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Continuous Improvement & Innovation | Overall operational efficiency improvement | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Residential Safety & Child-Safeguarding | 100% staff safeguarding training & background checks; 100% hostel safety audits | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Residential Safety & Child-Safeguarding | Fire & emergency drills as statutory; drill effectiveness ≥ 95% | % | ≥ | 95% | biannual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Residential Safety & Child-Safeguarding | Major safeguarding incidents | hrs | _n/a_ | 24 hrs | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Residential Safety & Child-Safeguarding | CCTV & entry/exit systems uptime ≥ 99%; entry logs complete 100% | % | ≥ | 99%; entry logs complete 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Boarding Facilities & Preventive Maintenance | Preventive maintenance compliance ≥ 95% for dorms | % | ≥ | 95% for dorms | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Boarding Facilities & Preventive Maintenance | Dorm readiness ≥ 99% (beds, bedding, lighting, locks) | % | ≥ | 99% (beds, bedding, lighting, locks) | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Boarding Facilities & Preventive Maintenance | Residential infrastructure audit score ≥ 90%; projects on time & within budget | % | ≥ | 90%; projects on time & within budget | quarterly | yes | Value + Event Time | TAT/Response Time (point not named in manual) | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Hostel Housekeeping & Hygiene | Hostel cleanliness audit ≥ 95%; daily checklist 100% compliance | % | ≥ | 95%; daily checklist 100% compliance | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Hostel Housekeeping & Hygiene | Laundry turnaround ≤ 24 hours; pest control monthly 100% | % | ≤ | 24 hours; pest control monthly 100% | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Hostel Housekeeping & Hygiene | Hygiene complaints ≤ 2/month; response TAT ≤ 2 hours | hours | ≤ | 2/month; response TAT ≤ 2 hours | monthly | no | Value + Event Time | Response Time | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Food & Nutrition (Mess Management) | Food safety compliance 100% (HACCP/FSMS); menu nutrition compliance 100% | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Food & Nutrition (Mess Management) | Meal satisfaction ≥ 4/5 (termly); food wastage ≤ 5%; zero food-borne incidents | % | ≥ | 4/5 (termly); food wastage ≤ 5%; zero food-borne incidents | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Food & Nutrition (Mess Management) | Meal service punctuality & quality 100% | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Medical Care & Student Health | 100% periodic medical checkups as scheduled; first-aid response ≤ 15 minutes | minutes | ≤ | 15 minutes | monthly | yes | Value + Event Time | Response Time | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Medical Care & Student Health | Medical incident reporting & follow-up 100% within 24 hrs; immunization records 100% | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Student Welfare, Pastoral Care & Mental Health | Welfare incidents resolved ≤ 24 hrs; counseling check-ins minimum 1 per term | hrs | ≤ | 24 hrs; counseling check-ins minimum 1 per term | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Student Welfare, Pastoral Care & Mental Health | Student wellbeing/satisfaction ≥ 4/5 termly; 100% at-risk plans in place and reviewed monthly | % | ≥ | 4/5 termly; 100% at-risk plans in place and reviewed monthly | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Residential Staff Management & Training | 100% background & statutory checks before engagement; staff | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Discipline, Behaviour & Child Protection | Target ≥ 10% YoY reduction in disciplinary incidents; investigations concluded ≤ 7 working days | % | ≥ | 10% YoY reduction; investigations concluded ≤ 7 working days | quarterly | no | Value + Event Time | TAT/Response Time (point not named in manual) | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Discipline, Behaviour & Child Protection | 100% parent notification for major incidents; appeals/closure ≥ 95% on time | % | _n/a_ | 100% parent notification; appeals/closure ≥ 95% on time | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Compliance, Licensing & Statutory Reporting | Boarding inspections passed/remediated 100%; license renewals 100% before expiry | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Compliance, Licensing & Statutory Reporting | Policy documents & logs maintained 100% accuracy | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Parent & Stakeholder Communication | 100% monthly residential updates; parent satisfaction ≥ 4/5 termly | termly | ≥ | 4/5 termly | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Parent & Stakeholder Communication | Parent concerns resolved TAT ≤ 48 hours | hours | ≤ | 48 hours | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Activities, Routine & Student Life | Activity calendar adherence 100%; student participation ≥ 75% in supervised activities | % | ≥ | 75% in supervised activities | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Activities, Routine & Student Life | Zero major event incidents; post-event satisfaction ≥ 4/5 | _n/a_ | ≥ | 4/5 | Event-driven (per event; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Emergency Preparedness & Risk Management | Emergency plan readiness score ≥ 95%; evacuation times meet benchmark during drills | % | ≥ | 95%; evacuation times meet benchmark during drills | biannual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Emergency Preparedness & Risk Management | Emergency contacts & contingency plans updated & tested quarterly | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Inventory, Linens & Asset Management | Inventory accuracy ≥ 98%; bedding/uniform issuance ≤ 48 hours | % | ≥ | 98%; bedding/uniform issuance ≤ 48 hours | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Inventory, Linens & Asset Management | Loss/damage replacement ≤ 7 days; loss/damage incidents ≤ defined threshold | days | ≤ | 7 days; loss/damage incidents ≤ defined threshold | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Residential Transport & Leave Coordination | 100% compliance for leave/travel permissions & manifests; zero residential transport safety incidents | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Residential Transport & Leave Coordination | Parent handover protocol compliance 100%; transport & leave MIS updates 100% on time | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Statutory & Regulatory Compliance | All statutory inspections (education, health & safety, fire, food, transport) passed or remediated | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Statutory & Regulatory Compliance | Regulatory notices closed within defined remediation period (suggest ≤ 30 days) | % | ≤ | 30 days): 100% / ≤ 30 days | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Statutory & Regulatory Compliance | Licenses & registrations renewed | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Health, Safety & Environment Compliance | Safety audits compliance (campus-wide) | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Health, Safety & Environment Compliance | Fire safety certification & electrical safety checks current | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Health, Safety & Environment Compliance | Hazard rectification TAT ≤ 24 hours for high-risk; safety incidents | hours | ≤ | 24 hours for high-risk; safety incidents: Zero major incidents | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Child Protection & Safeguarding (School-wide) | Child protection policy compliance and staff safeguarding training | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Child Protection & Safeguarding (School-wide) | Background / DBS checks for all staff and volunteers | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Child Protection & Safeguarding (School-wide) | Safeguarding incidents reported & investigated within 24 hours; safeguarding audit compliance | hours | _n/a_ | 24 hours | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Food Safety & Hygiene Compliance | Food safety (HACCP/FSMS) compliance | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Food Safety & Hygiene Compliance | Temperature logs & storage records maintained 100%; monthly food safety audits | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Food Safety & Hygiene Compliance | Zero food-borne illness incidents; pest control records up-to-date | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Transport Compliance | Vehicle fitness & statutory compliance | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Asset | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Transport Compliance | Driver licenses, medicals & mandatory training | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Transport Compliance | GPS & tracking uptime ≥ 99%; pre-trip risk assessments & permits 100% completed for external trips | % | ≥ | 99%; pre-trip risk assessments & permits 100% completed for external trips | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | HR & Labour Compliance | Employment contracts, payroll, statutory benefits & gratuity compliance | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | HR & Labour Compliance | Mandatory staff certifications & statutory medicals | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | HR & Labour Compliance | Working hours & statutory record-keeping compliance ≤ 0 exceptions | exceptions | ≤ | 0 exceptions | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Data Protection & Privacy | Student & staff personal data handling policies implemented | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Data Protection & Privacy | Access logs & consent records maintained 100%; data breach response tested annually | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Data Protection & Privacy | Retention & disposal policies implemented and audited yearly | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Building, Fire & Utilities Compliance | Building occupancy, structural safety checks & fire certificates current | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Building, Fire & Utilities Compliance | Emergency lighting, exit signage & firefighting equipment inspection | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Building, Fire & Utilities Compliance | Electrical & gas safety certification renewed as required | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Medical & Public Health Compliance | Immunization compliance for students as per statutory requirements | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Medical & Public Health Compliance | Medication administration logs & sickbay protocols 100% accurate; infection control plans in place & tested | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Medical & Public Health Compliance | Reportable public-health incidents notified within regulatory timelines | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as incidents occur; reported within regulatory timelines) | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Environmental & Waste Management Compliance | Hazardous waste & chemical storage handled per regulation | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Environmental & Waste Management Compliance | Effluent, sewage & solid waste disposal compliant with local laws; recycling & energy audits annually | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Environmental & Waste Management Compliance | Environmental incidents | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Accreditation & External Reporting | Maintain accreditation standards and evidence | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Accreditation & External Reporting | Respond to regulator / accreditor queries within ≤ 7 working days | % | ≤ | 7 working days: 100% | Event-driven (as queries occur; TAT-based, not calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Accreditation & External Reporting | Annual & statutory filings completed on time | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Compliance Training, Internal Audit & Closure | Mandatory compliance training completion | % | _n/a_ | 100% | annual | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Compliance Training, Internal Audit & Closure | Internal compliance audits quarterly; external audits as scheduled | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Compliance Training, Internal Audit & Closure | Remediation closure rate ≥ 95% within agreed timelines | % | ≥ | 95% within agreed timelines | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Compliance Calendar & MIS | Compliance calendar maintained & updated 100% with owners, due dates & evidence | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Compliance Calendar & MIS | Compliance KPI dashboard updated monthly; exception reporting in Daily MIS when required | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Compliance Calendar & MIS | Designated Compliance Officer and SOTC Head oversight with clear escalation paths | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Systems Uptime & Support | ERP / core systems uptime | % | ≥ | 99% | daily | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Systems Uptime & Support | IT support ticket resolution | min | ≤ | 30 min, High ≤ 1 hr, Medium ≤ 4 hrs, Low ≤ 24 hrs | daily | no | Value + Event Time | Resolution Time | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Systems Uptime & Support | CCTV and access-control system uptime | % | ≥ | 99% | daily | yes | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Data Backup & Cybersecurity | Scheduled data backup completion | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Data Backup & Cybersecurity | Password/access-policy compliance | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Data Backup & Cybersecurity | Cybersecurity incident response tested | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Asset Register & Lifecycle | Asset register accuracy | % | ≥ | 98% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | Asset | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Asset Register & Lifecycle | AMC renewal timeliness | % | _n/a_ | 100% | quarterly | yes | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Asset Register & Lifecycle | Assets flagged for replacement at biannual audit | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | Asset | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Energy & Waste Efficiency | Monthly electricity audit completion | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Energy & Waste Efficiency | YoY energy-consumption reduction | _n/a_ | _n/a_ | measurable target set annually | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Energy & Waste Efficiency | Waste segregation compliance (biodegradable / non-biodegradable / hazardous) | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Crisis Readiness (Campus-Wide) | Crisis/emergency response plan tested | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Crisis Readiness (Campus-Wide) | Communication-tree activation time (parents, staff, Central Team) | _n/a_ | ≤ | defined benchmark | annual (tested annually as part of drill cycle) | no | Value + Event Time | Activation Time | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Crisis Readiness (Campus-Wide) | Post-incident review completed | % | _n/a_ | 100% | Event-driven (as incidents occur) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Workforce Administration | Attendance logging accuracy (non-residential ops staff) | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Workforce Administration | Leave approval TAT | hours | ≤ | 48 hours | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Workforce Administration | Grievances acknowledged ≤ 24 hours; resolved ≤ 7 working days | hours | ≤ | 24 hours; resolved ≤ 7 working days | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Insurance Coverage | Vehicle and property insurance renewal | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | Asset | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Insurance Coverage | Student/staff accident-policy coverage | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Insurance Coverage | Claims processed within policy TAT | % | _n/a_ | 100% | monthly | yes | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Day-School Parent Communication | Parent concern resolution TAT | hours | ≤ | 48 hours | monthly | no | Value + Event Time | Resolution Time | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Day-School Parent Communication | Periodic (e.g., termly) operations update to parents | % | _n/a_ | 100% | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Day-School Parent Communication | Parent satisfaction score (operations-related) | _n/a_ | ≥ | 4/5 | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Launch Readiness | New-campus infrastructure checklist completion | % | _n/a_ | 100% | Event-driven (per new-campus launch; not a recurring cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| SOTC Head (Safety, Operations, Transport & Compliance) | Launch Readiness | Setup turnaround time | weeks | _n/a_ | 3 weeks | Event-driven (per new-campus launch; not a recurring cadence) | no | Value + Event Time | Setup Completion Time | Skip (default — not specified per manual) | none | No |
| SOTC Head (Safety, Operations, Transport & Compliance) | Launch Readiness | Statutory pre-opening approvals secured | % | _n/a_ | 100% | Event-driven (per new-campus launch; not a recurring cadence) | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |

---

**Note on this manual's coverage:** Sections 9–17 were introduced to close gaps identified against the original SOTC KRA/KPI document and should be prioritised for sign-off by Central Operations.

**Performance review cadence:** The SOTC Head's own performance is reviewed against this KRA/KPI set at least twice yearly by the Principal and Central Operations.

**Manual review cadence:** This manual is reviewed at least once every academic year, or earlier where a regulatory change or major incident requires an update.

---

### Role: `School Accountant`

*Source manual: `TGS_Accountant_KRA_KPI.docx`*

**Role overview:** The School Accountant is responsible for the school's financial management, payroll, statutory compliance, and financial reporting, ensuring accurate records and sound financial controls.

**Reporting line:** Principal / Operations Head — day-to-day financial administration and approvals; Central Finance Team — budget consolidation, statutory compliance, and audit coordination

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| School Accountant | Annual Budget Preparation & Monitoring | Prepare, manage, and monitor the annual budget | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Annual Budget Preparation & Monitoring | Budget variance | % | ≤ | ±5% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Financial Performance Tracking | Track and report financial performance | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Accounting Standards Compliance | Ensure compliance with accounting standards and regulations | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Payroll Calculation & Processing | Calculate and process payroll for all staff | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Statutory Deductions | Deduct and remit taxes, benefits, and contributions (PF/ESI/TDS, etc.) | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Accounts Payable | Process vendor invoices and payments | % | ≥ | 95% on-time | weekly | yes | Value + Event Time | TAT/Response Time (point not named in manual) | Skip (default — not specified per manual) | none | No |
| School Accountant | Accounts Receivable (Tuition & Other Income) | Oversee tuition fee and other income collection | _n/a_ | ≥ | defined target | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Accounts Receivable (Tuition & Other Income) | Outstanding receivables ageing tracked | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Financial Statements | Generate income statements, balance sheets, and cash flow statements | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Management & Board Updates | Provide regular financial updates to school management and board | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Accountant | External Audit Coordination | Coordinate external audits and ensure regulatory compliance | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School Accountant | Internal Controls | Implement internal controls to safeguard finances and assets | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Grant Identification & Application | Identify and apply for relevant grants/funding | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Grant Fund Management | Manage grant funds and ensure compliance with grant requirements | % | _n/a_ | 100% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Tax Return Filing | Prepare and file all applicable tax returns | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Tax Law Currency | Stay current on tax laws relevant to educational institutions | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Collaborative Budget Development | Work with school administrators on annual budgets | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Accountant | Financial Insight for Strategic Planning | Provide financial insights supporting strategic decisions | % | _n/a_ | 100% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Accounting Software Utilisation | Utilise accounting software/tools for financial processes | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Record Accuracy in Systems | Maintain accurate, up-to-date financial records in software | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Cash Flow Monitoring | Monitor cash flow for day-to-day operations | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | weekly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Cash Reserves & Short-Term Investments | Manage cash reserves and short-term investments | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Tracking Grants, Donations & Endowments | Track and manage all grants, donations, and endowments received | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Allocation & Reporting | Ensure proper allocation and reporting of donated/granted funds | % | _n/a_ | 100% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Communication with Leadership | Collaborate with leadership to communicate financial information | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Financial Education & Training | Provide financial education/training to staff as needed | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Cost Review & Savings | Analyse costs and recommend savings measures | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Financial Impact Assessment | Assess financial impact of proposed projects/initiatives | % | _n/a_ | 100% | Event-driven (per project/initiative; not a fixed calendar cadence) | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Physical & Digital Records | Maintain accurate, organised financial records in both formats | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Audit-Ready Accessibility | Ensure records are accessible for audits and reporting | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School Accountant | Year-End Closing | Facilitate year-end financial closing, reconciling accounts | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Annual Financial Reports | Prepare annual financial reports | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Fee Collection Reconciliation | Daily/weekly reconciliation of fee collection against the ERP admission/fee module | % | _n/a_ | 100% | daily | yes | Value Reading | n/a | Not Applicable on non-working days | none | No |
| School Accountant | Discount & Waiver Tracking | Fee discounts/waivers applied match the approved discount matrix | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Petty Cash Control | Petty cash disbursed only against approved vouchers | % | _n/a_ | 100% | weekly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Petty Cash Control | Petty cash reconciled | % | _n/a_ | 100% | weekly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Asset Register Maintenance | Fixed asset register maintained with purchase date, cost, and depreciation | % | _n/a_ | 100% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | Asset | Yes |
| School Accountant | Asset Register Maintenance | Physical verification of assets against register | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | Asset | Yes |
| School Accountant | Approval & Payment Separation | The person approving an expense is not the same person disbursing payment | % | _n/a_ | 100% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Periodic Independent Review | Financial records reviewed by someone outside routine processing (Principal/Central Finance) | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Access Control | Financial system access restricted to authorised personnel | % | _n/a_ | 100% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Accountant | Record Retention | Financial records retained per statutory minimum period | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |

---

**Performance review cadence:** The Accountant's performance against this KRA/KPI set is reviewed at least quarterly by the Principal / Central Finance Team.

**Manual review cadence:** This manual is reviewed at least once every academic year, or earlier where a regulatory or accounting-standard change requires an update.

---

### Role: `Facility Manager`

*Source manual: `TGS_Facility_Manager_KRA_KPI.docx`*

**Role overview:** The Facility Manager is responsible for the upkeep, safety, and functionality of the school's physical infrastructure — buildings, utilities, equipment, and vendor-executed maintenance work.

**Reporting line:** Operations Head — day-to-day supervision, budget approval, and incident escalation; Central Operations Team — coordination on CapEx, compliance, and vendor contracts

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Facility Manager | Facility Maintenance Oversight | Oversee maintenance of buildings, classrooms, playgrounds, and other facilities | % | ≥ | 95% planned tasks completed | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Facility Manager | Infrastructure Upkeep (Painting/Electrical/Plumbing/Carpentry) | Manage upkeep across trades | % | ≥ | 90% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Facility Manager | Infrastructure Upkeep (Painting/Electrical/Plumbing/Carpentry) | Infrastructure audit score | % | ≥ | 90% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Facility Manager | Cleanliness Auditing | Audit premises' cleanliness daily and report if not cleaned properly | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | Yes |
| Facility Manager | Cleanliness Auditing | Housekeeping audit score | % | ≥ | 90% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Facility Manager | Equipment Procurement Support | Support Operations Head on procurement/maintenance of essential equipment (projectors, computers, lab equipment) | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Utility Monitoring & Energy Conservation | Monitor water/electricity usage and manage conservation | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Utility Monitoring & Energy Conservation | YoY energy-consumption reduction | _n/a_ | _n/a_ | measurable target set annually | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Contractor & Vendor Engagement | Engage contractors/vendors for maintenance, repair, and construction | % | ≥ | 95% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Third-Party Service Delivery | Ensure timely delivery of services from third-party vendors | % | ≥ | 95% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Records Maintenance | Maintain records of building maintenance, safety inspections, repairs, and upgrades | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Facility Manager | Reporting to Administration | Prepare infrastructure reports for school administration | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| Facility Manager | Stakeholder Communication | Communicate updates on repairs, construction, or disruptions | % | _n/a_ | 100% | Event-driven (as repairs/disruptions occur; not a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Electrical Safety | Electrical wiring properly maintained and kept out of reach of students/staff | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Facility Manager | Construction Site Safety | All construction sites properly barricaded | % | _n/a_ | 100% | Event-driven (per active construction project) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Water Tank Cleaning | Water tanks cleaned | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Facility Manager | RO Water Quality (TDS Monitoring) | TDS level in RO water monitored | % | _n/a_ | 100% | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Fire Safety Equipment | Fire extinguishers, hose reels, and smoke detectors maintained and functional | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Facility Manager | Fire Safety Equipment | Evacuation routes clearly marked and unobstructed | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| Facility Manager | Fire Drills | Evacuation drills conducted as per statutory norms | % | ≥ | 95% | biannual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Lift Maintenance | Monthly operational/safety checks and annual certified inspection | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Lift Maintenance | Child-safety door sensors functional | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Electrical Control Panels | Monthly cleaning, cable-tightness checks, and thermal scanning | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Facility Manager | Pest Control | Pest control treatments conducted | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Waste Segregation & Disposal | Waste segregated (biodegradable / non-biodegradable / hazardous) at source | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Facility Manager | Waste Segregation & Disposal | Hazardous waste disposed via licensed handler with certificate on file | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Vendor Documentation | Mandatory vendor documents (MSME, GST, PAN, bank details) collected before onboarding | % | _n/a_ | 100% | Event-driven (per vendor onboarding) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Vendor Performance Review | Vendor performance reviewed on quality, timeliness, and cost | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Infrastructure Audits | Biannual infrastructure audit covering structural stability, classrooms, labs, and common spaces | % | _n/a_ | 100% | biannual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| Facility Manager | CapEx Request Tracking | CapEx requests prioritised by urgency/impact and tracked via project tracker | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | CapEx Request Tracking | Time from approval to completion | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| Facility Manager | Safety & Equipment Training | Facility team trained on fire safety, electrical safety, and emergency response | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Facility Manager | Safety & Equipment Training | Refresher training conducted | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |

---

**Note on this manual's coverage:** Sections 4–10 (Fire Safety, Lift & Electrical Maintenance, Pest Control & Waste Management, Vendor Management, CapEx & Audits, Compliance Calendar, and Training) should be confirmed by the Operations Head.

**Performance review cadence:** The Facility Manager's performance against this KRA/KPI set is reviewed at least quarterly by the Operations Head.

**Manual review cadence:** This manual is reviewed at least once every academic year, or earlier where a safety incident or regulatory change requires an update.

---

### Role: `School IT Manager`

*Source manual: `TGS_IT_Manager_KRA_KPI.docx`*

**Role overview:** The IT Manager is responsible for network infrastructure, device management, IT security, and technology support across the campus, ensuring reliable connectivity and functioning systems for staff and students.

**Reporting line:** Operations Head / Principal — day-to-day supervision and escalation; Central IT / Central Operations Team — coordination on security, licensing, and major upgrades

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| School IT Manager | Network Infrastructure | Monitor and maintain wired/wireless network | % | ≥ | 99% | daily | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | Yes |
| School IT Manager | Network Infrastructure | Network issue resolution TAT | hours | ≤ | 4 hours for standard faults | monthly | no | Value + Event Time | Resolution Time | Skip (default — not specified per manual) | none | Yes |
| School IT Manager | Hardware & Software Currency | Hardware/software kept up-to-date | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Hardware & Software Currency | Software meets educational delivery needs | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Vendor Coordination for Repairs/Upgrades | Vendor-dependent repair/upgrade TAT | % | _n/a_ | 100% | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Network Security Protocols | Security protocols implemented and monitored | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| School IT Manager | Network Security Protocols | Security incidents | hours | _n/a_ | 24 hours | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Device Management (computers, tablets, interactive boards) | Device inventory accuracy | % | ≥ | 98% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Device Management (computers, tablets, interactive boards) | Devices functional and ready for use | % | ≥ | 95% uptime | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Device Maintenance & Troubleshooting | Scheduled maintenance completion | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Device Maintenance & Troubleshooting | Device fault resolution TAT | hours | ≤ | 24 hours for classroom-critical devices | monthly | no | Value + Event Time | Resolution Time | Skip (default — not specified per manual) | Asset/Location | No |
| School IT Manager | IT Inventory Management | Inventory of computers, software, and peripherals maintained | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | IT Inventory Management | Inventory audit completed | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School IT Manager | Device Setup & Configuration | New device setup/configuration TAT | hours | ≤ | 48 hours from request | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Device Setup & Configuration | Staff/student accessibility confirmed at handover | % | _n/a_ | 100% | Event-driven (per device handover; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Firewall & Antivirus Management | Firewalls and antivirus configured and monitored | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| School IT Manager | Firewall & Antivirus Management | Security alerts reviewed and actioned | hours | _n/a_ | 2 hours | daily | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| School IT Manager | CCTV Blind-Spot Identification | Blind-spot survey conducted | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School IT Manager | CCTV Blind-Spot Identification | Identified blind spots actioned (camera installed) | days | _n/a_ | 30 days | event-triggered | yes | Value Reading | n/a | Skip (default — not specified per manual) | Asset | Yes |
| School IT Manager | CCTV Monitoring & Footage Retention | Premises monitored on screen during school hours | % | _n/a_ | 100% | daily | yes | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| School IT Manager | CCTV Monitoring & Footage Retention | CCTV footage retained | month | _n/a_ | 1 month | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School IT Manager | Security Audits | Regular security audits of systems/networks | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Security Audits | Audit findings remediated | % | ≥ | 95% within 30 days | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School IT Manager | New Employee Smart Class Training | Smart class training delivered to every new employee | % | _n/a_ | 100% | Event-driven (per new hire; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | New Employee Smart Class Training | Training record maintained for every session | % | _n/a_ | 100% | Event-driven (per training session; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | PW Application Knowledge (Student Batch Issues) | Working knowledge of PW applications for batch-related issue resolution | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value + Event Time | Resolution Time | Skip (default — not specified per manual) | none | No |
| School IT Manager | PW Application Knowledge (Student Batch Issues) | Batch-related issue resolution TAT | hours | ≤ | 4 hours | monthly | no | Value + Event Time | Resolution Time | Skip (default — not specified per manual) | none | No |
| School IT Manager | Backup & Recovery | Scheduled backup (ERP data, CCTV footage, key school records) completion | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | Location | Yes |
| School IT Manager | Backup & Recovery | Backup restoration tested | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Backup & Recovery | Recovery time objective (RTO) for critical systems | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | biannual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Access & Password Governance | Tiered access-level system maintained for staff/student accounts | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Access & Password Governance | Password policy (minimum length, rotation) enforced | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Access & Password Governance | Access logs reviewed periodically for anomalies | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Support Ticket SLA | Critical (system-wide outage) | minutes | ≤ | 30 minutes | monthly | no | Value + Event Time | Response Time | Skip (default — not specified per manual) | none | No |
| School IT Manager | Support Ticket SLA | High (multi-user/department issue) | hour | ≤ | 1 hour | monthly | no | Value + Event Time | Response Time | Skip (default — not specified per manual) | none | No |
| School IT Manager | Support Ticket SLA | Medium (single-user issue) | hours | ≤ | 4 hours | monthly | no | Value + Event Time | Response Time | Skip (default — not specified per manual) | none | No |
| School IT Manager | Support Ticket SLA | Low (minor/routine) | hours | ≤ | 24 hours | monthly | no | Value + Event Time | Response Time | Skip (default — not specified per manual) | none | No |
| School IT Manager | Licensing Compliance | All installed software covered by valid licence | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Licensing Compliance | Licence renewal tracked against expiry | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Asset Lifecycle Management | AMC renewal tracked and actioned | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Asset Lifecycle Management | Assets nearing end-of-life flagged for replacement | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | Asset | No |
| School IT Manager | Data Privacy | Role-restricted access to student/staff personal data | % | _n/a_ | 100% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Data Privacy | Data retention/purge policy applied to non-active records | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Network outage (campus-wide) | IT Manager → Operations Head, immediate; vendor engaged within 30 minutes if hardware-related | minutes | _n/a_ | 30 minutes | Event-driven (as incidents occur; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Security breach / suspected intrusion | IT Manager → Operations Head + Central IT, immediate | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as incidents occur; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | CCTV/camera blind spot or failure | IT Manager → Facility Manager (for installation) + Central Team, within 24 hours | hours | _n/a_ | 24 hours | Event-driven (as incidents occur; not on a fixed calendar cadence) | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School IT Manager | Device fault affecting a classroom | IT Manager → resolve or escalate to vendor within 24 hours | hours | _n/a_ | 24 hours | Event-driven (as incidents occur; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School IT Manager | Licence lapse or compliance gap | IT Manager → Central Operations, before renewal deadline | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as incidents occur; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |

---

**Note on this manual's coverage:** Sections 5–10 were added to close gaps in the original role list and should be confirmed by the Operations Head / Central IT Team.

**Performance review cadence:** The IT Manager's performance against this KRA/KPI set is reviewed at least quarterly by the Operations Head.

**Manual review cadence:** This manual is reviewed at least once every academic year, or earlier where a security incident or system change requires an update.

---

### Role: `School Store In-Charge`

*Source manual: `TGS_Store_Incharge_KRA_KPI.docx`*

**Role overview:** The Store In-Charge is responsible for the day-to-day management of the school store — stock accuracy, safety, and service quality — and is the frontline owner of the inventory processes defined in the Inventory Management & Procurement SOP.

**Reporting line:** Operations Head / Operations Manager — day-to-day supervision and approval of stock/procurement requests; Central Operations Team — dotted-line coordination on audits, monthly reporting, and vendor matters

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| School Store In-Charge | Stock Record Accuracy | Maintain accurate stock records | % | ≥ | 98% | daily | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Stock Record Accuracy | Reorder inventory before stockout | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Stock Record Accuracy | Conduct regular stock audits | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Stock Rotation | Implement efficient stock rotation (FIFO/FEFO) | % | _n/a_ | 100% | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Stock Rotation | Expired/near-expiry items flagged before use | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Service Quality | Polite and efficient service to students and staff | _n/a_ | ≤ | X/month | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Service Quality | Handle inquiries and complaints professionally | hours | ≤ | 2 hours | daily | no | Value + Event Time | Response Time | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Store Environment | Maintain a clean and organised store | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | Yes |
| School Store In-Charge | Store Environment | Store audit (cleanliness/organisation) score | % | ≥ | 90% | daily | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| School Store In-Charge | Storage & Layout Safety | Ensure proper storage of items to prevent accidents | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Storage & Layout Safety | Maintain clear pathways and exits | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| School Store In-Charge | Hazard Monitoring | Regularly check for potential hazards (e.g., wet floors) | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | Yes |
| School Store In-Charge | Hazard Monitoring | Hazard rectification TAT | hours | ≤ | 24 hours | event-trigerred | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| School Store In-Charge | Product Safety & Expiry | Ensure all products meet safety standards | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Product Safety & Expiry | Check expiration dates regularly | % | _n/a_ | 100% | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Fire & Emergency Readiness | Ensure fire extinguishers are in place and functional | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Fire & Emergency Readiness | Fire drill participation | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | biannual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| School Store In-Charge | Theft & Access Control | Implement measures to prevent theft | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Theft & Access Control | Monitor store area to prevent unauthorised access | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| School Store In-Charge | Systems & Equipment Training | Hands-on training for ERP systems and inventory management | % | _n/a_ | 100% | Event-driven (per new hire; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Systems & Equipment Training | Training on proper use of equipment and safety gear | % | _n/a_ | 100% | Event-driven (per new hire; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Inventory Tagging & Product Knowledge | Learn inventory tagging system | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (per new hire; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Inventory Tagging & Product Knowledge | Keep updated on new products and their features | _n/a_ | ≥ | quarterly | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Handling & Storage Practices | Learn proper storage and handling of different product types | % | _n/a_ | 100% | Event-driven (per new hire; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Handling & Storage Practices | Practical assessment pass rate | % | _n/a_ | 100% | Event-driven (per training cycle; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Registers & Documentation | Gate entry register, stock sheet, distribution register, and approval-slips file maintained 100% accurately | % | _n/a_ | 100% | daily | no | Value + Event Time | n/a | Not Applicable on non-working days | Location | No |
| School Store In-Charge | Registers & Documentation | Daily consumption sheet filled same-day with no blank fields | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| School Store In-Charge | Reporting Cadence | Weekly consumption sheet presented every review meeting | % | _n/a_ | 100% | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Reporting Cadence | Support Central Team's monthly consumption report with complete, accurate data | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Low-Stock Escalation | Minimum stock thresholds defined and monitored | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Low-Stock Escalation | Low-stock approval email sent to Operations Manager same day threshold is hit | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as threshold is hit; not on a fixed calendar cadence) | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | New/Unavailable Items | New or locally unavailable items escalated to Operations within 24 hours | hours | _n/a_ | 24 hours | Event-driven (as items arise; not on a fixed calendar cadence) | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Goods Receipt | Gate registration and delivery verification completed for 100% of deliveries | % | _n/a_ | 100% | Event-driven (per delivery; not on a fixed calendar cadence) | no | Value Reading | n/a | Not Applicable on non-working days | Location | No |
| School Store In-Charge | Goods Receipt | Damage/mismatch reported to Central Operations same day, with photos and documentation | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as damage/mismatch occurs; not on a fixed calendar cadence) | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | Yes |
| School Store In-Charge | Approval & Value Control | No item distributed without a valid, approved demand slip | % | _n/a_ | 100% | Event-driven (per distribution; not on a fixed calendar cadence) | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| School Store In-Charge | Approval & Value Control | Stock value reconciliation matches book value | _n/a_ | ≤ | defined threshold at each audit | monthly | yes | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |

---

**Note on this manual's coverage:** Sections 5–9 were added to align this KRA document with the full Inventory Management & Procurement SOP and should be confirmed by the Operations Head.

**Performance review cadence:** The Store In-Charge's performance against this KRA/KPI set is reviewed at least quarterly by the Operations Head.

**Manual review cadence:** This manual is reviewed at least once every academic year, or earlier where the Inventory Management & Procurement SOP is updated.

---

### Role: `Security Guard (Bilingual — English/Hindi source)`

*Source manual: `TGS_Security_Guard_KRA_Bilingual.docx`*

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Security Guard (Bilingual — English/Hindi source) | Premises patrol & monitoring | परिसर गश्त और निगरानी | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Security Guard (Bilingual — English/Hindi source) | Entry/exit log accuracy | प्रवेश/निकास लॉग सटीकता | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| Security Guard (Bilingual — English/Hindi source) | Visitor registration & verification | आगंतुक पंजीकरण और सत्यापन | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| Security Guard (Bilingual — English/Hindi source) | CCTV/alarm/communication equipment check | सीसीटीवी/अलार्म/संचार उपकरण जांच | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | yes | Value + Event Time | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | Yes |
| Security Guard (Bilingual — English/Hindi source) | Door/key/utility open-close routine | दरवाज़ा/चाबी/उपयोगिता खोलना-बंद करना | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| Security Guard (Bilingual — English/Hindi source) | Generator operation on power failure | बिजली जाने पर जनरेटर संचालन | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as power failures occur; not on a fixed calendar cadence) | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| Security Guard (Bilingual — English/Hindi source) | Student safety during arrival/departure | आगमन/प्रस्थान के दौरान छात्र सुरक्षा | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Security Guard (Bilingual — English/Hindi source) | Incident reporting | घटना रिपोर्टिंग | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as incidents occur; not on a fixed calendar cadence) | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| Security Guard (Bilingual — English/Hindi source) | Emergency contact readiness | आपातकालीन संपर्क तैयारी | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Applicable — capture continues on non-working days (always-on / 24x7 duty) | none | No |
| Security Guard (Bilingual — English/Hindi source) | Emergency response time | आपातकालीन प्रतिक्रिया समय | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as emergencies occur; not on a fixed calendar cadence) | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| Security Guard (Bilingual — English/Hindi source) | Unauthorised access attempt | अनधिकृत प्रवेश प्रयास | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as incidents occur; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Security Guard (Bilingual — English/Hindi source) | Suspicious activity / hazard | संदिग्ध गतिविधि / जोखिम | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as incidents occur; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Security Guard (Bilingual — English/Hindi source) | Fire / medical / major emergency | आग / चिकित्सा / बड़ी आपात स्थिति | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as incidents occur; not on a fixed calendar cadence) | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Security Guard (Bilingual — English/Hindi source) | Equipment fault (CCTV/alarm/generator) | उपकरण खराबी (सीसीटीवी/अलार्म/जनरेटर) | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as incidents occur; not on a fixed calendar cadence) | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | Yes |
| Security Guard (Bilingual — English/Hindi source) | Child release / custody concern | छात्र रिलीज़ / अभिरक्षा संबंधी चिंता | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as incidents occur; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |

---

**Manual review cadence:** This manual is reviewed at least once every academic year, or earlier where a security incident or regulatory change requires an update. Sections 3–10 were added to close gaps in the original role list and should be confirmed by the Operations Head.

---

### Role: `Marketing Manager`

*Source manual: `TGS_Marketing_Manager_KRA_KPI.docx`*

**Role overview:** The Marketing Manager is responsible for driving student admissions through brand-building, marketing strategy, digital presence, public relations, and community engagement, working closely with the counselling and admissions team.

**Reporting line:** Principal / Central Admissions Head — day-to-day coordination and target alignment; Central Marketing Team — brand guidelines, campaign approval, and budget consolidation

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Marketing Manager | Counselling Team Coordination | Work closely with the counselling team to drive admissions | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Enrolment Growth Strategy | Develop and implement strategies to increase enrolment across grades | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Admissions Target Achievement | Meet admissions targets for each academic session | % | ≥ | 95% of session target achieved | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Brand Identity Consistency | Maintain brand identity consistency across all marketing materials | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Reputation & Visibility | Enhance the school's reputation and visibility in the community | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Marketing Manager | Marketing Plan Development | Develop comprehensive marketing plans aligned with school objectives | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Marketing Manager | USP Communication Materials | Develop materials communicating the school's unique selling propositions | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Marketing Manager | Market & Competitor Analysis | Identify market trends and analyse competitor activity, adjusting strategy accordingly | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Data-Driven Decision Making | Use data to improve marketing strategies | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Admissions-Aligned Digital Materials | Work with admissions to develop digital materials communicating USPs | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Digital Enrolment Strategy | Implement digital strategies to increase enrolment and meet targets | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Media & Stakeholder Relationships | Maintain relationships with local media and community stakeholders | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | PR for Achievements & Events | Manage PR efforts highlighting school achievements and events | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Marketing Manager | Promotional Events & Open Houses | Plan and execute promotional events, open houses, and school tours | % | _n/a_ | 100% | Event-driven (per event; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Marketing Manager | Promotional Events & Open Houses | Attendee-to-inquiry conversion at events | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (per event; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Local Partnerships | Establish partnerships with local businesses, community organisations, and institutions | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Budget Development & Management | Develop and manage the marketing budget effectively | % | ≤ | ±5% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Campaign Effectiveness Analysis | Analyse marketing data/metrics to evaluate campaign effectiveness | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Return on Investment | Ensure effective ROI on marketing spend | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Content Calendar & Posting | Regular organic and paid content across social platforms | % | _n/a_ | 100% | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Engagement & Growth | Grow follower base and engagement rate | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Photography, Video & Collateral | Produce photography, video, and print collateral for campaigns and events | % | _n/a_ | 100% | Event-driven (per campaign/event; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Asset Library Management | Maintain an organised, up-to-date media asset library | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | annual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | Asset | No |
| Marketing Manager | Lead Source Tracking | Track inquiries by marketing source/channel in the ERP/CRM | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Funnel Conversion Reporting | Report inquiry-to-admission conversion by channel | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Website Content Accuracy | School website content kept accurate and current (fees, admissions, events) | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Marketing Manager | Search Visibility | Maintain/improve organic search ranking for key admissions terms | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Competitor Fee & Offering Review | Competitor fee structures and offerings reviewed ahead of each admission cycle | % | _n/a_ | 100% | annual (ahead of each admission cycle) | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Agency/Vendor Onboarding & Quotes | Marketing vendors/agencies selected via quotation comparison | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | Event-driven (as vendor needs arise; not on a fixed calendar cadence) | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Vendor Performance Review | Vendor/agency performance reviewed on delivery quality and timeliness | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Negative Publicity / Complaint Response | Negative media/social mentions acknowledged and responded to | hours | _n/a_ | 24 hours | monthly | no | Value + Event Time | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Crisis Communication Protocol | Crisis communication protocol followed for reputation-sensitive incidents, in coordination with the Principal | % | _n/a_ | 100% | Event-driven (as incidents occur; not on a fixed calendar cadence) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Alumni Relationship Maintenance | Maintain alumni engagement channels | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Referral Programme Tracking | Referral-sourced admissions tagged and tracked | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Truthful & Compliant Advertising | All marketing claims (fees, results, facilities) are accurate and verifiable | % | _n/a_ | 100% | quarterly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Marketing Manager | Brand & IP Usage | No unauthorised use of third-party brands, images, or copyrighted material in campaigns | % | _n/a_ | 100% | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |

---

**Performance review cadence:** The Marketing Manager's performance against this KRA/KPI set is reviewed at least quarterly by the Principal / Central Admissions Head.

**Manual review cadence:** This manual is reviewed at least once every academic year, or earlier where a major campaign, brand, or strategy shift requires an update.

---

### Role: `Telecaller`

*Source manual: `TGS_Telecaller_KRA_KPI.docx`*

**Role overview:** The Telecaller is responsible for outbound and inbound calling to prospective parents/guardians, converting inquiries into school visits and admissions, and maintaining accurate records of every interaction.

**Reporting line:** Counsellor Lead — day-to-day supervision, call quality review, and daily targets; Marketing Lead — coordination on lead source and campaign follow-up

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Telecaller | Outbound Lead Generation | Generate leads through outbound calls to potential parents/guardians | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Telecaller | School Information Delivery | Provide accurate information on curriculum, facilities, and admission process | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Telecaller | Lead Nurturing & Walk-in Conversion | Follow up with prospective parents to nurture leads and drive walk-ins | _n/a_ | ≥ | defined target | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Telecaller | Database Accuracy | Maintain and update CRM with correct dispositions and call notes | % | _n/a_ | 100% | daily | yes | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Telecaller | Interaction Tracking & Follow-Up | Track customer interactions and ensure timely follow-ups | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Telecaller | Multi-Channel Communication | Execute communication plans across channels (email, WhatsApp, phone) | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Telecaller | Personalised Interaction | Personalise interactions to strengthen customer connections | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Telecaller | Counsellor/Principal Appointments | Schedule appointments for school counsellors or Principal with prospective parents | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | No |
| Telecaller | Reminders & No-Show Reduction | Send reminders to staff and parents ahead of appointments | _n/a_ | ≤ | defined threshold | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Telecaller | Cross-Department Support | Provide administrative support to other departments (event coordination, data entry, etc.) | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Telecaller | Call Quality Monitoring | Calls monitored/audited for tone, accuracy, and script adherence | _n/a_ | ≥ | defined target | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Telecaller | Complaint & Escalation Handling | Parent complaints on call handling | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Telecaller | Daily Call Targets | Minimum outbound calls per day achieved | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |
| Telecaller | Talk-Time & Utilisation | Productive talk-time as a share of shift hours | _n/a_ | ≥ | defined target | daily | no | Value + Event Time | TAT/Response Time (point not named in manual) | Not Applicable on non-working days | none | No |
| Telecaller | Consent & Data Handling | Parent/guardian data collected and used only for admission-related communication with appropriate consent | % | _n/a_ | 100% | weekly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Telecaller | Do-Not-Call / Preference Compliance | Do-not-call requests and call-time restrictions honoured | % | _n/a_ | 100% | weekly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Telecaller | Duplicate Lead Handling | Duplicate leads identified and merged in the CRM before repeat calling | % | _n/a_ | 100% | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Telecaller | Stale/Inactive Lead Review | Non-converted leads reviewed and archived per the data retention policy | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Telecaller | Induction & Product Training | New telecaller induction on school offering, fee structure, and CRM tool | % | _n/a_ | 100% | event-triggered (on joining) | yes | Value Reading | n/a | Skip (default — not specified per manual) | Location | No |
| Telecaller | Ongoing Skills Refresh | Refresher training on communication skills and CRM updates | _n/a_ | _n/a_ | _target not numerically specified in manual — see description_ | quarterly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Telecaller | Shift & Attendance Compliance | Attendance and shift timing adherence | _n/a_ | ≥ | defined target | daily | no | Value Reading | n/a | Not Applicable on non-working days | none | No |

---

**Performance review cadence:** The Telecaller's performance against this KRA/KPI set is reviewed at least monthly by the Counsellor Lead.

**Manual review cadence:** This manual is reviewed at least once every academic year, or earlier where CRM tools or calling processes change.

---

## 3. D1 (Q3) and D3 (Q5) — now resolved

- **D1 (formerly Q3)** — RESOLVED: Marketing Manager and Telecaller KPIs
  are in-platform for Phase 1 (see `assumptions-log.md`). They are no
  longer held — the two role sections above (§2) are released for SME
  column review and Prompt 6 import along with the other 8 roles.
- **D3 (formerly Q5)** — RESOLVED: the minimum-viable taxonomy for schools
  without a supplied role manual is the 5-category **Core KRA Set** below
  (§2a), applied by default, with role-manual KPIs layered on top where a
  manual exists.
- **Sensitive/financial flagging** — PRS §16 risk table and R-50 both depend
  on knowing *which* KPIs are financial/sensitive. SME-reviewed and
  approved 2026-08-08 (see the review checklist / `assumptions-log.md`) —
  this data-quality pass is now closed, corrections go through the master
  dashboard post-launch.
- **v1.5 columns (Capture Type, Event Time Points, Non-Working-Day Policy,
  Asset/Location scoping)** — not stated explicitly in any of the ten
  manuals; first-pass inferences have been SME-reviewed and approved
  2026-08-08 — closed, unaffected by D1/D3.

### 2a. Core KRA Set (D3 — applies to any School without a supplied role manual)

Derived from the categories that recur across all 10 supplied role manuals,
not invented from scratch. Applied as the default taxonomy for a School with
no matching role manual; role-manual KPIs are layered on top wherever a
manual is supplied for that School's staff roles. Targets below are Phase 1
starting defaults (configurable per School via the Configuration Engine, same
as any other KPI). The six reviewed columns plus Evidence Required are
SME-approved (2026-08-08) same as every other role tab in this file.

| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Core (no role manual) | Safety | Safety incidents reported and logged within policy window | % | _n/a_ | 100% | daily | no | Value Reading | n/a | Not Applicable on non-working days | Location | No |
| Core (no role manual) | Safety | Hazard rectification TAT | hours | ≤ | 24 hours | event-triggered | no | Value + Event Time | Resolution Time | Skip (default — not specified per manual) | Location | Yes |
| Core (no role manual) | Safety | Fire/emergency drills conducted as per statutory norms | % | ≥ | 95% | annual (twice yearly) | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Core (no role manual) | Academics | Academic standards and student achievement monitored against defined targets | _n/a_ | ≥ | defined target | termly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Core (no role manual) | Academics | Staff meetings held to review academic progress | % | _n/a_ | 100% | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Core (no role manual) | Facilities | Preventive maintenance compliance | % | ≥ | 95% planned tasks completed | monthly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| Core (no role manual) | Facilities | Cleanliness audit compliance | % | ≥ | 90% | weekly | no | Value Reading | n/a | Skip (default — not specified per manual) | Location | Yes |
| Core (no role manual) | Finance (basic) | Budget variance | % | ≤ | ±5% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Core (no role manual) | Finance (basic) | Monthly financial reporting accuracy | % | _n/a_ | 100% | monthly | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Core (no role manual) | Staff Compliance | Mandatory statutory training and background checks completed | % | _n/a_ | 100% | annual | yes | Value Reading | n/a | Skip (default — not specified per manual) | none | No |
| Core (no role manual) | Staff Compliance | Staff performance reviews completed on cycle | % | _n/a_ | 100% | annual | no | Value Reading | n/a | Skip (default — not specified per manual) | none | No |



## 4. Import mechanics (for whoever builds the importer)

- One School cannot go Active until departments **and KPI library import**
  succeed (PRS §52 validation rule) — so this file (once reviewed) is a
  Phase 1 launch blocker per school, not a nice-to-have.
- KPIs are versioned from the moment they're created (R-17) — the *first*
  import is version 1 of each KPI; there is no "unversioned seed" exception.
- Only SuperAdmin can create/modify entries in the Global KPI Library
  (R-43/BR-04) — the import tool should run under a SuperAdmin identity, not
  a special seeding bypass that skips the permission model.
- **(v1.5)** Where a KPI is Asset-scoped (e.g., per-vehicle bus KPIs),
  the referenced Asset must already exist as an Active Asset record (BR-23)
  — the importer should not create bare Asset stubs on the fly; Assets are
  seeded separately (or created via the Settings/Master Data UI) before KPI
  import references them.