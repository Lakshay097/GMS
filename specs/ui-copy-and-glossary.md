# UI Copy & Glossary — School Operations & Governance Platform

Purpose: collect English + Hindi strings (PRS §6/phases.md §1.1 localization
requirement) in one place so terminology stays consistent across 10+ modules
built in separate Devin sessions, instead of "Discrepancy" becoming "Issue"
in one module and staying "Discrepancy" in another.

**Hindi strings below are a starting draft, not final copy** — have a native
Hindi speaker familiar with Indian school-administration terminology review
every row before shipping. Machine-consistent terminology across modules
matters more than any single translation being perfect on day one; get the
review done once this file is populated, not per-module.

---

## 1. Core Business Glossary (source: PRS §15)

| Term (EN) | Definition | Hindi (draft) | Notes |
|---|---|---|---|
| KRA | Key Result Area — governance category grouping related KPIs | मुख्य परिणाम क्षेत्र (KRA) | Keep "KRA" as a bracketed abbreviation even in Hindi UI — staff already use the English acronym in manuals. |
| KPI | Key Performance Indicator — measurable target belonging to exactly one KRA | मुख्य प्रदर्शन संकेतक (KPI) | Same abbreviation-retention approach as KRA. |
| Observation | A single captured reading/evidence entry against a KPI, made by a Checker | अवलोकन | |
| Auto-Result | System-computed evaluation (Met/Not Met/N/A) | स्वतः-परिणाम | Never let this be manually entered — copy should make clear it's system-generated (e.g., a lock icon or "System Computed" badge). |
| Discrepancy | Formal record raised by an Auditor when an Observation doesn't match verification evidence | विसंगति | Do not translate as "समस्या" (problem) in some modules and "विसंगति" in others — pick one and keep it everywhere. |
| Escalation Matrix | Configurable, ordered chain of users/roles with SLA timers | एस्केलेशन मैट्रिक्स | Keep "एस्केलेशन" transliterated rather than translating "escalation" — this is common practice in Indian enterprise software and avoids ambiguity. |
| Primary Owner | User with direct accountability for a Task; multiple may exist per task | प्राथमिक स्वामी | |
| ETA | Estimated Time of Arrival/completion for a Task; extendable up to 3 times | अनुमानित पूर्णता समय (ETA) | Keep the "ETA" abbreviation bracketed. |
| Scorecard | Immutable, versioned, auto-generated performance summary | स्कोरकार्ड | |
| Lock Period | Configurable duration after which an Observation becomes immutable | लॉक अवधि | |
| Global KPI Library | Single, centrally governed catalogue of all KPIs org-wide | वैश्विक केपीआई लाइब्रेरी | |
| Discrepancy Category *(v1.5)* | Classification assigned to a Discrepancy at creation; determines its Approval Chain | विसंगति श्रेणी | Immutable once set on a Discrepancy — copy should not imply it can be changed later. |
| Approval Chain *(v1.5)* | Configured sequence of up to two approval levels (role + order) a Discrepancy Category routes through before Closure | अनुमोदन श्रृंखला | Distinct from a single "Approve" action — UI should show "Level 1 of 2," not a flat approve button, when a chain has 2 levels. |
| Holiday Calendar *(v1.5)* | Organization/School-scoped list of non-working days used by the Compliance Scheduler | अवकाश कैलेंडर | |
| Working Days *(v1.5)* | Per-School (or per-KPI override) definition of which weekdays are working days | कार्य दिवस | |
| Grace Period *(v1.5)* | Configurable window after a KPI's due date during which a Late submission is still accepted without Admin approval | अनुग्रह अवधि | |
| Closed-Missed *(v1.5)* | State a compliance record enters once its Grace Period elapses with no submission | बंद-चूका हुआ | Distinct from "Overdue" — Overdue is still submittable; Closed-Missed requires a Reopen approval first. |
| Reopen *(v1.5)* | Admin/SuperAdmin-approved action restoring submittability to a Closed-Missed record | पुनः खोलें | |
| Duplicate Observation *(v1.5)* | A second Observation attempt matching an existing one on KPI version + scope + Checker within the Duplicate Detection Window | डुप्लिकेट अवलोकन | |
| Override *(v1.5)* | Justified, logged action permitting submission of a detected duplicate | ओवरराइड | Always pair with a visible mandatory-justification field in the UI — never a bare confirm button. |
| Evidence Retention Period *(v1.5)* | Configured duration after which an evidence file becomes eligible for deletion (not auto-deleted) | साक्ष्य प्रतिधारण अवधि | Copy must not imply automatic deletion — deletion is always a separate, explicit Admin action. |
| Asset *(v1.5)* | A tracked physical unit (vehicle, cleaning zone, etc.) referenced by Event Time Observations; Active or Retired, never deleted | परिसंपत्ति (एसेट) | |
| Event Time *(v1.2)* | The actual clock time an operational event occurred, distinct from Submitted At | घटना समय | |
| Time Capture Mode *(v1.2)* | Whether an Event Time was Auto-Captured or Manually Entered | समय कैप्चर मोड | Always show which mode was used wherever Event Time is displayed — never merge Auto and Manual without indicating which. |

## 2. Role Names (PRS §11)

| Role (EN) | Hindi (draft) |
|---|---|
| SuperAdmin | सुपर एडमिन |
| Admin | एडमिन |
| Checker | चेकर |
| Auditor | ऑडिटर |
| Viewer | दर्शक / व्यूअर |

## 3. Status / State Labels

Used across Observations, Discrepancies, Tasks, Checklists — keep these
identical wherever they appear rather than re-labeling per module:

| Status (EN) | Hindi (draft) | Used by |
|---|---|---|
| Draft | प्रारूप | Tasks, Checklists |
| Submitted | प्रस्तुत | Observations |
| Locked | लॉक्ड | Observations (post lock-period) |
| Verified | सत्यापित | Observations (post-audit) |
| Open | खुला | Discrepancies, Tasks |
| Investigation | जांच जारी | Discrepancies |
| Resolved | हल किया गया | Discrepancies |
| Approved | स्वीकृत | Discrepancies |
| Closed | बंद | Discrepancies |
| In Progress | प्रगति में | Tasks |
| Completed | पूर्ण | Tasks |
| Overdue | विलंबित / समय-सीमा पार | Tasks, KPIs |
| Escalated | एस्केलेटेड | Tasks, Discrepancies |
| Active | सक्रिय | Schools, Users, KPIs |
| Deactivated | निष्क्रिय | Schools |
| Archived | संग्रहीत | Departments, Users |
| Deprecated | अप्रचलित | KPI versions |
| Superseded | प्रतिस्थापित | Scorecard/KPI versions |
| Pending Approval (L1/L2) *(v1.5)* | अनुमोदन लंबित (स्तर 1/2) | Discrepancies |
| Late *(v1.5)* | विलंबित (देर से) | Observations, KPI compliance records |
| Closed-Missed *(v1.5)* | बंद-चूका हुआ | KPI compliance records |
| Reopened *(v1.5)* | पुनः खोला गया | KPI compliance records |
| Retired *(v1.5)* | सेवामुक्त | Assets |

## 4. RAG Status Labels

| Status | Hindi (draft) | Color convention |
|---|---|---|
| Green (Met) | हरा (लक्ष्य पूर्ण) | Standard green |
| Amber (Within tolerance, at risk) | एम्बर (सीमा के भीतर, जोखिम में) | Standard amber/yellow |
| Red (Not Met) | लाल (लक्ष्य अपूर्ण) | Standard red |
| N/A | लागू नहीं | Neutral gray |

## 5. Notification Templates (source: PRS §49 Notification Matrix)

For each event, keep subject line short, body includes the specific
entity name/ID, and every notification links directly to the relevant
record — don't make the recipient navigate to find what triggered it.

| Priority | Event | EN Subject Template | Hindi Subject Template (draft) |
|---|---|---|---|
| 1 — Escalation | Escalation Level Triggered | "Escalation: {entity_type} {entity_id} requires your attention" | "एस्केलेशन: {entity_type} {entity_id} पर तुरंत ध्यान दें" |
| 2 — Audit Failure | Audit Failed / Discrepancy Raised | "Discrepancy raised on Observation {observation_id}" | "अवलोकन {observation_id} पर विसंगति दर्ज की गई" |
| 3 — Task Assignment | Task Assigned | "New task assigned: {task_title}" | "नया कार्य सौंपा गया: {task_title}" |
| 4 — Due Today | Task or KPI due today | "Due today: {entity_title}" | "आज देय: {entity_title}" |
| 5 — KPI Reminder | Reminder before due | "Reminder: {kpi_name} due {due_date}" | "अनुस्मारक: {kpi_name} की देय तिथि {due_date}" |
| 6 — Comments | Task Comment / @Mention | "{user_name} mentioned you on {task_title}" | "{user_name} ने आपको {task_title} पर उल्लेख किया" |
| 7 — Informational | Created/Changed events | "{entity_type} {entity_name} was {action}" | "{entity_type} {entity_name} को {action} किया गया" |

Reminder in copy for categories 1 and 2: these **cannot be muted** (R-39) —
consider surfacing this fact in the notification-settings UI itself (e.g.,
a disabled toggle with a tooltip: "Escalation and Audit Failure alerts are
mandatory and cannot be turned off") rather than silently ignoring a mute
attempt, so users understand why the toggle doesn't move.

## 6. Common Action Labels (keep identical across every module)

| Action (EN) | Hindi (draft) |
|---|---|
| Save | सहेजें |
| Submit | प्रस्तुत करें |
| Cancel | रद्द करें |
| Approve | स्वीकृत करें |
| Reject | अस्वीकार करें |
| Archive | संग्रहीत करें |
| Deactivate | निष्क्रिय करें |
| Extend ETA | ETA बढ़ाएं |
| Raise Discrepancy | विसंगति दर्ज करें |
| Verify | सत्यापित करें |
| Export | निर्यात करें |
| View History | इतिहास देखें |
| Override *(v1.5)* | ओवरराइड करें |
| Request Reopen *(v1.5)* | पुनः खोलने का अनुरोध करें |
| Approve Reopen *(v1.5)* | पुनः खोलना स्वीकृत करें |
| Retire Asset *(v1.5)* | परिसंपत्ति सेवामुक्त करें |

## 7. Structured Error Message Copy (pairs with API-Spec §3 error codes)

Keep user-facing error text short, specific, and actionable — never expose
raw DB/stack-trace text to the client. Match these to the `error.code`
values from the API contract:

| Error Code | EN User-Facing Message | Hindi (draft) |
|---|---|---|
| VALIDATION_ERROR | "{field} is invalid: {reason}" | "{field} अमान्य है: {reason}" |
| PERMISSION_DENIED | "You don't have permission to do this." | "आपके पास यह करने की अनुमति नहीं है।" |
| SCOPE_NOT_FOUND | "This record doesn't exist or isn't available to you." | "यह रिकॉर्ड मौजूद नहीं है या आपके लिए उपलब्ध नहीं है।" *(deliberately identical wording for 404 whether the record is missing or out-of-scope — see R-06/API-Spec §3, never reveal cross-tenant existence)* |
| CONFLICT | "This action conflicts with an existing record: {detail}." | "यह क्रिया एक मौजूदा रिकॉर्ड से टकराती है: {detail}।" |
| BUSINESS_RULE_VIOLATION | "This isn't allowed: {reason}." | "यह अनुमति नहीं है: {reason}।" |
| DUPLICATE_DETECTED *(v1.5)* | "This looks like a duplicate of an existing entry. Review it below, or override with a reason." | "यह किसी मौजूदा प्रविष्टि की डुप्लिकेट लगती है। नीचे समीक्षा करें, या कारण देकर ओवरराइड करें।" *(pair with the prior Observation's summary inline, per PRS §24.6 — never just a bare block message)* |
| SERVER_ERROR | "Something went wrong on our end. It's been logged — please try again." | "हमारी ओर से कुछ गलत हुआ। इसे लॉग कर लिया गया है — कृपया पुनः प्रयास करें।" |

## 8. Locale Switching Behavior

- Locale is a Configuration Engine value (PRS §54) — the UI should read the
  active locale from config, not from a hardcoded default, so adding a
  third language later is a config + string-file addition, not a rebuild.
- Locale switch applies to: UI labels, notification templates (§5 above),
  error messages (§7 above), and PDF/Excel export headers. It does not
  translate user-entered free-text data (Observation notes, Discrepancy
  findings, etc.) — those stay as entered.

## 9. Open Items

- Full native-speaker review of every Hindi string above before Production
  launch — this file is a structural placeholder, not final copy.
- Confirm whether additional regional terminology varies by state (India
  has regional variation in some administrative terms) — if any pilot
  schools are in a specific state, check with them before finalizing.
- **(v1.5)** The eleven new terms/statuses/labels added for BR-21–27
  (Discrepancy Category, Approval Chain, Holiday Calendar, Working Days,
  Grace Period, Closed-Missed, Reopen, Duplicate Observation, Override,
  Evidence Retention Period, Asset/Retired) are first-pass drafts only —
  include them in the same native-speaker review pass above rather than a
  separate one, so terminology stays consistent with the v1.1 baseline
  terms.
