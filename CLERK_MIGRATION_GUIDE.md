# Clerk Migration Guide

This guide explains the migration from Neon Auth to Clerk authentication.

## Environment Configuration

### Backend (.env)
Update your backend environment variables:
```bash
# Auth — Clerk
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_cG9wdWxhci1zcGFuaWVsLTU2NjAuY2xlcmsuYWNjb3VudHMuZGV2JA
CLERK_SECRET_KEY=sk_test_3Vl885kbImIyNuBUqNaw7etRpqn2JOG8zRFpYmxtfk
CLERK_JWKS_URL=https://popular-spaniel-5660.clerk.accounts.dev/.well-known/jwks.json
MFA_REQUIRED_ROLES=Admin,SuperAdmin
SESSION_TIMEOUT_MINUTES=30
```

### Frontend (frontend/.env)
Update your frontend environment variables:
```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_cG9wdWxhci1zcGFuaWVsLTU2NjAuY2xlcmsuYWNjb3VudHMuZGV2JA
VITE_CLERK_DOMAIN=popular-spaniel-5660.clerk.accounts.dev
```

## Database Migration

Run the migration to rename `neon_auth_user_id` to `clerk_user_id`:
```bash
alembic upgrade head
```

## Frontend Changes

### Dependencies Removed
- `@neondatabase/auth`
- `@neondatabase/neon-js`

### Dependencies Added
- `@clerk/clerk-react`

### Key Changes
1. **Auth Provider**: Replaced `NeonAuthUIProvider` with `ClerkProvider`
2. **Auth Hooks**: Updated to use Clerk's `useAuth` hook
3. **Components**: Replaced Neon Auth components with Clerk components:
   - `SignInButton`, `SignUpButton` for authentication
   - `UserButton` for user account management
4. **Token Retrieval**: Updated to use Clerk's `getToken()` method

## Backend Changes

### JWKS Configuration
- Updated JWKS endpoint to use Clerk's JWKS URL
- Supported algorithms: RS256, ES256 (Clerk default), HS256 (fallback)

### Token Structure
Clerk JWTs use the following claims:
- `sub`: User ID (Clerk user ID)
- `email`: User email
- `exp`: Expiration timestamp
- Standard JWT claims

### Session Token Removal
Removed session token fallback - Clerk only uses JWTs.

## Testing

### Integration Tests
Run the Clerk integration tests:
```bash
pytest tests/test_clerk_integration.py -v
```

### Manual Testing
1. Start the backend server
2. Start the frontend development server
3. Sign up a new user via Clerk
4. Complete the account setup with school code
5. Verify JWT token is issued and backend accepts it

## Migration Notes

### User Data Migration
Existing users with `neon_auth_user_id` will have this field renamed to `clerk_user_id` automatically via the migration.

### Token Verification
The backend JWT verification logic is preserved - only the JWKS endpoint and supported algorithms changed.

### Security
- All security features (rate limiting, MFA, cookie security) remain intact
- Clerk provides enhanced security with built-in session management
- httpOnly cookies continue to be used for enhanced security

## Next Steps

1. Update your environment files with the provided Clerk credentials
2. Run the database migration
3. Install frontend dependencies: `cd frontend && npm install`
4. Run the integration tests
5. Perform manual end-to-end testing
6. Deploy to staging environment for verification
7. Update production environment variables
8. Deploy to production

## Rollback Plan

If needed, you can rollback the migration:
```bash
alembic downgrade -1
```

This will revert the database column name back to `neon_auth_user_id`.
