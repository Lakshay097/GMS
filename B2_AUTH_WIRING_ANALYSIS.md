# B2: Auth Wiring Audit - Neon Auth Integration

## Current Auth Flow Analysis

### Token Types Supported
Based on `shared/auth.py`:
1. **Neon Auth asymmetric JWT** (EdDSA/RS256) - verified via JWKS
2. **Platform HS256 tokens** - verified with `NEON_AUTH_COOKIE_SECRET`

### Current Flow (from code analysis)

#### 1. Frontend → Backend Auth Exchange
- Frontend calls `/auth/set-auth-cookie` with a token
- Backend validates token via `decode_access_token()`
- Backend sets httpOnly cookie with the token

#### 2. Token Validation
`decode_access_token()` tries:
1. Neon Auth JWKS verification (preferred)
2. Falls back to HS256 with `NEON_AUTH_COOKIE_SECRET`

#### 3. Protected Routes
- Middleware reads token from cookie first, then Authorization header
- Token validated via `decode_access_token()`
- Tenant context extracted from validated token

### 🔍 Critical Questions to Verify

#### Q1: Which token type is actually in the cookie?
**Status**: UNCLEAR from code inspection
- Frontend sends token to `/auth/set-auth-cookie` but token source not visible in current code
- Need to verify: Is this a Neon Auth token or a platform-issued token?

#### Q2: Does `/auth/link-account` set the cookie for new users?
**Status**: NO - POTENTIAL BUG
- `/auth/link-account` does NOT call `response.set_cookie()`
- New users are created and linked, but no cookie is set
- **Issue**: New users will link successfully but fail subsequent requests

#### Q3: Is logout working correctly?
**Status**: YES
- `/auth/logout` sets expired cookie with correct attributes
- Matches cookie settings from `/auth/set-auth-cookie`

#### Q4: Token validation consistency
**Status**: UNCLEAR
- `decode_access_token()` accepts both token types
- But which one is actually being used in production is unknown
- Risk: Wrong secret validation if token type mismatches expectation

### 🚨 Identified Issues

#### Issue 1: Cookie not set in `/auth/link-account`
**Impact**: NEW USERS BROKEN
- User completes Neon Auth → `/auth/link-account` → user created
- But no cookie is set, so next request fails with 401
- **Fix needed**: Add cookie setting to `/auth/link-account` response

#### Issue 2: Unclear token type in cookie
**Impact**: POTENTIAL PRODUCTION FAILURE
- If cookie holds Neon Auth token but code expects platform token (or vice versa), auth fails
- Need to verify which token type is actually used

#### Issue 3: Cookie setting attributes verification
**Status**: PARTIALLY VERIFIED
- `httponly=True`, `Secure=True`, `SameSite=Lax` confirmed in code
- Need to verify these are actually present in Set-Cookie header in live test

### ✅ Working Correctly
- Token extraction from cookie (middleware updated)
- Cookie logout (expired cookie set correctly)
- CORS configuration for cookie-based auth
- Rate limiting on auth endpoints

### 🔧 Required Fixes
1. Add cookie setting to `/auth/link-account` endpoint
2. Clarify token type flow (Neon Auth vs platform token)
3. Add integration test for full auth flow