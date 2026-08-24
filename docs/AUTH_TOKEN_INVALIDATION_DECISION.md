# Auth Token Invalidation Decision

## Current Architecture Analysis

The current authentication architecture uses **stateless JWT tokens** issued by Neon Auth:

1. **Token Issuance**: Neon Auth (external service) issues JWT tokens
2. **Token Verification**: Backend verifies JWT signatures using JWKS (Neon Auth's public keys)
3. **Token Storage**: No token state is stored in the backend (stateless)
4. **Session Management**: JWT expiration times handle session lifecycle
5. **Logout**: Currently handled by Neon Auth on the frontend (clears client-side tokens)

## Token Invalidation Options

### Option 1: Backend Token Blacklist (Redis)
- Store invalidated tokens in Redis
- Check blacklist on each request
- **Pros**: Immediate invalidation
- **Cons**: 
  - Requires Redis infrastructure
  - Breaks stateless JWT pattern
  - Adds latency to every request
  - Not consistent with current architecture

### Option 2: Short-lived JWTs with Refresh Tokens
- Use short access tokens (e.g., 15 minutes)
- Use refresh tokens for session continuity
- Invalidate refresh tokens on logout
- **Pros**: Standard OAuth2 pattern
- **Cons**: 
  - Requires token state management
  - Changes authentication flow significantly
  - Requires Neon Auth changes
  - Not consistent with current architecture

### Option 3: Maintain Current Approach (Stateless JWTs)
- Continue using stateless JWTs from Neon Auth
- Handle invalidation on frontend (current approach)
- Rely on JWT expiration for security
- **Pros**: 
  - Consistent with current architecture
  - No infrastructure changes needed
  - No additional latency
  - Stateless and scalable
- **Cons**: 
  - No immediate backend invalidation
  - Tokens remain valid until expiration

## Decision

**Maintain the current stateless JWT approach.**

### Rationale

1. **Architecture Consistency**: The current architecture is designed around stateless JWTs issued by Neon Auth. Adding backend token invalidation would break this pattern.

2. **No Infrastructure Overhead**: Adding Redis for token blacklisting would introduce infrastructure complexity and operational overhead without corresponding benefit.

3. **Existing Security Model**: The current security model relies on:
   - Short JWT expiration times (configurable via SESSION_TIMEOUT_MINUTES)
   - Neon Auth's security controls
   - Client-side token management

4. **Frontend Control**: Neon Auth handles token lifecycle on the frontend, which is the appropriate place for client-side session management.

5. **Audit Requirements**: The audit explicitly states: "Implement token invalidation only if it is consistent with the existing authentication architecture" and "Do not introduce Redis unless the current architecture genuinely requires distributed token state."

### Tradeoffs

**Accepted Tradeoffs:**
- Tokens cannot be immediately invalidated on the backend
- Relies on JWT expiration times for session termination
- Frontend must handle token clearing on logout

**Security Mitigations:**
- Short session timeout (default 30 minutes, configurable)
- Neon Auth's built-in security controls
- Proper frontend token management
- HTTPS for token transmission (data in transit per R-57)

### Recommendations

1. **Keep Session Timeout Short**: Ensure SESSION_TIMEOUT_MINUTES is set appropriately (default 30 minutes is reasonable).

2. **Frontend Token Management**: Ensure frontend properly clears tokens on logout and handles token expiration.

3. **Monitor Token Expiration**: Consider adding monitoring for failed token verifications to detect potential issues.

4. **Document Architecture**: Ensure the stateless JWT architecture is well-documented for future reference.

5. **Future Consideration**: If immediate backend invalidation becomes a critical requirement, reconsider the authentication architecture to support token state management (e.g., refresh tokens, blacklisting).

## Conclusion

The current stateless JWT architecture with Neon Auth is appropriate for the application's needs. Backend token invalidation would introduce complexity without proportional security benefit and would be inconsistent with the existing design.

**No implementation changes required for Phase 6.**
