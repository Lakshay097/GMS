# Route Hygiene Decisions

**Date:** 2026-08-17
**Priority:** Medium
**Scope:** SuperAdmin controls, CORS, KPI import, Boto3 dependency

## Summary

Route hygiene improvements have been implemented to strengthen security around destructive actions and sensitive endpoints.

## Implemented Changes

### 1. SuperAdmin Destructive Action Confirmation

**Problem:** SuperAdmin endpoints for destructive actions (deactivate, archive, deprecate) had no confirmation mechanism, making accidental destructive operations possible.

**Solution:** Added `confirm=true` query parameter requirement to destructive endpoints:

- `/api/v1/schools/{school_id}/deactivate` - Now requires `confirm=true`
- `/api/v1/users/{user_id}/archive` - Now requires `confirm=true`
- `/api/v1/kpis/{kpi_id}/deprecate` - Now requires `confirm=true`

**Implementation:**
```python
confirm: bool = Query(False, description="Must be true to confirm destructive action")
```

If `confirm` is not `true`, returns:
```json
{
  "error": {
    "code": "CONFIRMATION_REQUIRED",
    "message": "Destructive action requires confirmation. Set confirm=true to proceed."
  }
}
```

**Files Modified:**
- `modules/school-dept-user-role/api/schools.py`
- `modules/school-dept-user-role/api/users.py`
- `modules/kra-kpi-library/api/routes.py`

### 2. KPI Import Endpoint Hidden from Public Docs

**Problem:** `/api/v1/kpis/import` is a SuperAdmin-only endpoint for bulk KPI import. Being exposed in public OpenAPI docs could reveal internal system capabilities.

**Solution:** Added `include_in_schema=False` to the route decorator.

**Implementation:**
```python
@router.post("/kpis/import", include_in_schema=False)
```

**Files Modified:**
- `modules/kra-kpi-library/api/routes.py`

### 3. CORS Configuration

**Status:** Already properly configured in `api/main.py`

**Current Implementation:**
- Development: Defaults to localhost origins for convenience
- Production: Requires explicit `CORS_ORIGINS` environment variable
- Warning logged if wildcard (`*`) is used in production
- Credentials allowed for cookie-based authentication

**No changes needed** - CORS is already properly configured with security in mind.

### 4. Boto3/S3 Dependency

**Status:** Legitimate use case - KEEP

**Analysis:**
- boto3 is used in `shared/task_queue.py` for AWS SQS integration
- The dependency is in `pyproject.toml` with version `>=1.28.0`
- Used for async task queue operations (enqueue/dequeue)
- This is a legitimate infrastructure dependency for distributed task processing

**Decision:** Keep boto3 dependency as it serves a legitimate purpose for the task queue system.

**Files:**
- `shared/task_queue.py` - Uses boto3 for SQS client
- `pyproject.toml` - boto3 dependency declaration

## Security Impact

### Before
- SuperAdmin could accidentally deactivate schools, archive users, or deprecate KPIs without confirmation
- KPI import endpoint was visible in public API documentation
- CORS was already properly configured (no change needed)
- Boto3 dependency was legitimate (no change needed)

### After
- All destructive SuperAdmin actions require explicit `confirm=true` parameter
- KPI import endpoint is hidden from public OpenAPI docs
- CORS remains properly configured
- Boto3 dependency remains as legitimate infrastructure code

## Testing

Created `tests/test_route_hygiene.py` to verify:
1. Destructive endpoints require confirmation parameter
2. KPI import endpoint is hidden from schema
3. CORS configuration is environment-aware
4. Boto3 is used for legitimate purposes

## Documentation Updates

- Updated route docstrings to reflect confirmation requirement
- Added security notes to destructive endpoints
- Documented Boto3 use case in this file

## Future Considerations

1. **Audit Logging:** Consider adding audit log entries for all destructive actions, even if confirmation is provided
2. **Multi-Factor Confirmation:** For extremely destructive actions (e.g., school deactivation), consider requiring additional confirmation beyond a simple boolean
3. **Rate Limiting:** Consider adding stricter rate limits to destructive endpoints to prevent bulk accidental operations
4. **Email Notifications:** Consider sending email notifications to other SuperAdmins when destructive actions are performed

## Sign-off

**Decision Date:** 2026-08-17
**Approved By:** Security Remediation Team
**Next Review:** When additional destructive endpoints are added
