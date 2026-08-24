# Neon Auth Architecture Mismatch Analysis

**Date:** 2026-08-17  
**Context:** Live verification against staging Neon Auth instance  
**Status:** ⚠️ **BLOCKING ISSUE FOR PHASE 1.5 SIGNOFF**

## Executive Summary

Live verification against the staging Neon Auth instance has revealed a **fundamental architectural mismatch** between our backend expectations and current Neon Auth behavior. Our backend expects JWT tokens for verification, but Neon Auth now returns opaque session tokens by default.

## Live Verification Results

### ✅ Working Components
- **JWKS Endpoint**: Accessible and valid (EdDSA/Ed25519)
- **Authentication Flow**: Working (returns user data)
- **User Data**: Available in login response

### ❌ Critical Issues
- **Token Format**: 32-character opaque session token (e.g., `Uxl2VkU4bhl3e0Rpey6gH4zjov7YnrZU`)
- **JWT Exchange**: `/token` endpoint returns 401 Unauthorized
- **Session API**: `/get-session` returns null
- **Backend Compatibility**: Our `decode_access_token()` cannot process session tokens

## Detailed Findings

### 1. Token Format Change
**Expected (Our Backend):** JWT with 3-part structure (header.payload.signature)  
**Actual (Current Neon Auth):** 32-character opaque session token

**Impact:** Our entire JWT verification pipeline in `shared/auth.py` cannot process current tokens.

### 2. JWT Exchange Failure
**Attempted Methods:**
- `/token` endpoint with Bearer header: 401 Unauthorized
- `/token` endpoint with session cookie: 401 Unauthorized  
- `/get-session` endpoint: Returns null
- Alternative endpoints: All failed or returned no JWT

**Impact:** No working method to exchange session tokens for JWTs.

### 3. Documentation Analysis
**Key Finding:** According to Neon Auth documentation, JWT is now a **plugin-based feature**:

> "Managed Better Auth's JWT plugin lets backend services, CLI tools, and cross-domain API requests retrieve raw JSON Web Tokens via `authClient.token()` or the `set-auth-jwt` response header, rather than relying on HTTP-only session cookies."

> "This plugin is **not** a replacement for session management in web applications. For standard browser-based apps (Next.js, React, Vue, etc.), rely on the default session cookie mechanism provided by `authClient.signIn` and `authClient.getSession`."

**Implication:** JWTs are now opt-in via plugin configuration, not the default.

## Root Cause Analysis

### Most Likely: JWT Plugin Not Enabled
The staging Neon Auth instance likely does not have the JWT plugin enabled, making it incompatible with our JWT-based backend verification.

### Alternative: Architecture Change
Neon Auth may have shifted to session-first architecture where JWTs are only available through specific SDK methods with proper browser context.

## Resolution Options

### Option A: Enable JWT Plugin (RECOMMENDED)
**Approach:** Enable JWT plugin in Neon Auth configuration  
**Steps:**
1. Check Neon Auth console/CLI for JWT plugin configuration
2. Enable JWT plugin for the staging instance
3. Re-test JWT exchange endpoints
4. Verify our backend works with obtained JWTs

**Pros:**
- Minimal code changes required
- Maintains current security model (JWKS verification)
- Aligns with our existing architecture

**Cons:**
- Requires Neon Auth configuration access
- May not be available in all Neon Auth tiers
- Unknown if plugin is available for our instance

**Effort:** Low (if configuration available)

### Option B: Frontend SDK JWT Retrieval
**Approach:** Use frontend SDK to get JWT and pass to backend  
**Steps:**
1. Update frontend to use `authClient.token()` after login
2. Pass JWT to backend via `/auth/set-auth-cookie` or similar
3. Backend continues using JWT verification

**Pros:**
- No backend architecture changes
- Uses documented SDK method
- Maintains JWKS verification

**Cons:**
- Requires frontend changes
- Adds complexity to auth flow
- Depends on proper browser session context

**Effort:** Medium

### Option C: Session Token Validation
**Approach:** Update backend to validate session tokens directly  
**Steps:**
1. Implement session token validation with Neon Auth API
2. Replace JWT verification with session validation
3. Update tenant context resolution
4. Add caching to reduce API calls

**Pros:**
- Works with current Neon Auth configuration
- No plugin configuration needed
- Aligns with Neon Auth's default flow

**Cons:**
- **Major backend architecture change**
- Adds external API dependency for every request
- **Different failure modes** (API availability vs local verification)
- **Latency impact** (API call vs local JWKS verification)
- Requires significant testing and validation

**Effort:** High

### Option D: Hybrid Approach
**Approach:** Support both JWT and session tokens  
**Steps:**
1. Update backend to handle both token types
2. Try JWT verification first, fall back to session validation
3. Phase out JWT support over time if needed

**Pros:**
- Backward compatible
- Gradual migration path
- Maximum flexibility

**Cons:**
- Most complex implementation
- Maintains two code paths
- Higher maintenance burden

**Effort:** Very High

## Tradeoffs Analysis

| Option | Code Changes | External Dependencies | Latency | Failure Modes | Effort |
|---------|--------------|---------------------|---------|---------------|---------|
| A: Enable JWT Plugin | Minimal | None (JWKS) | Low | Standard | Low |
| B: Frontend SDK JWT | Medium | None (JWKS) | Low | Standard | Medium |
| C: Session Validation | Major | High (API calls) | **High** | **API-dependent** | High |
| D: Hybrid | Very High | Medium | Medium | Mixed | Very High |

## Recommendations

### Immediate (Shortest Path)
**Try Option A first** - Check if JWT plugin can be enabled in Neon Auth configuration. This is the lowest effort path if available.

### Fallback (If Option A unavailable)
**Implement Option B** - Use frontend SDK to retrieve JWT and pass to backend. This maintains our security model with moderate effort.

### Last Resort (If neither A nor B work)
**Implement Option C** - Session token validation. This requires significant architectural changes but aligns with Neon Auth's current default behavior.

## Testing Strategy

### For Option A:
1. Enable JWT plugin in Neon Auth console
2. Re-run JWT exchange test
3. Verify backend compatibility
4. Test full auth flow end-to-end

### For Option B:
1. Update frontend to call `authClient.token()`
2. Modify `/auth/set-auth-cookie` to handle JWT
3. Test session-to-JWT flow
4. Verify backend JWT verification

### For Option C:
1. Implement session validation API calls
2. Replace JWT verification logic
3. Add caching layer
4. Extensive load testing for latency
5. Fallback mechanism design

## Phase 1.5 Impact

**Current Status:** ❌ **BLOCKED**  
**Required Action:** Resolve architectural mismatch before signoff  
**Estimated Resolution Time:** 2-4 hours (depending on option chosen)

## Conclusion

The live verification successfully identified a critical architectural mismatch that mock testing could not catch. This validates the importance of external service verification. The resolution path depends on Neon Auth configuration availability, with Option A being preferred if feasible.

**Next Step:** Check Neon Auth configuration for JWT plugin availability before implementing code changes.