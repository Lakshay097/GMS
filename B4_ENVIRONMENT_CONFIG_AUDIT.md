# B4: Environment/Config Audit

## Environment Variables in Use

### Security-Critical Variables (Required in Production)

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `ENCRYPTION_KEY` | MFA secret encryption | ✅ Yes | Required in production |
| `INTERNAL_SCHEDULER_SECRET` | Cloud Scheduler auth | ✅ Yes | Required in production |
| `CORS_ORIGINS` | CORS allowed origins | ✅ Yes | Required in production |
| `NEON_AUTH_COOKIE_SECRET` | Neon Auth token validation | ✅ Yes | Required |
| `NEON_AUTH_BASE_URL` | Neon Auth service URL | ✅ Yes | Required |

### Feature Flags (Gated Routes)

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `FEATURE_FLAG_MFA_ENABLED` | Gate `/auth/mfa/setup` | ❌ No | Should be documented |
| `FEATURE_FLAG_SSO_ENABLED` | Gate `/auth/sso/{provider}` | ❌ No | Should be documented |
| `FEATURE_FLAG_OBSERVATION_REOPEN_ENABLED` | Gate observation reopen routes | ❌ No | Should be documented |
| `FEATURE_FLAG_SAVED_FILTERS_ENABLED` | Gate saved filters routes | ❌ No | Should be documented |

### Database Variables

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `DATABASE_URL` | Primary database connection | ✅ Yes | Required |
| `DATABASE_READ_REPLICA_URL` | Read replica for reports | ✅ Yes | Optional |
| `NEON_PROJECT_ID` | Neon project ID | ✅ Yes | Required |
| `NEON_BRANCH_ID` | Neon branch ID | ✅ Yes | Required |
| `NEON_API_KEY` | Neon API key | ✅ Yes | Required |

### Media Storage (Cloudinary)

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name | ✅ Yes | Required |
| `CLOUDINARY_API_KEY` | Cloudinary API key | ✅ Yes | Required |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret | ✅ Yes | Required |
| `CLOUDINARY_UPLOAD_PRESET` | Cloudinary upload preset | ✅ Yes | Required |
| `FILE_UPLOAD_MAX_SIZE_MB` | Max file upload size | ✅ Yes | Configured |
| `EVIDENCE_RETENTION_PERIOD_DAYS` | Evidence retention period | ✅ Yes | Configured |

### Auth Configuration

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `MFA_REQUIRED_ROLES` | Roles requiring MFA | ✅ Yes | Configured |
| `SESSION_TIMEOUT_MINUTES` | Session timeout | ✅ Yes | Configured |

### Security/Network Configuration

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `BEHIND_PROXY` | Proxy detection for rate limiting | ✅ Yes | Configured (A9 fix) |
| `CLOUD_SCHEDULER_IP_RANGES` | Cloud Scheduler IP whitelist | ❌ No | Should be documented |

### Queue Configuration

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `QUEUE_PROVIDER` | Queue backend type | ✅ Yes | Configured |
| `QUEUE_CONNECTION_STRING` | Queue connection string | ✅ Yes | Required |

### Cache/Session

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `REDIS_URL` | Redis connection | ✅ Yes | Required |

### Search Configuration

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `SEARCH_INDEX_URL` | Meilisearch URL | ✅ Yes | Required |
| `SEARCH_INDEX_API_KEY` | Meilisearch API key | ✅ Yes | Required |
| `SEARCH_INDEXING_LAG_TARGET_SECONDS` | Indexing lag target | ✅ Yes | Configured |

### Compliance Configuration

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `DUPLICATE_DETECTION_WINDOW_MINUTES` | Duplicate detection window | ✅ Yes | Configured |
| `GRACE_PERIOD_HOURS` | Default grace period | ✅ Yes | Configured |
| `SCHEDULER_OUTAGE_GRACE_EXTENSION` | Scheduler outage extension | ✅ Yes | Configured |
| `DEFAULT_SCHOOL_TIMEZONE` | Default school timezone | ✅ Yes | Required |

### Notification Providers

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `EMAIL_PROVIDER_API_KEY` | Email provider (Resend) | ✅ Yes | Required |
| `SMS_PROVIDER_API_KEY` | SMS provider | ✅ Yes | Optional |
| `WHATSAPP_PROVIDER_API_KEY` | WhatsApp provider | ✅ Yes | Optional |

### Observability

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `LOG_LEVEL` | Logging level | ✅ Yes | Configured |
| `APM_PROVIDER` | APM provider | ✅ Yes | Optional |
| `ERROR_TRACKING_DSN` | Error tracking DSN | ✅ Yes | Optional |

### SSO Configuration (Phase 2)

| Variable | Usage | Documented in .env.example | Status |
|----------|-------|---------------------------|--------|
| `SSO_PROVIDER` | SSO provider name | ✅ Yes | Phase 2 |
| `SSO_CLIENT_ID` | SSO client ID | ✅ Yes | Phase 2 |
| `SSO_CLIENT_SECRET` | SSO client secret | ✅ Yes | Phase 2 |

### Undocumented Variables

| Variable | Usage | Recommendation |
|----------|-------|----------------|
| `FEATURE_FLAG_MFA_ENABLED` | Gate MFA routes | Add to .env.example |
| `FEATURE_FLAG_SSO_ENABLED` | Gate SSO routes | Add to .env.example |
| `FEATURE_FLAG_OBSERVATION_REOPEN_ENABLED` | Gate observation reopen | Add to .env.example |
| `FEATURE_FLAG_SAVED_FILTERS_ENABLED` | Gate saved filters | Add to .env.example |
| `CLOUD_SCHEDULER_IP_RANGES` | Cloud Scheduler IP whitelist | Add to .env.example |
| `IDEMPOTENCY_EXPIRY_HOURS` | Idempotency cache expiry | Add to .env.example |

## Audit Summary

### ✅ Well Documented
- All security-critical variables documented
- All database, storage, and observability variables documented
- CORS and proxy configuration documented (A9 fix)

### ⚠️ Missing Documentation
- 6 feature flags not documented in .env.example
- Cloud Scheduler IP ranges not documented
- Idempotency configuration not documented

### 🔧 Required Actions
1. Add missing feature flags to .env.example
2. Add CLOUD_SCHEDULER_IP_RANGES to .env.example
3. Add IDEMPOTENCY_EXPIRY_HOURS to .env.example
4. Consider centralizing feature flag documentation