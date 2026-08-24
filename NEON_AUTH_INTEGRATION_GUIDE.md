# Neon Auth Integration Guide

## Overview

This guide explains how the SchoolOP application now properly integrates with Neon Auth according to the official Neon Auth documentation. The authentication flow ensures that accounts are created with proper Neon Auth user IDs, preventing issues with token expiration and authentication failures.

## Key Changes

### 1. Proper Neon Auth SDK Integration

**Before:** The signup flow created platform users without proper Neon Auth integration, using placeholder IDs.

**After:** The signup flow now uses the Neon Auth SDK to create users first, then links them to platform users.

### 2. Two-Step Signup Process

The new signup process follows Neon Auth best practices:

#### Step 1: Neon Auth Signup
```typescript
const { data: neonData, error: neonError } = await authClient.signUp.email({
  email: formData.email,
  password: formData.password,
  name: formData.full_name,
});
```

- Creates user in Neon Auth database (`neon_auth.user` table)
- Stores credentials in `neon_auth.account` table
- Returns a proper Neon Auth user ID
- Sets HTTP-only session cookie automatically

#### Step 2: Platform User Creation
```typescript
const response = await apiFetch('/api/auth/signup', {
  method: 'POST',
  body: JSON.stringify({
    neon_auth_user_id: neonData.user.id, // Real Neon Auth ID
    email: formData.email,
    full_name: formData.full_name,
    school_code: formData.school_code,
    // ... other fields
  })
});
```

- Creates platform user with the actual Neon Auth user ID
- Validates school code and assigns VIEWER role
- Links Neon Auth session to platform user

### 3. Token Management

According to Neon Auth documentation:

**Session Cookie:** 
- HTTP-only cookie `__Secure-neonauth.session_token`
- Contains opaque session token (not JWT)
- Automatically sent with requests to Auth API
- Managed entirely by SDK

**JWT Token:**
- Automatically retrieved by SDK and stored in `session.access_token`
- Contains user ID in `sub` claim
- Used for Data API requests
- Expires in 15 minutes (auto-refreshed by SDK)

**Our Implementation:**
```typescript
export async function getAccessToken(): Promise<string | null> {
  try {
    const result = await authClient.getSession()
    const token = result?.data?.session?.token ?? null

    if (token) {
      localStorage.setItem('auth_token', token) // For compatibility
      return token
    }
  } catch (err) {
    console.error('Failed to read Neon Auth session', err)
  }

  return localStorage.getItem('auth_token') // Fallback
}
```

### 4. Sign-Out Handling

Proper sign-out implementation per Neon Auth docs:

```typescript
export async function signOut() {
  try {
    const { error } = await authClient.signOut();
    if (error) {
      console.error('Sign out error:', error);
      throw error;
    }
    // Clear any local storage auth token as well
    localStorage.removeItem('auth_token');
  } catch (error) {
    console.error('Failed to sign out:', error);
    throw error;
  }
}
```

This ensures:
- Neon Auth session cookie is cleared
- JWT tokens are invalidated
- Local state is cleaned up
- User is redirected to sign-in page

### 5. Account Linking Logic

The `/api/auth/link-account` endpoint now handles three scenarios:

1. **Self-signed up users:** Already have proper `neon_auth_user_id` from signup
2. **Manually created users:** Have placeholder `neon_auth_user_id` (manual-setup-*)
3. **Legacy users:** Need email-based linking

```python
# First try to find by neon_auth_user_id (most efficient)
result = await db.execute(
    select(User).where(User.neon_auth_user_id == neon_sub)
)
user = result.scalar_one_or_none()

if user is None:
    # Fallback to email-based lookup for legacy users
    email = email or body.get("email")
    if email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
```

## Authentication Flow

### Signup Flow
1. User enters email, password, name, and school code
2. Frontend calls `authClient.signUp.email()` with Neon Auth SDK
3. Neon Auth creates user in `neon_auth.user` table
4. Neon Auth returns user ID and sets session cookie
5. Frontend calls `/api/auth/signup` with Neon Auth user ID
6. Backend validates school code and creates platform user
7. Platform user is linked to Neon Auth user ID
8. User is redirected to sign-in page

### Sign-In Flow
1. User enters email and password
2. Frontend calls `authClient.signIn.email()` with Neon Auth SDK
3. Neon Auth validates credentials and creates session
4. SDK automatically retrieves JWT token
5. Frontend makes API requests with JWT in Authorization header
6. Backend validates JWT and extracts user ID from `sub` claim
7. Backend finds platform user by `neon_auth_user_id`
8. User is authenticated and granted access based on roles

### Sign-Out Flow
1. User clicks "Sign Out" button
2. Frontend calls `authClient.signOut()` with Neon Auth SDK
3. Neon Auth clears session cookie and invalidates tokens
4. Frontend clears local storage
5. User is redirected to sign-in page

## Error Handling

### School Code Validation
```python
if not school:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": {
                "code": "INVALID_SCHOOL_CODE",
                "message": "Invalid or inactive school code. Please contact your administrator."
            }
        }
    )
```

### Duplicate User Prevention
```python
existing_user = await db.execute(
    select(User).where(User.email == request.email)
)
if existing_user.scalar_one_or_none():
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": {
                "code": "USER_EXISTS",
                "message": "A user with this email already exists. Please contact your administrator."
            }
        }
    )
```

### Neon Auth Link Validation
```python
existing_neon_user = await db.execute(
    select(User).where(User.neon_auth_user_id == request.neon_auth_user_id)
)
if existing_neon_user.scalar_one_or_none():
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": {
                "code": "NEON_USER_EXISTS",
                "message": "This Neon Auth account is already linked to a platform user."
            }
        }
    )
```

## Security Considerations

1. **Cross-Origin Credentials:** The auth client is configured with `credentials: 'include'` for cross-origin requests from localhost to neon.tech
2. **HTTP-Only Cookies:** Session cookies are HTTP-only and secure, preventing XSS attacks
3. **JWT Validation:** Backend validates JWT signatures using JWKS public keys
4. **Role-Based Access:** Users are created with VIEWER role by default; only SuperAdmin/Admin/DeptHead can upgrade roles
5. **School Code Validation:** Only valid, active school codes are accepted for signup

## Testing the Auth Flow

### Test Signup
1. Navigate to `http://localhost:5173/auth/sign-up`
2. Enter email, password, full name, and school code (TEST001)
3. Submit the form
4. Verify account creation success message
5. Redirect to sign-in page

### Test Sign-In
1. Navigate to `http://localhost:5173/auth/sign-in`
2. Enter the credentials you just created
3. Verify successful authentication
4. Check that you have VIEWER access only
5. Verify user appears in Users list (for admins)

### Test Sign-Out
1. Click the "Sign Out" button in the top right
2. Verify session is cleared
3. Verify redirect to sign-in page
4. Try to access protected routes (should redirect to sign-in)

## Troubleshooting

### CORS Issues
If you get CORS errors, ensure:
- Neon Auth Console has your frontend URL in allowed origins
- Add `http://localhost:5173` and `http://127.0.0.1:5173` to allowed origins

### Token Issues
If tokens don't work:
- Verify `credentials: 'include'` is set in auth client config
- Check that NEON_AUTH_COOKIE_SECRET matches between frontend and backend
- Clear browser cookies and local storage

### School Code Issues
If school code validation fails:
- Verify school exists in database
- Check school status is 'active'
- Use test school code: TEST001

## References

- [Neon Auth Authentication Flow](https://neon.com/docs/auth/authentication-flow)
- [Neon Auth JavaScript SDK](https://neon.com/docs/reference/javascript-sdk)
- [Neon Auth JWT Plugin](https://neon.com/docs/auth/guides/plugins/jwt)
- [Neon Auth Overview](https://neon.com/docs/auth/overview)

## Conclusion

This implementation follows Neon Auth best practices and ensures:
- ✅ Proper user account creation with valid Neon Auth IDs
- ✅ Secure token management with automatic refresh
- ✅ Proper sign-out handling that clears all sessions
- ✅ School ID validation for signup restrictions
- ✅ Role-based access control with VIEWER default
- ✅ Error handling for all authentication scenarios
