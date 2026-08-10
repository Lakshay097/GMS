# Service-Layer Authorization Architecture Review

**Date:** 2026-08-10  
**Scope:** FR-166 Authorization Bypass Investigation  
**Purpose:** Determine whether service-layer authorization absence is intentional architecture or an oversight

---

## Executive Summary

This audit examined service-layer authorization enforcement across all core services in the School Operations & Governance Platform. The investigation found **no service-layer role enforcement** in any examined service. Authorization is enforced exclusively at the API route layer via the `require_permission()` middleware in `shared/middleware/permissions.py`.

Based on architecture documentation and codebase analysis, this appears to be **intentional architecture**: the API gateway is designed as the sole enforcement boundary, with services operating as internal-trust-boundary components that trust their callers.

---

## Part 1: Service-Layer Authorization Sweep

### Summary Table

| Service Name | Enforcement Status | Evidence Location |
|--------------|-------------------|------------------|
| ConfigurationEngine | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `platform_services/configuration_engine/service.py` - Methods `set_global()`, `set_override()` accept `updated_by` but don't validate role. API enforcement in `modules/settings_master_data/api/configuration_routes.py:178-207` |
| ApprovalChainService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `modules/audit_discrepancy/services/approval_chain_service.py` - Methods accept `created_by` but don't validate role |
| DiscrepancyService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `modules/audit_discrepancy/services/discrepancy_service.py` - Methods accept actor parameters but don't validate role |
| TaskService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `modules/task-management/services/task_service.py` - Methods like `create_task()`, `complete_task()` accept user IDs but don't validate role |
| PerformanceReviewService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `modules/performance-scorecards/services/performance_review_service.py` - No role validation in methods |
| NotificationService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `platform_services/notification_service/service.py` - Enforces mandatory category rules (R-39) but not role-based authorization |
| ObservationService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `modules/observation-capture/services/observation_service.py` - Methods accept actor parameters but don't validate role |
| ComplianceScheduler | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `platform_services/compliance_scheduler/service.py` - Background scheduler, no role validation |
| AuditLogService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `platform_services/audit_log_service/service.py` - Append-only audit log, no role validation |
| WorkflowEngine | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `platform_services/workflow_engine/service.py` - State machine engine, no role validation |
| MasterDataService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `platform_services/master_data_service/service.py` - No role validation in methods |
| UserService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `modules/school-dept-user-role/services/user_service.py` - Methods accept actor parameters but don't validate role |
| SchoolService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `modules/school-dept-user-role/services/school_service.py` - Methods accept actor parameters but don't validate role |
| KpiService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `modules/kra-kpi-library/services/kpi_service.py` - Methods accept `created_by` but don't validate role |
| DashboardService | ❌ NO SERVICE-LAYER ENFORCEMENT (API-layer only) | `modules/dashboards-reports-search/services/dashboard_service.py` - No role validation, only shapes response based on role |

### Detailed Findings

**Common Pattern Across All Services:**
- All services accept optional actor/user parameters (e.g., `created_by`, `updated_by`, `actor_id`)
- None of these parameters are validated against role permissions internally
- No decorators, base classes, or middleware patterns enforce service-layer authorization
- Business rule validation exists (e.g., mandatory notification categories, duplicate detection) but not role-based authorization

**Shared Authorization Infrastructure:**
- `shared/middleware/permissions.py` provides `require_permission()` function
- This function is used exclusively in API route files, not in service methods
- No service base class or DI pattern exists for automatic authorization enforcement

---

## Part 2: Architecture vs. Oversight Analysis

### Evidence for Intentional Architecture

**1. Architecture Documentation:**
- `docs/ARCHITECTURE.md` Section 6 explicitly describes "Row-Level Tenant Isolation" enforced at the query layer via tenancy middleware
- `specs/API-Spec.md` Section 2 states: "Every endpoint below enforces the identical Permission Matrix as the UI (PRS §39) — there is no separate, looser API-only authorization path"
- The architecture follows a modular monolith pattern (ADR-01) with API gateway as the public entry point

**2. Codebase Evidence:**
- Authorization checks are consistently implemented at the API route layer across all examined routes
- Example: `modules/settings_master_data/api/configuration_routes.py:178-207` shows explicit role checks before calling `ConfigurationEngine.set_global()` and `set_override()`
- No partially-implemented service-layer authorization was found (no commented-out role checks, no TODOs for service-layer auth)

**3. Module Boundary Rule:**
- Per `README.md` and coding standards: "A module writes only to its own tables. To read/write another module's data, call that module's internal service interface."
- This design assumes services are internal components, not public APIs

### Conclusion: (a) Deliberate Architecture

**This is intentional architecture**, not an oversight. The evidence supports:

- The API gateway is designed as the **sole enforcement boundary** for authorization
- Services are **internal-trust-boundary components** that trust their callers
- The only public entry point is the API layer; no other code is expected to call services directly
- The "gap" is only exploitable if something violates this architecture assumption

The architecture is consistent with:
- Modular monolith patterns where services are internal components
- API-first design where the API layer owns cross-cutting concerns like authorization
- Defense-in-depth where tenancy (scope isolation) is enforced at the query layer independently of role permissions

---

## Part 3: Real Caller Exposure Analysis

### Non-API, Non-Test Service Callers

| Caller Type | Caller Location | Service Methods Called | Authorization Context | Risk Assessment |
|-------------|----------------|----------------------|---------------------|-----------------|
| **Background Scheduler** | `platform_services/compliance_scheduler/service.py` | `MasterDataService.is_asset_active()`, `ConfigurationEngine.get()` | System context - no human actor | ✅ ACCEPTABLE - Scheduled job operating as system |
| **Background Scheduler** | `platform_services/checklist_scheduler/service.py` | Direct database writes to `checklist_instances` | System context - no human actor | ✅ ACCEPTABLE - Scheduled job operating as system |
| **Service-to-Service** | `modules/audit_discrepancy/services/discrepancy_service.py:217-218` | `ApprovalChainService.get_active_approval_chain()` | Internal service call | ✅ ACCEPTABLE - Internal module communication per module boundary rule |
| **Service-to-Service** | `modules/audit_discrepancy/services/discrepancy_service.py:512-513` | `ApprovalChainService.get_active_approval_chain()` | Internal service call | ✅ ACCEPTABLE - Internal module communication per module boundary rule |
| **Service-to-Service** | `modules/observation-capture/services/observation_service.py` | `ConfigurationEngine.get()`, `RuleEngine.compute_auto_result()` | Internal service call | ✅ ACCEPTABLE - Internal module communication per module boundary rule |
| **Service-to-Service** | `modules/task-management/services/task_service.py` | `NotificationService.dispatch()` | Internal service call | ✅ ACCEPTABLE - Internal module communication per module boundary rule |

### Test Files (Not Production Risks)

All other direct service callers are test files:
- `tests/unit/test_configuration_engine.py`
- `tests/unit/test_settings.py`
- `tests/unit/test_discrepancy_notification_failure.py`
- `tests/unit/test_approval_chain_service.py`
- `tests/unit/test_location_manual_time_reason.py`
- `tests/unit/test_performance_reviews.py`
- `tests/e2e/test_e2e_task_eta_escalation_completion.py`
- `tests/e2e/test_e2e_discrepancy_multilevel_approval_closure.py`
- `tests/e2e/test_e2e_scheduler_grace_period_scorecard.py`
- `tests/unit/test_BR26_backfill_grace_period_extension.py`
- `tests/unit/test_BR24_timezone_aware_generation.py`
- `tests/unit/test_BR22_additional_test_cases.py`

These are **not production risks** - they test services directly by design.

### Exposure Assessment

**Low Risk Exposure:**
- All non-API callers are either background schedulers (system context) or internal service-to-service calls
- Background schedulers operate in a system context, which is appropriate for their function
- Internal service-to-service calls follow the module boundary rule and are expected in a modular monolith
- No evidence of scripts, migrations, or other code paths that could bypass API layer authorization with untrusted actors

**Architecture Assumption:**
- The architecture assumes services are only called via:
  1. API routes (with authorization)
  2. Background schedulers (system context)
  3. Other services (internal trust boundary)
  4. Tests (development context)

---

## Part 4: Stakeholder Decision Required

### Options for Resolution

This document presents the architecture as designed. The following options are available for stakeholder decision:

**Option (i): Accept as Documented Architecture**
- Acknowledge that API gateway as sole enforcement boundary is intentional
- Document this architectural decision in ADR format
- Add comments to service methods explicitly stating they trust caller authorization
- Ensure no new code paths violate this assumption

**Option (ii): Treat as Phase 1 Blocker Requiring Systemic Fix**
- Add service-layer role enforcement to all core services
- This would be a significant architectural change requiring:
  - Authorization context injection into all service methods
  - Refactoring of service constructors to accept auth context
  - Updates to all service-to-service calls to pass auth context
  - Potential impact on background schedulers and internal communication

**Option (iii): Defer to Phase 2 with Compensating Controls**
- Accept current architecture for Phase 1
- Add compensating controls:
  - Code review gates to prevent new direct service callers
  - Documentation warning about service-layer trust assumption
  - Consider adding service-layer authorization in Phase 2 if new patterns emerge

### Recommendation

Based on the evidence, **Option (i) is recommended**:
- The architecture is consistent and well-documented
- No production risks were identified in current caller patterns
- Adding service-layer authorization would be a significant change with unclear benefit
- The current design follows established modular monolith patterns

However, this decision should be made by security/architecture stakeholders, not unilaterally by engineering implementation.

---

## Appendix: Investigation Methodology

### Services Examined
- Platform Services: ConfigurationEngine, NotificationService, AuditLogService, WorkflowEngine, MasterDataService, ComplianceScheduler, ChecklistScheduler, RuleEngine
- Module Services: TaskService, PerformanceReviewService, ObservationService, ApprovalChainService, DiscrepancyService, UserService, SchoolService, KpiService, DashboardService

### Documentation Reviewed
- `docs/ARCHITECTURE.md`
- `specs/phases.md`
- `specs/API-Spec.md`
- `README.md`
- `specs/Architecture.md`

### Code Analysis
- Searched for authorization decorators, base classes, and middleware patterns
- Examined all service constructors and public methods
- Analyzed API route files to understand authorization enforcement patterns
- Searched for non-API, non-test service callers across the codebase

### Evidence Files
- Configuration API routes: `modules/settings_master_data/api/configuration_routes.py`
- Permission middleware: `shared/middleware/permissions.py`
- Auth integration: `shared/auth.py`
- API auth: `api/auth.py`

---

**Document Classification:** Internal — Security/Architecture  
**Next Review:** Phase 2 planning or if new service caller patterns emerge