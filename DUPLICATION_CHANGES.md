# DUPLICATION_CHANGES.md — Clerk → Self-Managed Authentication

Record of the conversion of SchoolOps into an **independent application with fully self-managed authentication** (FastAPI + Neon PostgreSQL). The UI, business logic, workflows, permissions and data model are unchanged.

---

## 1. Removed

| Item | Where |
|---|---|
| Clerk JWT/JWKS verification (`PyJWKClient`, RS256/ES256, token LRU cache) | `shared/auth.py` (rewritten) |
| `ClerkClient` class, `sync_roles_to_clerk()` (Clerk Backend API calls) | `shared/auth.py`, `modules/school-dept-user-role/services/user_service.py` |
| `clerk_user_id` column (UNIQUE, NOT NULL) | `users` table — dropped by migration `20260906_1000_self_managed_auth` |
| Clerk webhook handler + Svix signature verification | `api/webhooks.py` (now an empty router) |
| Endpoints `/auth/set-auth-cookie`, `/auth/link-account`, `/auth/check-provisioning`, `/auth/sso/{provider}` | `api/auth.py` (rewritten) |
| `@clerk/clerk-react` npm dependency (`ClerkProvider`, `SignIn/SignUpButton`, `SignedIn/SignedOut`, `UserButton`, `useUser`, `useClerk`, `publicMetadata`) | `frontend/package.json`, `frontend/src/*` |
| Env vars `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`, `CLERK_WEBHOOK_SECRET`, `VITE_CLERK_PUBLISHABLE_KEY`, `VITE_NEON_AUTH_URL` | `.env.example`, `Dockerfile`, `cloudbuild.yaml` |
| Clerk CSP allowances (`*.clerk.accounts.dev`, `clerk-telemetry.com`) | `api/main.py` |
| Clerk test suites & E2E scripts (`test_clerk_integration.py`, `test_neon_auth_*.py`, `test_session_*_validation*.py`, `test_frontend_jwt_retrieval.py`, `test_clerk_neon_e2e.py`, `test_neon_auth.js`, `frontend/test_clerk_jwt.html`, `CLERK_MIGRATION_GUIDE.md`, `setup-gcp-secrets.sh` Clerk section) | deleted |
| `clerk_user_id=...` kwargs in every test/fixture User constructor (~98 occurrences) | `tests/**` |

## 2. Replaced With

| New | File(s) |
|---|---|
| Argon2id hashing (`hash_password`/`verify_password`/`needs_rehash`), password policy, session-token generation/hashing, MFA crypto (kept), password-reset tokens | `shared/auth.py` |
| `POST /auth/login` (Argon2id verify → DB session → HttpOnly cookie), `POST /auth/logout` (server-side invalidation), `GET /auth/me` + `/auth/get-session` (compat), `POST /auth/verify` (compat), `POST /auth/change-password`, `POST /auth/forgot-password`, `POST /auth/reset-password`, `GET/DELETE /auth/sessions`, `POST /auth/complete-signup` (session-based), `POST /auth/mfa/setup`, `GET /auth/schools` | `api/auth.py` |
| Session validation against `auth_sessions` (cookie or Bearer), sliding+absolute expiry, 60 s bounded cache; identical `TenantContext`, `apply_tenant_filter`, `scoped_to_tenant` authorization surface | `shared/middleware/tenancy.py` |
| `AuthProvider` / `useAuth()` abstraction (`user, isAuthenticated, loading, error, roles, perms, schoolId, departmentId, login, logout, refresh`) | `frontend/src/contexts/AuthContext.tsx` |
| Cookie-only `authFetch`/`login`/`logout`/`getSession`/`changePassword`/`forgotPassword`/`resetPassword` client | `frontend/src/lib/auth.ts` |
| `apiFetch`/`fetchWithAuth` without JWT handling (cookie travels automatically) | `frontend/src/lib/api.ts` |
| Email/password Login page and Forgot/Reset password page (original auth-screen design preserved) | `frontend/src/components/auth/Login.tsx`, `ForgotPassword.tsx` |
| Session-based `RequireAuth` (redirects to `/auth/sign-in`; superadmin/admin school bypass preserved) and in-app profile menu replacing Clerk's `UserButton` | `frontend/src/App.tsx` |
| "Initial Password" field (optional, policy-validated) replacing the manual Clerk User ID field | `frontend/src/components/users/UserForm.tsx`, `modules/school-dept-user-role/api/users.py` |
| First-admin CLI: `python -m scripts.create_admin` | `scripts/create_admin.py` |
| Read-only in-app notification center: bell dropdown in the topbar + `GET /api/v1/notifications`, `GET /api/v1/notifications/unread-count`, `POST /api/v1/notifications/{id}/read`, `POST /api/v1/notifications/read-all` (strictly per-user; `notifications.read_at` added by migration `20260906_1100_notification_read_at`) — makes the self-hosted reset-token fallback user-visible | `api/notifications.py`, `frontend/src/components/notifications/NotificationBell.tsx` |

## 3. Preserved (untouched)

- All business modules: KRA/KPI library, KPI entries & checker views, observations + evidence, audit/discrepancies, approval chains, tasks + escalation, dashboards/reports/search, settings/master data, feature flags, locations, notifications, schedulers, audit-log service, rule/config/workflow engines.
- RBAC: roles, permission matrix, field-level permissions, `PermissionChecker`.
- Tenant isolation: `school_id`/`department_id` filters, `user_school_grants`, SuperAdmin/Viewer semantics.
- UI/design system, i18n, Sentry, Cloudinary evidence, Redis queue, Meilisearch config, idempotency middleware.
- User archival semantics (never hard-delete), department-request workflow, complete-signup school picker.

## 4. Database Changes (Alembic `20260906_1000_self_managed_auth`)

- `users`: **drop** `clerk_user_id`; **add** `password_hash VARCHAR(255)`, `failed_login_count INTEGER NOT NULL DEFAULT 0`, `locked_until TIMESTAMPTZ`.
- **New** `auth_sessions`: `id, user_id→users ON DELETE CASCADE, token_hash (unique idx), created_at, expires_at, absolute_expires_at, last_used_at, ip_address, user_agent`.
- **New** `password_reset_tokens`: `id, user_id→users, token_hash (unique idx), created_at, expires_at, used_at`.
- Also made `20260902_observation_schema_drift_fix` idempotent (pre-existing bug: re-added already-present columns and crashed `alembic upgrade head`).

## 5. Environment Changes (`.env.example`)

Removed: all `CLERK_*`, `VITE_CLERK_*`, `NEON_AUTH_*`.
Added: `SESSION_TIMEOUT_MINUTES`, `SESSION_ABSOLUTE_TIMEOUT_HOURS`, `SESSION_COOKIE_NAME`, `SESSION_PURGE_INTERVAL_MINUTES`, `MAX_FAILED_LOGINS`, `LOCKOUT_MINUTES`, `MIN_PASSWORD_LENGTH`, `PASSWORD_RESET_TIMEOUT_MINUTES`.
Kept: `DATABASE_URL`, `DATABASE_READ_REPLICA_URL`, `ENCRYPTION_KEY`, `PLATFORM_JWT_SECRET` (tests/internal only), `INTERNAL_SCHEDULER_SECRET`, `CORS_ORIGINS`, Cloudinary, Redis/queue, Resend email, Sentry, search.

## 6. Deployment Changes

- Single container unchanged: FastAPI serves `frontend/dist` (catch-all SPA route).
- `Dockerfile`/`cloudbuild.yaml`: Clerk/Neon-Auth build args and secrets removed.
- Run `alembic upgrade head` on the (Neon) database before first start, then create the first SuperAdmin.

## 7. Setup (exact commands)

```bash
# 1. Backend deps
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env            # set DATABASE_URL (Neon), ENCRYPTION_KEY, CORS_ORIGINS, …

# 3. Database migrations
alembic upgrade head

# 4. First admin
python -m scripts.create_admin --email admin@example.com --name "Platform Admin"

# 4b. Migrated users without credentials? Set initial passwords in bulk
#     (prints one strong password per user; or --password to share one)
python -m scripts.set_user_passwords

# 5. Backend
uvicorn api.main:app --host 0.0.0.0 --port 8000

# 6. Frontend (dev)
cd frontend && npm install && npm run dev
#    (production: npm run build → served by FastAPI at /)

# 7. Tests
python -m pytest tests/unit/ tests/test_cookie_auth.py tests/test_scope_isolation.py
python tests/e2e/test_self_managed_auth_flow.py http://127.0.0.1:8000   # against a running server
cd frontend && npm run lint && npm run build

# 8. Deploy (Cloud Run via cloudbuild.yaml, or any container host)
#    Set DATABASE_URL, ENCRYPTION_KEY, CORS_ORIGINS, PLATFORM_JWT_SECRET,
#    INTERNAL_SCHEDULER_SECRET at runtime; run alembic upgrade head on release.
```

## 8. Remaining "Clerk" Mentions (informational only — zero runtime references)

Historical Alembic migration `20260817_migrate_neon_auth_to_clerk.py` (kept for chain integrity) and prose comments in docs/tests describing the removal. No code imports, calls, or configures Clerk.

## 9. Known Issues

- Two pre-existing, date-dependent test failures (`tests/unit/test_BR24_timezone_aware_generation.py::test_BR24_backfill_*`) — they fail identically on the unmodified original code and are unrelated to authentication.
- Frontend lint reports pre-existing warnings across legacy components (setState-in-effect, `any`); the auth rewrite files are clean and the overall error count decreased.
- Password-reset token delivery is explicit in both modes: with `EMAIL_PROVIDER_API_KEY` the token is emailed via the notification service; without it the token is persisted as an in-app `notifications` row (recoverable by an operator) and a WARNING names the user — the response stays uniform. Admins bypass delivery entirely via `POST /api/v1/users/{id}/set-password` (direct password or response-embedded one-time token) and `scripts/set_user_passwords.py`.
- Fixed en route (pre-existing bug surfaced by the live E2E): `shared/platform_models.Notification.channel/status` were declared as native PG enums while the `notifications` migration created plain `VARCHAR` columns — every notification insert failed against Neon with `type "notificationchannel" does not exist`. The ORM now uses non-native (VARCHAR) enums for those two columns.
- Fixed en route (found by exercising the full workflow chain live): (1) `configuration_items` was never seeded on fresh databases — `ConfigurationEngine.seed_defaults()` now runs idempotently at app startup; (2) 17 more ORM enum declarations claimed native PG types that do not exist in the database (tasks, observations, configuration, escalations, compliance, checklists, scorecards, expirations) — all flipped to `native_enum=False` to match the actual VARCHAR schema; (3) `submit_observation` named its pydantic body `request`, which the slowapi rate limiter grabbed instead of the starlette Request — every KPI entry submission 500'd; renamed to `request: Request, body: ...` (the pattern already used in `audit_discrepancy`); (4) task/escalation endpoints referenced an undefined `db` (and `user_roles_lower`) — added the missing `Depends(get_db)` parameters; (5) `NotificationService.dispatch` enqueued to Redis inside the triggering transaction, so an unreachable queue failed the whole business operation — enqueue is now best-effort (R-40) with the row left PENDING for retry; (6) the escalation scheduler fed a role-name string into the UUID `task_escalations.escalated_to_role_id` column — non-UUID role names are now dropped from the record (they stay on the rule and in the notes); (7) task ETA inputs that carry a timezone (the frontend sends `toISOString()`) crashed `create_task` against the naive-UTC service — `TaskCreate.eta` and `EtaExtensionRequest.new_eta` now normalize aware datetimes to naive UTC.
- MFA enrollment UI is backend-only (unchanged from original, which also exposed setup via API behind a feature flag).
