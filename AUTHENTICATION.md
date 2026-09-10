# AUTHENTICATION.md — Self-Managed Authentication

SchoolOps authenticates users entirely on its own infrastructure: **FastAPI + Neon PostgreSQL + Argon2id + secure HTTP-only session cookies**. There is no Clerk, no SaaS identity provider, and no third-party auth dependency.

---

## 1. Architecture

```
React/Vite (frontend/)
   │  fetch(..., credentials:'include')  — cookie travels automatically
   ▼
FastAPI (api/main.py)
   ├── api/auth.py            — /auth/login, /auth/logout, /auth/me, passwords, sessions
   ├── shared/auth.py         — Argon2id hashing, token generation, policy, MFA crypto
   ├── shared/middleware/tenancy.py — session validation + RBAC/tenant scope
   │           │
   │           ▼
   │   Neon PostgreSQL
   │     ├── users                  (password_hash, failed_login_count, locked_until)
   │     ├── auth_sessions          (sha256(token), sliding + absolute expiry)
   │     └── password_reset_tokens  (sha256(token), single-use)
   ▼
Business modules (unchanged) — authorization via roles/permissions/tenant scope
```

**Authentication answers *who* the user is; authorization (roles, permissions, school/department isolation in `shared/middleware/tenancy.py` and `shared/permissions.py`) answers *what they can do* — both are fully preserved.**

---

## 2. Login Flow

```
User → React Login page (frontend/src/components/auth/Login.tsx)
     → POST /auth/login { email, password }
     → FastAPI: lookup user by email
     → verify Argon2id hash (verify_password)
     → lockout check (locked_until) / failure counter update
     → generate 384-bit random token (secrets.token_urlsafe(48))
     → store SHA-256(token) in auth_sessions (never the raw token)
     → Set-Cookie: schoolops_session=<raw token>; HttpOnly; Secure (prod); SameSite=Lax
     → GET /auth/get-session returns the user + roles for the SPA
```

Uniform errors prevent account enumeration: unknown email and wrong password both return `401 {"code":"INVALID_CREDENTIALS","message":"Invalid email or password"}`.

## 3. Logout Flow

```
POST /auth/logout
  → delete the auth_sessions row matching sha256(cookie token)
  → evict from in-process cache
  → clear the cookie (Max-Age=0)
```
The old token can no longer authenticate — the server-side row is gone.

## 4. Session Management

| Property | Value | Env var |
|---|---|---|
| Idle (sliding) timeout | 30 min, auto-extended on activity | `SESSION_TIMEOUT_MINUTES` |
| Absolute ceiling | 12 h — re-login required regardless of activity | `SESSION_ABSOLUTE_TIMEOUT_HOURS` |
| Token | 384-bit random, `secrets.token_urlsafe(48)` | — |
| Storage | SHA-256 hash only (`auth_sessions.token_hash`, unique index) | — |
| Cookie | `HttpOnly`, `SameSite=Lax`, `Secure` in production, path `/` | `SESSION_COOKIE_NAME` |
| Cleanup | idle-expired rows deleted automatically by a startup purge task (runs at boot, then every `SESSION_PURGE_INTERVAL_MINUTES`), after the grace period | `SESSION_CLEANUP_GRACE_HOURS`, `SESSION_PURGE_INTERVAL_MINUTES` |
| Cache | 60 s bounded LRU in-process snapshot (same staleness as the old JWT cache) | — |

Multi-device: `GET /auth/sessions` lists active sessions; `DELETE /auth/sessions/{id}` revokes one.

## 5. Password Hashing

- **Argon2id** (`argon2-cffi`): `time_cost=3, memory_cost=64 MiB, parallelism=4` (OWASP parameters).
- Hashes are salted, self-contained strings — never plaintext, never MD5/SHA-1, never custom crypto.
- Login opportunistically rehashes when parameters change (`check_needs_rehash`).
- **Policy** (`validate_password_policy`): min length `MIN_PASSWORD_LENGTH` (default 10), ≥1 letter, ≥1 digit.

## 6. Password Recovery

```
POST /auth/forgot-password { email }   → always 200, identical body (no enumeration).
                                         Single-use token stored as sha256 hash.
POST /auth/reset-password { token, new_password }
                                       → consumes token, rehashes, REVOKES ALL SESSIONS.
```
Tokens expire after `PASSWORD_RESET_TIMEOUT_MINUTES` (default 30).

**Token delivery — explicit in both modes:**

- `EMAIL_PROVIDER_API_KEY` **set**: delivered by email through the notification service (Resend).
- `EMAIL_PROVIDER_API_KEY` **empty** (self-hosted default): the token is persisted as an **in-app notification row** (`notifications`, channel `in_app`) — the user can read it themselves in the topbar notification bell (`GET /api/v1/notifications`), and a WARNING is logged for operators. The HTTP response is identical either way; the raw token is never in the API response.

**Admin-issued credentials (no email provider needed):**

| Path | Use |
|---|---|
| `POST /api/v1/users/{id}/set-password` with `{ "password": "..." }` | Admin sets the password directly (policy-checked); share over a trusted channel |
| `POST /api/v1/users/{id}/set-password` with `{}` | Admin gets a one-time reset token **in the response** to hand to the user, who completes `POST /auth/reset-password` |
| `python -m scripts.set_user_passwords [--password X] [--emails a,b] [--all --yes]` | Bulk migration of users with `password_hash IS NULL`; unique random password per user printed once |

Both endpoint modes and the script revoke all of the user's existing sessions (force-reset semantics), clear lockout counters, and are scoped exactly like role assignment (SuperAdmin anywhere; Admin only within their own school). Admins can also set an initial password at creation time via the optional `password` field on `POST /api/v1/users`.

A fresh admin-created user therefore reaches a logged-in session without any email provider: create user → admin issues direct password or reset token → user logs in / resets.

## 7. Brute-Force Protection

- Per-account lockout: after `MAX_FAILED_LOGINS` (default 5) failures the account is locked for `LOCKOUT_MINUTES` (default 15) → `423 ACCOUNT_LOCKED`.
- Per-IP rate limits (slowapi): login 10/min, forgot/reset 5/min, get-session 60/min.

## 8. Roles & Permissions (unchanged)

Roles (`superadmin, admin, dept_head, checker, auditor, viewer`) live in `users.roles` (JSONB) and are resolved into `TenantContext` by `require_tenant_context()`. The permission matrix (`permissions` table, `shared/permissions.py`) and field-level permissions apply exactly as before. Nothing about authorization changed.

## 9. School / Department Isolation (unchanged)

`apply_tenant_filter()` / `scoped_to_tenant()` enforce row-level scope on every query:

- **SuperAdmin** — no school filter (manages all schools).
- **Viewer** — filtered by `user_school_grants`.
- **Other roles** — filtered by `school_id` (+ `department_id` when assigned).

Sessions carry only an opaque token; scope is always re-derived from the database, so manipulating `school_id`/`record_id` in a request cannot escape the tenant.

## 10. Admin Creation

```bash
python -m scripts.create_admin --email admin@example.com --name "Platform Admin"
# prompts for a hidden password + confirmation; --password for automation
# --school SCH-01 [--create-school "Name"] to attach/create a school
# --force to add another SuperAdmin when one exists
```
No hardcoded credentials, no default password — refuses weak passwords, refuses duplicate emails.

## 11. MFA (feature-flagged, as before)

`POST /auth/mfa/setup` (gated by `FEATURE_FLAG_MFA_ENABLED`) issues a TOTP secret encrypted at rest with `ENCRYPTION_KEY` (Fernet, R-57). `MFA_REQUIRED_ROLES` lists roles that require it.

## 12. Security Considerations

- Tokens are high-entropy and hashed at rest — a database leak cannot be replayed.
- Cookies are inaccessible to JavaScript (XSS cannot steal the session).
- `SameSite=Lax` + same-origin SPA (backend serves `frontend/dist`) mitigates CSRF; mutating endpoints additionally require JSON bodies.
- CORS `allow_credentials=True` requires explicit `CORS_ORIGINS` in production (validated at startup, wildcard rejected).
- Session rows record IP + user-agent for audit; password changes and resets revoke other sessions.
- Security headers (CSP without any IdP domains, HSTS in production) applied by middleware.
