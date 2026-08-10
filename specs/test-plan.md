# Test Plan — School Operations & Governance Platform

Purpose: rules.md states *what* must always be true; this file states the
concrete scenario each rule's automated test should exercise, so "has ≥1
automated test" (phases.md §1.5 exit criterion) can't be satisfied by a weak
or tautological test. Use the Test Name column verbatim (or close to it) so
the Prompt 13 traceability matrix can match rule → test mechanically.

Format per rule: **Given / When / Then**, plus the Test Name to use.

**PRS v1.5 note:** the R-xx numbering below is this file's own local test-ID
scheme (not PRS's BR-xx/FR-xxx numbering) and predates the v1.5 gap-closure
items. Rather than renumber everything, the seven new v1.5 rule groups
(BR-21–27) are inserted below using their PRS BR-xx/FR-xxx IDs directly,
in the position matching their functional area (Discrepancy, Observation,
Scheduler, Master Data) — treat R-xx and BR-xx/FR-xxx as two coexisting
ID schemes in this file, not a gap to fix.

---

## Tenancy & Scope (R-01 to R-08)

| Rule | Scenario | Test Name |
|---|---|---|
| R-01 | Given a non-SuperAdmin/Viewer user, when a second School is granted to them, then the grant is rejected or the user's role must first be SuperAdmin/Viewer. | `test_R01_single_school_constraint_enforced` |
| R-02 | Given a valid Admin token scoped to School A, when they request a resource in School B by ID (guessing/enumerating), then a scope-filtered query returns not-found, never the record. | `test_R02_scope_filter_runs_before_permission_check` |
| R-03 | Given the schema, when inspecting any tenant-scoped table, then it has non-null `school_id` (and `department_id` where applicable) and no separate per-school database/schema exists. | `test_R03_shared_db_row_level_isolation_schema_check` |
| R-04 | Given a SuperAdmin, when accessing School B's data, then an explicit scope-grant record exists for it — access is never a blanket bypass flag. | `test_R04_superadmin_access_is_explicit_grant_not_bypass` |
| R-05 | Given an Admin (not SuperAdmin) user, when they call the School-creation endpoint, then it is rejected with 403. | `test_R05_only_superadmin_creates_school` |
| R-06 | Given two Schools A and B, when a School A user lists any entity, then no School B rows appear, with no special query param required to exclude them (default-deny, not opt-in filter). | `test_R06_school_data_isolated_by_default` |
| R-07 | Given a Department, when created, then it references exactly one School and cannot be created without one. | `test_R07_department_single_school_fk_required` |
| R-08 | Given a user with Admin and Viewer roles concurrently in the same School, when they act under either role's permissions, then both are honored without conflict. | `test_R08_user_multiple_roles_same_school` |

## Lifecycle & Deletion (R-09 to R-14)

| Rule | Scenario | Test Name |
|---|---|---|
| R-09 | Given any business entity (School/User/Observation/Discrepancy/Task/Scorecard/KPI/Department), when a delete is attempted via API or direct DB grant, then it is rejected — no DELETE grant exists for the relevant role. | `test_R09_no_hard_delete_any_business_entity` |
| R-10 | Given a School, when a "delete" action is invoked, then the School is Deactivated (soft), historical data remains readable. | `test_R10_school_delete_is_deactivate_not_remove` |
| R-11 | Given a Department with an open Task or unresolved Discrepancy, when Archive is attempted, then it is rejected with a structured error naming the blocking record type. | `test_R11_department_archive_blocked_by_open_records` |
| R-12 | Given a User, when "deleted," then login is disabled, record is archived, and all prior audit history remains queryable. | `test_R12_user_delete_is_archive_disable_login` |
| R-13 | Given an Archived record of any type, when an edit is attempted, then it is rejected even though the record remains readable/searchable. | `test_R13_archived_records_readonly` |
| R-14 | Given a Master Data enumeration value in use by existing records, when the value is changed/deprecated, then existing records keep referencing the value as it was at their creation time. | `test_R14_master_data_forward_only_no_retroactive_repoint` |

## Immutability & Versioning (R-15 to R-21)

| Rule | Scenario | Test Name |
|---|---|---|
| R-15 | Given any immutable entity type, when checking DB grants for the relevant role, then no UPDATE/DELETE grant exists (not just "app code doesn't call it"). | `test_R15_immutability_enforced_at_grant_layer` |
| R-16 | Given a locked Observation (past Lock Period), when an UPDATE is attempted at the DB layer, then it is rejected; when a correction is submitted, then a NEW Observation is created referencing the original, and the original is untouched. | `test_R16_locked_observation_rejects_update_creates_correction` |
| R-17 | Given a KPI referenced by ≥1 Observation, when its Target/Comparator/Unit is edited, then a new version/ID is created, the prior version is untouched, and historical reports resolve against the version active at reading time. | `test_R17_kpi_edit_creates_new_version_prior_immutable` |
| R-18 | Given an existing Scorecard v1, when recalculation runs, then v2 is created, v1 is retained with `superseded_by` set, and no role holds UPDATE/DELETE grants on scorecard rows. | `test_R18_scorecard_recalc_creates_new_version` |
| R-19 | Given the audit_log_entries table, when checking grants for every application role in every environment, then zero UPDATE/DELETE grants exist. | `test_R19_audit_log_append_only_zero_update_delete_grants` |
| R-20 | Given a ChecklistTemplate edit, when saved, then a new version is created; existing ChecklistInstances keep referencing the template version active at their generation time. | `test_R20_checklist_template_versions_forward` |
| R-21 | Given a KPI version marked Deprecated, when an Observation submission references it, then the submission is rejected at validation with a structured error. | `test_R21_submission_against_deprecated_kpi_blocked` |

## Observation, Audit & Discrepancy (R-22 to R-29)

| Rule | Scenario | Test Name |
|---|---|---|
| R-22 | Given a Checker role, when they attempt to edit any non-Observation business record or audit data, then it is rejected with 403. | `test_R22_checker_cannot_edit_non_observation_records` |
| R-23 | Given an Observation submission with no KPI reference, when submitted, then it is rejected at validation. | `test_R23_observation_requires_kpi_link` |
| R-24 | Given an Auditor, when they attempt to directly edit an Observation (not verify/raise-discrepancy), then it is rejected with 403. | `test_R24_auditor_cannot_edit_observation` |
| R-25 | Given a Discrepancy in state "Discrepancy," when a transition directly to "Approval" (skipping Investigation/Resolution) is attempted, then it is rejected by the Workflow Engine. | `test_R25_discrepancy_lifecycle_no_skipped_states` |
| R-26 | Given a Discrepancy with no Investigation findings recorded, when a transition to Resolved is attempted, then it is rejected. | `test_R26_resolved_requires_investigation_findings` |
| R-27 | Given a Discrepancy where the same user is both Investigation Owner and attempted Approver, when Approval is attempted, then it is rejected. | `test_R27_approver_cannot_equal_investigation_owner` |
| R-28 | Given an Observation value with a type mismatched to the KPI's Unit, when submitted, then it is rejected with a field-referenced validation error. | `test_R28_observation_value_type_matched_to_kpi_unit` |
| R-29 | Given an Observation value, KPI Target, and Comparator, when Auto-Result is computed, then it matches the expected Met/Not Met/N/A outcome and cannot be overridden by a client-supplied value. | `test_R29_auto_result_system_computed_not_client_settable` |

## Multi-Level Discrepancy Approval (BR-21, FR-231–237, v1.5)

| Rule | Scenario | Test Name |
|---|---|---|
| BR-21a | Given a Discrepancy at creation, when submitted, then a Discrepancy Category is required and becomes immutable thereafter. | `test_BR21a_discrepancy_category_required_and_immutable` |
| FR-232 | Given a Discrepancy's Category with a configured 2-level Approval Chain, when it enters Approval, then Level 1's assigned Role/Approver is resolved from that chain, not hardcoded. | `test_FR232_approval_level_role_resolved_from_chain_config` |
| FR-233 | Given Level 1 already Approved by User X, when User X (or the Investigation Owner) is attempted as the Level 2 Approver, then it is rejected. | `test_FR233_approver_distinct_from_investigation_owner_and_prior_levels` |
| FR-234 | Given a 2-level chain with only Level 1 Approved, when Closure is attempted, then it is rejected. | `test_FR234_closure_blocked_until_all_levels_approved` |
| AQ-API7 | Given a Discrepancy with Level 1 not yet Approved, when Level 2 approval is attempted directly, then it is rejected (422, out-of-order transition). | `test_AQAPI7_out_of_order_approval_level_rejected` |
| FR-235 | Given a Discrepancy already in Approval when its Category's Approval Chain Configuration changes, when it proceeds through approval, then it continues using the chain version active when it entered Approval, not the new one. | `test_FR235_approval_chain_version_snapshotted_on_entry` |
| FR-237 | Given a completed multi-level approval, when the Discrepancy Approval History is read, then one row per level exists (Level, Assigned Role, Assigned User, Status, Approved At, Comments), not fixed columns on the Discrepancy record. | `test_FR237_approval_history_is_row_per_level` |

## Holiday Calendar & Compliance Scheduler (BR-22, BR-24, FR-238–255, v1.5)

| Rule | Scenario | Test Name |
|---|---|---|
| BR-22 | Given a KPI due date landing on a configured Holiday/non-working day with policy=Skip, when the Scheduler runs, then no compliance record is generated for that occurrence. | `test_BR22_skip_policy_no_record_on_holiday` |
| FR-238 | Given the same KPI with policy=Shift Forward, when the Scheduler runs, then exactly one record is generated, dated to the next working day. | `test_FR238_shift_forward_single_record_next_working_day` |
| FR-238b | Given the same KPI with policy=Shift Backward, when the Scheduler runs, then exactly one record is generated, dated to the preceding working day. | `test_FR238b_shift_backward_single_record_prior_working_day` |
| BR-24a | Given two overlapping Scheduler runs (retry/race), when both attempt to generate the same logical occurrence (KPI version + scope + due date), then only one record exists afterward. | `test_BR24a_scheduler_generation_idempotent_under_race` |
| BR-24b | Given a School with a non-UTC configured timezone, when the Scheduler computes a due date near a timezone boundary, then the due date matches the School's local time, not server-local/UTC. | `test_BR24b_scheduler_uses_school_timezone` |
| FR-250 | Given the Scheduler was down for N cycles, when it next runs successfully, then all N missed occurrences are generated, each dated to its correct original due date. | `test_FR250_scheduler_backfills_missed_occurrences` |
| §23.16 | Given any Scheduler run (success or failure), when it completes, then a run-log entry with generated/backfilled counts is written, distinct from per-record Audit Log entries. | `test_scheduler_run_log_written_every_run` |

## Phase 1 Asset Lifecycle (BR-23, FR-244–249, v1.5)

| Rule | Scenario | Test Name |
|---|---|---|
| BR-23 | Given an Asset marked Retired, when a hard-delete is attempted via API or DB grant, then it is rejected — no DELETE grant exists. | `test_BR23_retired_asset_never_hard_deleted` |
| FR-244 | Given a Retired Asset, when assignment to a new KPI, Event Time Point, or Task is attempted, then it is rejected. | `test_FR244_retired_asset_not_assignable_going_forward` |
| FR-245 | Given a Retired Asset with prior Observations referencing it, when those historical Observations/reports are viewed, then they remain fully intact and readable. | `test_FR245_retired_asset_preserves_historical_references` |

## Duplicate Observation Detection (BR-25, FR-256–262, v1.5)

| Rule | Scenario | Test Name |
|---|---|---|
| FR-256 | Given a prior Observation on the same KPI version, scope, Event Time Point (if applicable), and Checker within the Duplicate Detection Window, when a new matching Observation is submitted, then it is checked before acceptance. | `test_FR256_duplicate_check_runs_before_acceptance` |
| FR-257 | Given a detected duplicate, when submission is attempted by a user without Override permission, then it is blocked (409, `DUPLICATE_DETECTED`) with the prior Observation's summary returned. | `test_FR257_duplicate_blocked_by_default_with_prior_summary` |
| FR-258 | Given a detected duplicate and a user holding Override permission, when Override is submitted without a justification, then it is rejected; when submitted with a justification, then it is accepted. | `test_FR258_override_requires_mandatory_justification` |
| FR-259 | Given an Override-submitted duplicate, when the record is inspected, then it stores the justification, the overriding user, and a reference to the original Observation. | `test_FR259_override_records_justification_user_and_original_ref` |
| FR-260 | Given a submission-token retry (FR-069) and a genuine second distinct Observation attempt (BR-25), when both occur, then each is handled independently — a retried token does not trigger a duplicate-block, and a duplicate-block is not bypassed by a fresh token. | `test_FR260_idempotency_and_duplicate_detection_independent` |
| FR-256b | Given two different Checkers submitting for the same occurrence within the window (default Checker-scoped duplicate check), when the second submits, then it is NOT blocked, unless the School has configured Checker-agnostic duplicate checking. | `test_FR256b_duplicate_check_checker_scoped_by_default` |
| FR-262 | Given a blocked duplicate attempt or an Override action, when it occurs, then it is logged to the Audit Log. | `test_FR262_duplicate_attempts_and_overrides_audit_logged` |

## Missed-KPI Grace Period & Reopen (BR-26, FR-263–270, v1.5)

| Rule | Scenario | Test Name |
|---|---|---|
| FR-263 | Given a KPI compliance record past its due date but within the configured Grace Period, when a Checker submits, then it is accepted, flagged Late, with Auto-Result computed and no Admin action required. | `test_FR263_late_submission_within_grace_period_accepted` |
| FR-264 | Given a compliance record whose Grace Period has elapsed with no submission, when the transition is evaluated, then the record moves to Closed-Missed. | `test_FR264_grace_period_elapsed_transitions_to_closed_missed` |
| FR-265 | Given a Closed-Missed record, when a Checker attempts direct submission, then it is rejected. | `test_FR265_closed_missed_blocks_direct_checker_submission` |
| FR-266 | Given a Closed-Missed record, when a Reopen Request (with mandatory reason) is submitted and then Admin/SuperAdmin-approved, then the record accepts a new submission; when not yet approved, then submission remains rejected. | `test_FR266_reopen_requires_admin_approval_before_resubmission` |
| FR-267 | Given a post-reopen submission, when flagged, then it carries both Late and Reopened flags, distinct from an ordinary within-window Late submission. | `test_FR267_post_reopen_submission_flagged_late_and_reopened` |
| FR-269 | Given a backfilled compliance record (Scheduler was down), when its Grace Period is calculated, then it is extended by the outage duration relative to the original due date, not penalizing the Checker for the outage. | `test_FR269_grace_period_extended_for_scheduler_outage` |
| FR-270 | Given any Reopen Request or Approval/Rejection, when it occurs, then it is logged to the Audit Log. | `test_FR270_reopen_actions_audit_logged` |

## Evidence Retention & Deletion (BR-27, FR-271–274, v1.5)

| Rule | Scenario | Test Name |
|---|---|---|
| BR-27a | Given an evidence file whose Retention Period has elapsed, when checked, then it is flagged deletion-eligible but the file itself remains present — no automated purge process runs. | `test_BR27a_no_automated_purge_after_retention_elapses` |
| FR-271 | Given a deletion-eligible evidence file, when a non-Admin/SuperAdmin user attempts deletion, then it is rejected. | `test_FR271_evidence_deletion_requires_admin_or_superadmin` |
| FR-272 | Given an Admin/SuperAdmin deletes a deletion-eligible evidence file, when the action completes, then it is logged to the Audit Log with actor identity and timestamp. | `test_FR272_evidence_deletion_explicit_and_logged` |
| FR-273 | Given an evidence file not yet past its Retention Period, when deletion is attempted (even by Admin/SuperAdmin), then it is rejected — deletion eligibility is a precondition, not bypassable early. | `test_FR273_deletion_rejected_before_retention_period_elapses` |

## Task & Escalation (R-30 to R-34)

| Rule | Scenario | Test Name |
|---|---|---|
| R-30 | Given a Task creation request with zero Primary Owners, when submitted, then it is rejected. | `test_R30_task_requires_at_least_one_primary_owner` |
| R-31 | Given a Task with a set Completion Rule, when a change to that rule is attempted post-creation, then it is rejected. | `test_R31_completion_rule_immutable_after_creation` |
| R-32 | Given a Task creation request with an ETA in the past, when submitted, then it is rejected. | `test_R32_eta_must_be_future_at_creation` |
| R-33 | Given a Task that has already had 3 ETA extensions, when a 4th extension is requested, then it is auto-converted to an escalation rather than granted. | `test_R33_fourth_eta_extension_triggers_escalation` |
| R-34 | Given the client is offline, when an Observation/Task action is attempted, then no local queuing/sync occurs — the system requires connectivity, with a retry/resubmit pattern only. | `test_R34_no_offline_mode_client_requires_connectivity` |

## KPI Calculation (R-35 to R-37)

| Rule | Scenario | Test Name |
|---|---|---|
| R-35 | Given a KPI's Comparator and Target, when a result is computed, then it uses the platform's supported formula type via the Rule Engine, not inline per-module math. | `test_R35_kpi_result_uses_rule_engine_formula` |
| R-36 | Given a missing-data scenario for a KPI reading, when computed, then the behavior matches the Configuration-Engine-defined handling for that KPI, not a hardcoded module default. | `test_R36_missing_data_and_rounding_config_driven` |
| R-37 | Given a KPI category with an Amber Tolerance Band override, when RAG status is computed, then the override applies instead of the global default. | `test_R37_rag_uses_configurable_amber_tolerance_band` |

## Notifications (R-38 to R-40)

| Rule | Scenario | Test Name |
|---|---|---|
| R-38 | Given multiple notification events fire concurrently, when dispatched, then they are ordered/labeled per the fixed priority (1 Escalation … 7 Informational). | `test_R38_notification_fixed_priority_order` |
| R-39 | Given a user attempts to mute category 1 (Escalation) or 2 (Audit Failure) via any client path, then the server rejects the mute regardless of request shape. | `test_R39_mandatory_categories_cannot_be_muted_server_side` |
| R-40 | Given a slow/failing notification provider, when a triggering request fires a notification, then the triggering request completes normally without waiting on the provider. | `test_R40_notification_dispatch_never_blocks_request` |

## Configuration & Governance (R-41 to R-46)

| Rule | Scenario | Test Name |
|---|---|---|
| R-41 | Given a governance value (Lock Period, SLA, Reminder Frequency, etc.), when changed via the Configuration Engine, then the new value takes effect without a code deploy. | `test_R41_governance_values_config_driven_no_redeploy` |
| R-42 | Given an attempt to set Max ETA Extensions to a value other than 3 via the Configuration Engine, then it is rejected — this value is not exposed as overridable. | `test_R42_max_eta_extensions_not_overridable` |
| R-43 | Given a non-SuperAdmin (e.g., School Admin), when attempting to create/edit a Global KPI Library entry, then it is rejected with 403. | `test_R43_only_superadmin_manages_global_kpi_library` |
| R-44 | Given an Admin, when attempting to edit a Configuration item not marked delegable in PRS §54's table, then it is rejected. | `test_R44_admin_limited_to_delegable_config_items` |
| R-45 | Given a User transferred from Department A to B, when historical Observations/Tasks from before the transfer are viewed, then they still show Department A. | `test_R45_department_transfer_preserves_historical_attribution` |
| R-46 | (Phase 2+, stub now) Given ERP sync is active, when Users/Departments/Schools are synced, then ERP is authoritative for those three entities only — Tasks/Compliance/Audits/Discrepancies/KPIs/Performance remain platform-authoritative. | `test_R46_erp_master_data_boundary_phase2` *(deferred — write as a placeholder/pending test in Phase 1, activate in Phase 2)* |

## Permission & Authorization (R-47 to R-50)

| Rule | Scenario | Test Name |
|---|---|---|
| R-47 | Given the PRS §12 Permission Matrix, when tested at the API layer directly (no UI), then results match the matrix exactly — no looser API-only permission path exists. | `test_R47_api_permission_matches_ui_permission_matrix` |
| R-48 | Given a user's role is changed mid-session, when their next request is made, then the new permission set applies immediately (not the stale session-start permission set). | `test_R48_permissions_reevaluated_per_request` |
| R-49 | Given segregation-of-duties rules (e.g., R-27), when checked, then they are enforced in the Workflow Engine's guard logic, not only in UI conditionals. | `test_R49_segregation_of_duties_is_workflow_guard` |
| R-50 | Given a Viewer role and a category flagged as export-restricted (e.g., financial KPIs), when export is attempted, then it is rejected. | `test_R50_category_level_export_override_enforced` |

## Validation (§11 table)

| Domain | Scenario | Test Name |
|---|---|---|
| Observation | Missing value, mismatched type, oversized/wrong-format evidence, deprecated KPI — each rejected individually with field-referenced errors. | `test_validation_observation_*` (one per case) |
| Task | Zero owners, past ETA, post-creation completion-rule change — each rejected. | `test_validation_task_*` |
| KPI | Invalid comparator, missing/multiple KRA references, unsupported frequency — each rejected. | `test_validation_kpi_*` |
| Discrepancy | Missing investigation findings before Resolved; approver = investigation owner. | `test_validation_discrepancy_*` |
| User | Duplicate email/phone, zero active roles, multi-school without SuperAdmin/Viewer. | `test_validation_user_*` |
| Notification | Attempt to disable a mandatory category via any client path. | `test_validation_notification_*` |
| School | Duplicate name within org; activation attempted before departments+KPI import succeed. | `test_validation_school_*` |
| Department | Duplicate name within School; archive attempted with open Tasks/Discrepancies. | `test_validation_department_*` |

## Error Handling & Idempotency (R-51 to R-55)

| Rule | Scenario | Test Name |
|---|---|---|
| R-51 | Given any rejected operation, when the error is returned, then it matches the structured `{code, message, field}` shape. | `test_R51_structured_error_shape` |
| R-52 | Given a duplicate School name or concurrent conflicting audit action, when submitted, then a 409-equivalent response with a resolution path is returned. | `test_R52_conflict_returns_409_with_resolution_path` |
| R-53 | Given any error affecting data integrity, when it occurs, then an entry is written to the Audit/Error Log. | `test_R53_integrity_errors_logged` |
| R-54 | Given an Observation submission retried with the same Idempotency-Key after a network failure, when resent, then exactly one Observation exists and the original response body is returned (not a fresh 409). | `test_R54_observation_idempotency_key_prevents_duplicate` |
| R-55 | Given the Checklist Scheduler crashes and restarts mid-run, when it re-runs, then zero duplicate ChecklistInstances are created for the same (template, version, school, department, period). | `test_R55_checklist_scheduler_idempotent_on_crash_restart` |

## Security & Compliance (R-56 to R-58)

| Rule | Scenario | Test Name |
|---|---|---|
| R-56 | Given an Admin/SuperAdmin login attempt, when credentials are correct but MFA is not completed, then access is denied. | `test_R56_mfa_required_admin_superadmin` |
| R-57 | Given data in transit and at rest, when inspected, then encryption is confirmed active (TLS in transit, encryption-at-rest on the datastore). | `test_R57_encryption_in_transit_and_at_rest` |
| R-58 | *(BLOCKING on AQ4)* Given a DPDP erasure request against audit-relevant records, when processed, then it follows whichever model (anonymization vs. retention exemption) Legal confirms — do not implement either path until AQ4 resolves. | `test_R58_dpdp_erasure_model` *(deferred until AQ4 resolved — see assumptions-log.md)* |

## Export, Search & Reporting (R-59 to R-61)

| Rule | Scenario | Test Name |
|---|---|---|
| R-59 | Given an export request, when made, then Excel, CSV, PDF, and REST API formats are all available. | `test_R59_all_export_formats_supported` |
| R-60 | Given a new/updated record, when indexed for search, then it becomes searchable within 60 seconds; given a search request, then results are scoped identically to direct module access permissions. | `test_R60_search_indexing_lag_and_permission_scoping` |
| R-61 | Given a heavy report/dashboard export running concurrently with normal write traffic, when write latency is measured, then it does not regress compared to baseline. | `test_R61_report_generation_isolated_from_write_path` |

---

## Cross-Module End-to-End Workflows (phases.md §1.5 / rules.md §15)

These are not per-rule unit tests — they're full-path integration tests run
in Staging, required for Phase 1 exit:

| Workflow | Test Name |
|---|---|
| Observation → Audit → Discrepancy → Investigation → Closure | `test_e2e_observation_to_discrepancy_closure` |
| Task → ETA → Escalation → Completion | `test_e2e_task_eta_escalation_completion` |
| KPI → Observation → Scorecard | `test_e2e_kpi_observation_scorecard` |
| KPI → Scheduler → Observation → Grace Period → Scorecard *(v1.5)* | `test_e2e_scheduler_grace_period_scorecard` |
| Observation → Audit → Discrepancy → multi-level Approval Chain → Closure *(v1.5)* | `test_e2e_discrepancy_multilevel_approval_closure` |

Each must complete without any manual data patching in staging, per the
exit criterion — if a step requires a manual DB fix to proceed, the
workflow test fails, it doesn't get skipped.
