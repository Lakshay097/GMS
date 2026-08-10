# ADR-09: Service-Layer Authorization Boundary

**Status:** Accepted  
**Date:** 2026-08-10  
**Context:** FR-166 Authorization Bypass Investigation  

---

## Context

As part of the FR-166 authorization bypass investigation, a comprehensive audit of service-layer authorization enforcement was conducted across all 15 core services in the School Operations & Governance Platform. The audit found:

**15 Core Services with No Service-Layer Role Enforcement:**
1. ConfigurationEngine (`platform_services/configuration_engine/service.py`)
2. ApprovalChainService (`modules/audit_discrepancy/services/approval_chain_service.py`)
3. DiscrepancyService (`modules/audit_discrepancy/services/discrepancy_service.py`)
4. TaskService (`modules/task-management/services/task_service.py`)
5. PerformanceReviewService (`modules/performance-scorecards/services/performance_review_service.py`)
6. NotificationService (`platform_services/notification_service/service.py`)
7. ObservationService (`modules/observation-capture/services/observation_service.py`)
8. ComplianceScheduler (`platform_services/compliance_scheduler/service.py`)
9. AuditLogService (`platform_services/audit_log_service/service.py`)
10. WorkflowEngine (`platform_services/workflow_engine/service.py`)
11. MasterDataService (`platform_services/master_data_service/service.py`)
12. UserService (`modules/school-dept-user-role/services/user_service.py`)
13. SchoolService (`modules/school-dept-user-role/services/school_service.py`)
14. KpiService (`modules/kra-kpi-library/services/kpi_service.py`)
15. DashboardService (`modules/dashboards-reports-search/services/dashboard_service.py`

All authorization is enforced exclusively at the API route layer via the `require_permission()` middleware in `shared/middleware/permissions.py`. This middleware is used consistently across all API route files but never within service methods themselves.

The investigation confirmed this is **intentional architecture**, not an oversight. The architecture documentation (Architecture.md §6, §9) and codebase evidence support that the API gateway is designed as the sole enforcement boundary, with services operating as internal-trust-boundary components.

---

## Decision

Services are **internal-trust-boundary components**. The API gateway is the **sole authorization enforcement point**. Services trust that any caller has already been authorized upstream.

**Authorized Callers:**
1. **API Routes** – Files under `*/api/*_routes.py` that call services after enforcing `require_permission()` middleware
2. **Background Schedulers** – System-context callers like `compliance_scheduler/service.py` and `checklist_scheduler/service.py` that operate without human actors
3. **Service-to-Service Calls** – Internal module communication per the module boundary rule (coding-standards.md §1)
4. **Test Files** – Any file under `tests/` for testing purposes

**Deliberate Design Rationale:**
- Services are internal components, not public APIs
- The API layer owns cross-cutting concerns like authorization
- This follows the modular monolith pattern (ADR-01) where the API gateway is the public entry point
- Service-to-service calls are trusted internal communication per the module boundary rule
- Background schedulers operate as system context without human actors

---

## Consequences

### Positive
- Single point of authorization enforcement at the API gateway ensures consistency
- Service methods remain focused on business logic without authorization complexity
- Service-to-service communication is simplified (no need to pass authorization context)
- Aligns with modular monolith pattern where services are internal components

### Negative / Guardrails Required
- **Critical:** Any new code path calling these services directly must go through the API layer, or must be a recognized system-context caller (scheduler) or internal service-to-service call
- **Critical:** Direct service instantiation/calls from scripts, migrations, or ad-hoc tooling bypass authorization entirely and are NOT permitted without explicit review
- **Guardrail:** A custom import-linting check (`tools/lint_service_callers.py`) enforces this going forward by flagging any unauthorized direct service imports

### Extending the Allowlist
To add a new legitimate caller to the authorized allowlist:
1. Edit `tools/lint_service_callers.py`
2. Add the file path pattern to the `AUTHORIZED_CALLER_PATTERNS` list
3. Document the rationale in a code comment
4. Do NOT disable the check — extend the allowlist instead

---

## Supporting Evidence

- **FR-166 Investigation:** `security-fr-166-authorization-bypass.md`
- **Service-Layer Authorization Audit:** `service-layer-authorization-architecture-review.md`
- **Architecture Documentation:** `specs/Architecture.md` §6 (Multi-Tenancy & Scope Isolation), §9 (API Architecture)
- **Module Boundary Rule:** `specs/coding-standards.md` §1
- **Shared Authorization Infrastructure:** `shared/middleware/permissions.py`

---

## Stakeholder Decision

**Date:** 2026-08-10  
**Decision:** Accept the API-layer-only authorization architecture as intentional, but formalize it in writing (this ADR) and add a guardrail (import-linting check) to prevent silent erosion.  

**Direction:** Do NOT retrofit authorization checks into the 15 services themselves — this was explicitly not the chosen direction. The architecture is deliberate; the gap is only exploitable if something violates the architecture assumption. The guardrail ensures that violation is caught early.