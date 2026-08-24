# B1: Backend Route Enumeration vs Frontend Call Sites Analysis

## Backend Routes (87 total from FastAPI)

### Authentication Routes (8)
- GET /auth/get-session
- POST /auth/complete-signup
- POST /auth/link-account
- POST /auth/logout
- POST /auth/mfa/setup
- POST /auth/set-auth-cookie
- POST /auth/sso/{provider}
- POST /auth/verify

### API v1 Routes (76)
- Audit Discrepancy (13): approval-chains, discrepancies, approval workflows
- Configuration (5): global and school-level config
- Dashboard (1): main dashboard
- Departments (7): CRUD operations
- Evidence (4): upload, delete, signed-url, deletion-eligibility
- KPI Library (8): KPI CRUD and versioning
- KRA Library (3): KRA CRUD
- Observations (5): CRUD and reopen workflows
- Reports (6): report generation and export
- Search (4): global search and saved filters
- Schools (5): CRUD operations
- Settings (2): personal settings
- Tasks (6): task management and escalation
- Users (7): user management and school grants

### Internal Routes (4)
- POST /internal/scheduler/* (4): scheduler triggers

### Documentation Routes (3)
- GET /docs, /redoc, /openapi.json

## Frontend API Calls Analysis

### Direct API Calls Found (from grep):
- `/api/v1/dashboard` - Dashboard.tsx ✓
- `/api/v1/schools` - Multiple components ✓
- `/api/v1/departments` - Multiple components ✓
- `/api/v1/users` - Multiple components ✓
- `/api/v1/tasks` - TaskForm, TaskList, TaskDetail ✓
- `/api/v1/observations` - Multiple components ✓
- `/api/v1/kras` - KraList, KraForm ✓
- `/api/v1/kpis` - Multiple components ✓
- `/api/v1/reports` - ReportRunner, ReportCatalogue ✓
- `/api/v1/reports/export` - ReportRunner ✓
- `/api/v1/search` - GlobalSearch ✓
- `/api/v1/configuration/global` - ConfigurationPanel, SettingsMasterData ✓
- `/api/v1/configuration/schools/{school_id}` - ConfigurationPanel ✓
- `/api/v1/audit-discrepancy/approval-chains` - ApprovalChains ✓
- `/api/v1/audit-discrepancy/discrepancies` - DiscrepancyList, DiscrepancyDetail ✓
- `/api/v1/evidence/signed-url/{observation_id}/{public_id}` - api.ts ✓
- `/api/v1/escalation-rules` - EscalationRules ✓

### Auth Routes (via api.ts):
- `/auth/link-account` - api.ts ✓
- `/auth/get-session` - api.ts ✓

## Analysis Results

### ✅ Matched Routes (Frontend calls backend routes that exist)
All major frontend API calls have matching backend routes. No broken routes found.

### ⚠️ Routes Without Frontend Callers (Candidate for review)
1. **Audit Discrepancy** (9 routes):
   - `/api/v1/audit-discrepancy/approval-chains/active`
   - `/api/v1/audit-discrepancy/approval-chains/active/levels`
   - `/api/v1/audit-discrepancy/approval-chains/{chain_version_id}`
   - `/api/v1/audit-discrepancy/approval-chains/{chain_version_id}/activate`
   - `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/approval-history`
   - `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/approve`
   - `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/assign-investigation`
   - `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/reject`
   - `/api/v1/audit-discrepancy/discrepancies/{discrepancy_id}/start-approval`

2. **Configuration** (1 route):
   - `/api/v1/configuration/schools/{school_id}/reset`

3. **Departments** (1 route):
   - `/api/v1/departments/standard-departments/create-all`

4. **Evidence** (1 route):
   - `/api/v1/evidence/deletion-eligibility/{observation_id}/{public_id}`

5. **KPI Library** (2 routes):
   - `/api/v1/kpis/import`
   - `/api/v1/kpis/{kpi_id}/versions`
   - `/api/v1/kpis/{kpi_id}/versions/{version}`

6. **Reports** (3 routes):
   - `/api/v1/reports/category-restrictions` (3 variants)

7. **Search** (3 routes):
   - `/api/v1/search/saved-filters` (3 variants)

8. **Settings** (1 route):
   - `/api/v1/settings/me`

9. **Tasks** (1 route):
   - `/api/v1/tasks/escalation-check`

10. **Users** (3 routes):
    - `/api/v1/users/{user_id}/roles` (2 variants)
    - `/api/v1/users/{user_id}/school-grants`

11. **Authentication** (4 routes):
    - `/auth/complete-signup`
    - `/auth/mfa/setup`
    - `/auth/sso/{provider}`
    - `/auth/verify`

### 🆕 New Routes from Phase 1 (Verified)
- `/auth/set-auth-cookie` - Used by frontend (via api.ts) ✓
- `/api/v1/evidence/signed-url/{observation_id}/{public_id}` - Added for A7 fix, used by frontend ✓

### 🔍 Feature-Gated Routes (Need Verification)
- `/auth/mfa/setup` - Gated by FEATURE_FLAG_MFA_ENABLED
- `/auth/sso/{provider}` - Gated by FEATURE_FLAG_SSO_ENABLED
- `/api/v1/search/saved-filters` - May be gated (need to verify)

### 📊 Summary
- **Total backend routes**: 87
- **Frontend-called routes**: ~25
- **Uncalled routes**: ~62
- **Potentially broken**: 0 (all frontend calls have matching backend routes)
- **Action needed**: Review 62 uncalled routes for:
  1. Feature flag gating verification
  2. API-only use cases (cron jobs, internal services)
  3. Dead code that should be removed
  4. Future features not yet implemented