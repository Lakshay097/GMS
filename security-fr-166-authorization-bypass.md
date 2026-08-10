# Security Finding: Service-layer Authorization Bypass in ConfigurationEngine

**Finding ID**: FR-166  
**Date**: 2026-08-10  
**Severity**: HIGH  
**Status**: OPEN  

## Executive Summary

ConfigurationEngine.set_global() and set_override() do NOT enforce editable_by restrictions internally. Authorization enforcement exists ONLY at the API route layer (configuration_routes.py lines 178-207). Any code with direct service access can modify configuration regardless of editable_by setting, creating a significant authorization bypass vulnerability.

## Severity Assessment

**HIGH** - This vulnerability allows:

1. **Privilege Escalation**: Any internal service, script, or compromised component with direct ConfigurationEngine access can modify platform-wide configuration settings regardless of the intended role restrictions (editable_by field in CONFIG_DEFINITIONS).

2. **Bypass of Defense in Depth**: The security model assumes authorization is enforced at multiple layers, but ConfigurationEngine has no internal authorization checks. If the API route layer is bypassed (e.g., through internal service calls, testing frameworks, or future API endpoints), there is no fallback protection.

3. **Configuration Tampering**: Critical settings like SESSION_TIMEOUT_MINUTES, GRACE_PERIOD_HOURS, and feature flags can be modified by unauthorized actors, potentially affecting system security, compliance, and operational behavior.

4. **Audit Trail Issues**: While audit logging is implemented, the actor_id parameter is optional and not validated. Unauthorized modifications may be logged with invalid or missing actor information.

## Blast Radius Analysis

### Current Callers of set_global() and set_override()

#### SAFE Callers (Go Through Authorized API Routes)

1. **modules/settings_master_data/api/configuration_routes.py**
   - Lines 183, 207: set_global() calls within API routes
   - Lines 192, 201: set_override() calls within API routes
   - **Status**: SAFE - These routes have role checks via require_roles() decorator and validate editable_by before calling ConfigurationEngine methods

2. **Test Files** (33 set_global calls, 17 set_override calls)
   - All test files in tests/ directory
   - **Status**: SAFE - Tests intentionally bypass API routes to test service behavior directly

#### EXPOSED Callers (Direct Service Access - Security Risk)

1. **modules/school-dept-user-role/services/configuration_service.py**
   - Line 78: `await self.config_engine.set_global(key, value, updated_by=updated_by_user_id)`
   - Line 160: `await self.config_engine.set_override(key, "school", school_id, value, updated_by=updated_by_user_id)`
   - **Status**: EXPOSED - This service layer calls ConfigurationEngine methods directly without role validation
   - **Context**: This is a separate service layer that may be called by internal components without going through the authorized API routes

#### READ-ONLY Callers (No Security Risk)

The following services have ConfigurationEngine instances but only call get() methods (read-only):
- modules/kra-kpi-library/services/kpi_service.py
- modules/observation-capture/services/evidence_service.py
- modules/observation-capture/services/observation_service.py
- modules/performance-scorecards/services/performance_review_service.py

**Status**: SAFE - These services only read configuration, they cannot modify it

### Summary

- **Total set_global() callers**: 33 (test) + 2 (API routes) + 1 (exposed service) = 36
- **Total set_override() callers**: 17 (test) + 2 (API routes) + 1 (exposed service) = 20
- **Exposed production code**: 1 service (configuration_service.py) with 2 method calls
- **Safe production code**: 2 API routes with proper authorization

## Consistency Check with Other Services

### ApprovalChainService
- **Location**: modules/audit_discrepancy/services/approval_chain_service.py
- **Authorization Pattern**: NO service-layer role enforcement
- **Relies on**: API route layer authorization only
- **Status**: Consistent with ConfigurationEngine (same pattern)

### DiscrepancyService  
- **Location**: modules/audit_discrepancy/services/discrepancy_service.py
- **Authorization Pattern**: NO service-layer role enforcement
- **Relies on**: API route layer authorization only
- **Status**: Consistent with ConfigurationEngine (same pattern)

**Conclusion**: The current codebase consistently relies on API route layer authorization for all services. ConfigurationEngine is not uniquely deficient in this regard, but it is uniquely critical because configuration changes have system-wide impact.

## Recommended Fix Options

### Option A: Add Service-Layer Role Enforcement (RECOMMENDED)

Add role/editable_by enforcement directly inside ConfigurationEngine.set_global() and set_override(), requiring an actor/role parameter to be passed and validated at the service layer.

**Implementation**:
1. Add `actor_role: UserRole` parameter to set_global() and set_override()
2. Validate actor_role against CONFIG_DEFINITIONS[key]["editable_by"] before applying changes
3. Raise AuthorizationError if role check fails
4. Update all callers to pass the actor's role

**Pros**:
- Defense in depth: authorization enforced even if API layer is bypassed
- Consistent with security best practices
- Future-proof against new internal callers
- Matches the pattern in other enterprise systems

**Cons**:
- Requires updating existing service callers (configuration_service.py)
- Breaking change to service method signatures
- Requires role information to be available at service layer

**Effort Estimate**: 4-8 hours

### Option B: Document as Accepted Risk with Compensating Controls

Accept the current architecture as deliberate, with compensating controls to mitigate risk.

**Compensating Controls**:
1. Restrict which internal services/scripts are permitted to import ConfigurationEngine directly
2. Add code review policies requiring authorization checks for any new ConfigurationEngine callers
3. Monitor audit logs for configuration changes and investigate anomalies
4. Add integration tests to verify no new unauthorized callers are introduced

**Pros**:
- No code changes required
- Maintains current architecture consistency
- Lower immediate effort

**Cons**:
- Relies on process controls rather than technical controls
- Higher ongoing maintenance burden
- Vulnerable to human error in code reviews
- No defense in depth

**Effort Estimate**: 2-4 hours (documentation + policy creation)

## Recommended Next Steps

1. **Security Review**: Route this finding to the security team for severity confirmation and remediation decision
2. **Decision Point**: Choose between Option A (technical fix) or Option B (acceptance with controls)
3. **If Option A**: Implement service-layer role enforcement and update existing callers
4. **If Option B**: Create compensating control documentation and integrate into security monitoring
5. **Verification**: Add regression test to prevent future unauthorized ConfigurationEngine callers

## References

- Test demonstrating the gap: tests/unit/test_configuration_engine.py::test_FR166_configuration_engine_lacks_role_enforcement
- API route layer enforcement: modules/settings_master_data/api/configuration_routes.py lines 178-207
- ConfigurationEngine service: platform_services/configuration_engine/service.py
- Exposed service caller: modules/school-dept-user-role/services/configuration_service.py lines 78, 160

---

**Prepared by**: Automated security analysis  
**Review required**: Security team, Architecture team  
**Target resolution**: Before Phase 1 production deployment