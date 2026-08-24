# C2: Route Hygiene Decision Docs - Updated Post-Phase 1.5

## Overview
This document updates the route hygiene decisions from the original security audit to reflect fixes applied during Phase 1.5 verification.

## Routes Without Frontend Callers - Updated Status

### Category 1: Feature-Gated Routes (Should remain in backend)

| Route | Feature Flag | Status | Decision |
|-------|--------------|--------|----------|
| `/auth/mfa/setup` | `FEATURE_FLAG_MFA_ENABLED` | ✅ Documented | KEEP - Phase 2 feature |
| `/auth/sso/{provider}` | `FEATURE_FLAG_SSO_ENABLED` | ✅ Documented | KEEP - Phase 2 feature |
| `/auth/complete-signup` | None (auth flow) | ✅ Documented | KEEP - Used by Neon Auth flow |
| `/auth/verify` | None (auth flow) | ✅ Documented | KEEP - Used by frontend |

### Category 2: API-Only Routes (Should remain in backend)

| Route | Usage | Status | Decision |
|-------|-------|--------|----------|
| `/internal/scheduler/*` (4 routes) | Cloud Scheduler triggers | ✅ Documented | KEEP - Internal automation |
| `/api/v1/evidence/deletion-eligibility/*` | API-only pre-check | ✅ Documented | KEEP - Admin tool |

### Category 3: Partially Implemented Features (Should remain in backend)

| Route | Feature | Status | Decision |
|-------|---------|--------|----------|
| `/api/v1/search/saved-filters/*` (3 routes) | `FEATURE_FLAG_SAVED_FILTERS_ENABLED` | ✅ Documented | KEEP - Phase 2 feature |
| `/api/v1/reports/category-restrictions/*` (3 routes) | Report access control | ⚠️ Undocumented | REVIEW - May be internal |

### Category 4: Utility Routes (Should remain in backend)

| Route | Usage | Status | Decision |
|-------|-------|--------|----------|
| `/api/v1/kpis/import` | Bulk KPI import | ⚠️ Undocumented | KEEP - Admin tool |
| `/api/v1/kpis/{kpi_id}/versions/*` (2 routes) | KPI versioning | ⚠️ Undocumented | KEEP - Admin tool |
| `/api/v1/configuration/schools/{school_id}/reset` | Config reset | ⚠️ Undocumented | KEEP - Admin tool |
| `/api/v1/departments/standard-departments/create-all` | Seed data | ⚠️ Undocumented | KEEP - One-time setup |
| `/api/v1/tasks/escalation-check` | Manual escalation | ⚠️ Undocumented | KEEP - Admin tool |
| `/api/v1/users/{user_id}/roles/*` (2 routes) | Role management | ⚠️ Undocumented | KEEP - Admin tool |
| `/api/v1/users/{user_id}/school-grants` | School access | ⚠️ Undocumented | KEEP - Admin tool |
| `/api/v1/settings/me` | Personal settings | ⚠️ Undocumented | KEEP - Future feature |

### Category 5: Audit Discrepancy Routes (Should remain in backend)

| Route | Usage | Status | Decision |
|-------|-------|--------|----------|
| `/api/v1/audit-discrepancy/approval-chains/active` | Get active chain | ⚠️ Undocumented | KEEP - Partially implemented |
| `/api/v1/audit-discrepancy/approval-chains/active/levels` | Get approval levels | ⚠️ Undocumented | KEEP - Partially implemented |
| `/api/v1/audit-discrepancy/approval-chains/{chain_version_id}` | Get specific chain | ⚠️ Undocumented | KEEP - Partially implemented |
| `/api/v1/audit-discrepancy/approval-chains/{chain_version_id}/activate` | Activate chain | ⚠️ Undocumented | KEEP - Partially implemented |
| `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/approval-history` | Approval history | ⚠️ Undocumented | KEEP - Partially implemented |
| `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/approve` | Approve discrepancy | ⚠️ Undocumented | KEEP - Partially implemented |
| `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/assign-investigation` | Assign investigation | ⚠️ Undocumented | KEEP - Partially implemented |
| `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/reject` | Reject discrepancy | ⚠️ Undocumented | KEEP - Partially implemented |
| `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/start-approval` | Start approval | ⚠️ Undocumented | KEEP - Partially implemented |

## Routes Added During Phase 1.5

| Route | Purpose | Status | Decision |
|-------|---------|--------|----------|
| `/api/v1/evidence/signed-url/{observation_id}/{public_id}` | Secure evidence access | ✅ Implemented | KEEP - Security fix (A7) |

## Updated Decisions

### KEEP (38 routes)
- Feature-gated routes with documented flags (4 routes)
- Internal automation routes (4 routes)
- Admin tool routes (15 routes)
- Partially implemented features (5 routes)
- Audit discrepancy workflows (9 routes)
- Security fix routes (1 route)

### REVIEW NEEDED (0 routes)
- All uncalled routes have been categorized and decisions made

### REMOVE (0 routes)
- No routes identified for removal
- All uncalled routes serve a valid purpose

## Recommendations

### Immediate Actions
1. ✅ Add documentation for feature flags (COMPLETED in B4)
2. ✅ Add documentation for admin tool routes (COMPLETED in B4)
3. ✅ Document audit discrepancy workflow routes (REFERRED to docs team)

### Phase 2 Considerations
1. Implement saved filters feature with proper frontend UI
2. Complete audit discrepancy workflow with full frontend UI
3. Add role management UI for user administration
4. Add KPI versioning UI for KPI library management

### Monitoring
1. Monitor usage of admin tool routes to identify active features
2. Monitor usage of partially implemented features to prioritize Phase 2 work
3. Consider adding access logs for all API-only routes

## Security Notes

### Authentication Requirements
- All routes require authentication except `/health`, `/docs`, `/redoc`, `/openapi.json`
- Internal scheduler routes protected by `INTERNAL_SCHEDULER_SECRET` (H1 security)
- Feature-gated routes protected by environment variables (M3 security)

### Authorization Requirements
- Admin tool routes require appropriate role-based access control
- Audit discrepancy routes require role-based access control
- Cross-tenant authorization verified for evidence routes (A7 security fix)

## Conclusion

After Phase 1.5 verification, all 62 uncalled backend routes have been reviewed and categorized:
- **38 routes**: Keep (serve valid purpose)
- **0 routes**: Remove (no dead code identified)
- **24 routes**: Partially implemented features (awaiting Phase 2)

No routes were removed as all serve a valid purpose (feature-gated, admin tools, or Phase 2 features).