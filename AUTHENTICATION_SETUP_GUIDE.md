# Authentication Setup Guide

## Problem
The frontend is returning "Failed to fetch" errors because the Neon Auth authentication is not properly configured. The backend requires valid JWT tokens from Neon Auth.

## Solution Steps

### 1. Configure Neon Auth Environment Variables

Add these to your `.env` file:

```bash
# Neon Auth Configuration
NEON_AUTH_BASE_URL=https://your-neon-project.neon.tech/auth
NEON_AUTH_COOKIE_SECRET=your-secret-key-from-neon-auth

# For development, you can generate a secret:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Configure Frontend Environment

Add to `frontend/.env`:

```bash
VITE_NEON_AUTH_URL=https://your-neon-project.neon.tech/auth
```

### 3. Ensure User is Provisioned in Database

The user must exist in the `users` table with proper `neon_auth_user_id` mapping.

Run the superadmin creation script if needed:

```bash
python create_superadmin.py
```

### 4. Update User's Neon Auth ID

After signing up/signing in through Neon Auth, update the user's `neon_auth_user_id` in the database to match the Neon Auth user ID.

### 5. Test Authentication Flow

1. Sign in through the frontend at `http://localhost:5173/auth`
2. The Neon Auth session will be established
3. The frontend will send JWT tokens via `apiFetch`
4. The backend will verify tokens using JWKS from Neon Auth

## Development Mode Alternative

For development without Neon Auth, you can create a simple token generator:

```python
# dev_token_generator.py
import jwt
import os
from datetime import datetime, timedelta

SECRET = os.getenv("NEON_AUTH_COOKIE_SECRET", "dev-secret-key")

def create_dev_token():
    payload = {
        "sub": "dd9c0ea1-04a7-49cf-b779-056f15365507",  # Your user ID
        "email": "lakshay.kumar@pw.live",
        "roles": ["superadmin"],
        "school_id": None,
        "department_id": None,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

if __name__ == "__main__":
    token = create_dev_token()
    print(f"Bearer {token}")
```

Use this token in your frontend `localStorage` for testing:
```javascript
localStorage.setItem('auth_token', 'YOUR_DEV_TOKEN_HERE')
```

## Key Files to Check

- `shared/auth.py` - Token verification logic
- `shared/middleware/tenancy.py` - Tenant context extraction
- `api/auth.py` - Authentication endpoints
- `frontend/src/lib/auth.ts` - Frontend auth client
- `frontend/src/lib/api.ts` - API fetch with auth headers
