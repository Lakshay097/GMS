# M3: Routes Without Frontend - Build/Keep/Kill Decisions

**Date:** 2025-01-20
**Priority:** Medium
**Scope:** Routes identified in audit report as having limited or no frontend integration

## Summary

Based on codebase analysis, the following routes have been categorized by their current status and recommended action:

## Decision Matrix

| Route Pattern | Location | Current Status | Recommended Action | Rationale |
|---------------|----------|-----------------|-------------------|-----------|
| `/api/v1/performance-reviews/*` | `modules/performance-scorecards/api/routes.py` | **KILL** | Remove | Not imported in main.py; no frontend; appears to be dead code |
| `/api/v1/scorecards/*` | `modules/performance-scorecards/api/routes.py` | **KILL** | Remove | Not imported in main.py; no frontend; appears to be dead code |
| `/auth/mfa/setup` | `api/auth.py` | **KEEP (GATED)** | Gate with feature flag | Marked as Phase 2; reserved for future MFA feature |
| `/auth/sso/{provider}` | `api/auth.py` | **KEEP (GATED)** | Gate with feature flag | Placeholder for Phase 2 SSO integration |
| `/api/v1/kpis/{kpi_id}/versions` | `modules/kra_kpi_library/api/routes.py` | **KEEP** | Document as admin API | May be used by admin tools or future features |
| `/api/v1/kpis/{kpi_id}/versions/{version}` | `modules/kra_kpi_library/api/routes.py` | **KEEP** | Document as admin API | May be used by admin tools or future features |
| `/api/v1/kpis/import` | `modules/kra_kpi_library/api/routes.py` | **KEEP** | Document as admin-only | Used by import script; legitimate admin endpoint |
| `/api/v1/observations/{observation_id}/reopen-request` | `modules/observation_capture/api/routes.py` | **KEEP (GATED)** | Gate with feature flag | Business logic exists; may be for future UI feature |
| `/api/v1/observations/{observation_id}/reopen-approval` | `modules/observation_capture/api/routes.py` | **KEEP (GATED)** | Gate with feature flag | Business logic exists; may be for future UI feature |
| `/api/v1/settings/me` | `modules/school_dept_user_role/api/personal_settings.py` | **KEEP** | Document as future API | Legitimate user settings endpoint; likely for future UI |
| `/api/v1/search/saved-filters` | `modules/dashboards_reports_search/api/routes.py` | **KEEP (GATED)** | Gate with feature flag | Business logic exists; may be for future UI feature |

## Detailed Decisions

### 1. Performance Reviews & Scorecards - **KILL**

**Status:** Dead code
**Evidence:**
- Routes defined in `modules/performance-scorecards/api/routes.py`
- NOT imported in `api/main.py`
- No frontend components found
- No internal scheduler or admin scripts reference these routes

**Action:**
- Remove the entire `modules/performance-scorecards` directory
- If these features are needed in the future, they should be re-implemented from scratch with proper planning
- This is premature optimization that is adding technical debt

**Impact:** Low - these routes are not accessible and appear to be completely unused

### 2. MFA Setup - **KEEP (GATED)**

**Status:** Phase 2 feature placeholder
**Evidence:**
- Defined in `api/auth.py` at `/auth/mfa/setup`
- Code comments explicitly state: "Phase 2 SSO integration"
- Currently always returns a 200 response with QR code placeholder
- Not currently called by frontend

**Action:**
- Keep the route but gate it behind a feature flag
- Add `FEATURE_FLAG_MFA_ENABLED` environment variable
- Return 503 Service Unavailable if flag is not set
- Document in roadmap as Phase 2 feature

**Implementation:**
```python
@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(...):
    if not os.getenv("FEATURE_FLAG_MFA_ENABLED"):
        raise HTTPException(status_code=503, detail="MFA feature not enabled")
    # ... existing implementation
```

### 3. SSO Login - **KEEP (GATED)**

**Status:** Phase 2 feature placeholder
**Evidence:**
- Defined in `api/auth.py` at `/auth/sso/{provider}`
- Code comments explicitly state: "Phase 2, reserved: Neon Auth SSO/OAuth connector"
- Currently returns placeholder message

**Action:**
- Keep the route but gate it behind a feature flag
- Add `FEATURE_FLAG_SSO_ENABLED` environment variable
- Return 503 Service Unavailable if flag is not set
- Document in roadmap as Phase 2 feature

**Implementation:**
```python
@router.post("/sso/{provider}")
async def sso_login(provider: str):
    if not os.getenv("FEATURE_FLAG_SSO_ENABLED"):
        raise HTTPException(status_code=503, detail="SSO feature not enabled")
    # ... existing placeholder implementation
```

### 4. KPI Versions - **KEEP**

**Status:** Admin API for future use
**Evidence:**
- Defined in `modules/kra_kpi_library/api/routes.py`
- Not called by frontend `KraList.tsx`
- May be used by admin tools or planned for future features

**Action:**
- Keep the routes as they are legitimate APIs
- Document in API documentation as "Admin or Future Use"
- Consider adding a warning header in OpenAPI docs
- No action needed now

### 5. KPI Import - **KEEP**

**Status:** Active admin endpoint
**Evidence:**
- Defined in `modules/kra_kpi_library/api/routes.py`
- Used by import script (not frontend)
- Legitimate admin-only operation

**Action:**
- Keep the route as it is actively used
- Ensure it has proper authentication and authorization
- Document as "Admin Only" in API docs
- No action needed now

### 6. Observation Reopen Request/Approval - **KEEP (GATED)**

**Status:** Future UI feature
**Evidence:**
- Defined in `modules/observation_capture/api/routes.py`
- Business logic exists and is functional
- Not currently called by frontend
- Represents a legitimate business workflow

**Action:**
- Keep the routes but gate them behind a feature flag
- Add `FEATURE_FLAG_OBSERVATION_REOPEN_ENABLED` environment variable
- Return 503 Service Unavailable if flag is not set
- Document in roadmap as future UI feature

**Implementation:**
```python
@router.post("/observations/{observation_id}/reopen-request")
async def request_reopen(...):
    if not os.getenv("FEATURE_FLAG_OBSERVATION_REOPEN_ENABLED"):
        raise HTTPException(status_code=503, detail="Observation reopen feature not enabled")
    # ... existing implementation
```

### 7. Settings/me - **KEEP**

**Status:** Future user settings API
**Evidence:**
- Defined in `modules/school_dept_user_role/api/personal_settings.py`
- Legitimate user settings endpoint
- Not currently called by main frontend components

**Action:**
- Keep the route as it represents legitimate functionality
- Document as "Future Use" in API docs
- No action needed now

### 8. Saved Filters - **KEEP (GATED)**

**Status:** Future UI feature
**Evidence:**
- Defined in `modules/dashboards_reports_search/api/routes.py`
- Business logic exists
- Not called by `GlobalSearch.tsx`
- Represents a legitimate user workflow

**Action:**
- Keep the routes but gate them behind a feature flag
- Add `FEATURE_FLAG_SAVED_FILTERS_ENABLED` environment variable
- Return 503 Service Unavailable if flag is not set
- Document in roadmap as future UI feature

**Implementation:**
```python
@router.post("/search/saved-filters")
async def create_saved_filter(...):
    if not os.getenv("FEATURE_FLAG_SAVED_FILTERS_ENABLED"):
        raise HTTPException(status_code=503, detail="Saved filters feature not enabled")
    # ... existing implementation
```

## Implementation Priority

1. **Immediate (High Priority):**
   - Remove dead code: `modules/performance-scorecards` directory

2. **Short-term (Medium Priority):**
   - Add feature flags to Phase 2 routes (MFA, SSO)
   - Add feature flags to future UI features (Observation Reopen, Saved Filters)

3. **Documentation (Low Priority):**
   - Document admin-only endpoints in API docs
   - Update roadmap with Phase 2 features

## Security Considerations

- All gated routes should still require authentication even when disabled
- Return 503 (Service Unavailable) rather than 404 to avoid revealing route existence
- Feature flags should be environment-specific (not set in production for Phase 2 features)
- Consider adding rate limiting to all Phase 2 routes even when disabled

## Testing Strategy

- Add tests to verify feature flag gating works correctly
- Add tests to verify dead code removal doesn't break existing functionality
- Document that Phase 2 features should not be tested in production smoke tests

## Sign-off

**Decision Date:** 2025-01-20
**Approved By:** Security Remediation Team
**Next Review:** When Phase 2 features are planned for implementation
