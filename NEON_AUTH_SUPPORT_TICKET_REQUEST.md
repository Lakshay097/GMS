# Neon Auth Support Ticket Request

**Date:** 2026-08-17  
**Priority:** High - Blocking Phase 1.5 Signoff  
**Component:** JWT Plugin Configuration

## Issue Summary

Our application requires JWT tokens for backend verification, but the current Neon Auth instance (ep-restless-moon-axra2khj) returns opaque session tokens instead. The `/token` endpoint returns 401 Unauthorized for all auth methods, suggesting JWT plugin may not be enabled.

## Instance Details

- **Instance:** ep-restless-moon-axra2khj  
- **Region:** us-east-2  
- **URL:** https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth
- **Environment:** Staging/Development

## Investigation Results

### Successful Components
- ✅ Login flow working (returns user data + session token)
- ✅ JWKS endpoint accessible (EdDSA/Ed25519 keys)
- ✅ User data returned in login response

### Failed Components
- ❌ `/token` endpoint: 401 Unauthorized (all auth methods tested)
- ❌ `/get-session` endpoint: Returns null (all auth methods)
- ❌ JWT exchange: No working method found

### Auth Methods Tested on `/token`
All returned 401 Unauthorized:
1. Bearer header with session token
2. Cookie with `__Secure-neonauth.session_token` (Neon Auth's cookie name)
3. Cookie with custom name
4. Both Bearer + Cookie
5. Server-to-server with `NEON_AUTH_COOKIE_SECRET`

### Endpoint Variations Tested
All returned 404:
- `/auth/token`
- `/auth/session/token`
- `/v1/token`
- `/api/token`
- `/jwt`
- `/auth/jwt`

## Request

**Please enable the JWT plugin** for Neon Auth instance `ep-restless-moon-axra2khj` or provide guidance on:

1. How to enable JWT plugin via console/CLI
2. Whether JWT plugin is available for our current plan/tier
3. Alternative methods to obtain JWT tokens from session tokens
4. Any configuration changes needed for `/token` endpoint to work

## Backend Architecture Context

Our backend uses custom JWT verification with JWKS:
- PyJWKClient for public key retrieval
- EdDSA/Ed25519 signature verification
- No Neon Auth SDK dependency on backend
- Expects standard JWT format for tenant context resolution

## Current Workaround

None identified. Cannot proceed with Phase 1.5 signoff until JWT tokens are obtainable.

## Timeline Request

Please respond within 24-48 hours as this is blocking production deployment.

## Contact

**Project:** SchoolOP  
**Technical Contact:** [Your email/Slack]  
**Priority:** Production Blocker

## Additional Context

Based on Neon Auth documentation, JWT is now a plugin-based feature. Our staging instance appears to be using the default session-first architecture without JWT plugin enabled. We need either:
- JWT plugin enabled for our instance, OR
- Alternative method to obtain JWTs from session tokens

Thank you for your assistance in resolving this configuration issue.