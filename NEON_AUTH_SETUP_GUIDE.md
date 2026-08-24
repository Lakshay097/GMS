# Neon Auth Setup Guide

## Project Structure
- **Project ID**: `wandering-band-34970686`
- **Branch**: `br-plain-mode-axsxspuv`
- **Auth Console**: https://console.neon.tech/app/projects/wandering-band-34970686/branches/br-plain-mode-axsxspuv/auth
- **Auth URL**: `https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth`

**Important**: "restless-moon" in the auth URL is the Neon compute instance/region name, not a separate project. Your single project `wandering-band-34970686` is hosted on the `restless-moon` Neon infrastructure.

## Problem
You're getting a 401 error when trying to sign up because Neon Auth is not properly configured for your project.

## Solution: Enable Neon Auth in Neon Console

### Step 1: Go to Neon Console
1. Log in to https://console.neon.tech
2. Navigate to: https://console.neon.tech/app/projects/wandering-band-34970686/branches/br-plain-mode-axsxspuv/auth
3. Verify that Auth is enabled for your branch

### Step 2: Enable Auth (if not enabled)
1. Click on the **Auth** tab in your project dashboard
2. Click **Enable Auth** or **Set up Auth**
3. Follow the setup wizard

### Step 3: Verify Auth URL
After enabling Auth, verify the auth URL shown in the Neon Console matches:
```
https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth
```

### Step 4: Verify Your Environment Files

**Frontend (`D:\SchoolOP\frontend\.env`):**
```env
VITE_NEON_AUTH_URL=https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth
```
✅ This is correct - "restless-moon" is the Neon compute instance, not a separate project

**Backend (`D:\SchoolOP\.env`):**
```env
NEON_AUTH_BASE_URL=https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth
NEON_AUTH_COOKIE_SECRET=1A8AC085B4F091359B172715134208AE54179A6CB43EA9264F45FB608DC2D601
```
❌ Add `NEON_AUTH_BASE_URL` to backend config

### Step 5: Restart Your Development Servers
1. Stop the frontend dev server (Ctrl+C)
2. Stop the backend dev server (Ctrl+C)
3. Restart both servers

### Step 6: Test Sign-Up
1. Navigate to `http://localhost:5173/auth/sign-up`
2. Try to sign up with a new email and password
3. It should work now that Auth is enabled

## Verification

### Test the Auth Endpoint
```bash
curl https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth
```

If it returns JSON data instead of 404, the Auth service is running.

### Check Project Configuration
1. In Neon Console, verify that Auth is enabled for the `br-plain-mode-axsxspuv` branch
2. Check that the auth endpoint is accessible from your application
3. Verify the auth URL format matches what Neon Console shows

## Additional Configuration

You may also need to configure:
- **Email verification** (optional but recommended)
- **Password requirements** (in Neon Console)
- **Session settings** (timeout, etc.)

## Troubleshooting

### Still getting 401 errors?
- Check that the Auth URL is exactly correct (no typos)
- Make sure Auth is actually enabled in Neon Console
- Clear browser cache and cookies
- Check browser console for detailed error messages

### Sign-up shows sign-in form?
- This is normal behavior in some Auth configurations
- Try clicking "Sign up" link in the AuthView component
- Check if email verification is required (you might need to verify email first)

## Current Configuration Status

✅ Frontend has `VITE_NEON_AUTH_URL` set (correct Neon compute instance URL)
✅ Backend has `NEON_AUTH_COOKIE_SECRET` set  
❌ Backend missing `NEON_AUTH_BASE_URL` (needs to be added)
❓ Auth service needs to be enabled in Neon Console
❓ Auth service availability needs testing

## Understanding the 404 Response

The 404 from the base auth URL is **expected** - it's an API endpoint, not a webpage. The endpoint expects specific routes like `/sign-in/email`, `/sign-up/email`, etc., not a bare GET request.

## ✅ Configuration Status

Both frontend and backend configurations are **complete and correct**:

**Frontend (`D:\SchoolOP\frontend\.env`):**
```env
VITE_NEON_AUTH_URL=https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth
NEON_AUTH_COOKIE_SECRET=63lhEmBliLeAD5YKTLQ8F/y2ZDoxM1NKYSBjYPNK1zA=
```

**Backend (`D:\SchoolOP\.env`):**
```env
NEON_AUTH_BASE_URL=https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth
NEON_AUTH_COOKIE_SECRET=63lhEmBliLeAD5YKTLQ8F/y2ZDoxM1NKYSBjYPNK1zA=
```

## 🔍 Real Issue Found: CORS Configuration

Testing the Neon Auth endpoints directly revealed:

**Sign-up endpoint:**
```json
{"code":"MISSING_ORIGIN","message":"Origin header is required when callbackURL is not an absolute URL"}
```

**Sign-in endpoint:**
```json
{"code":"MISSING_OR_NULL_ORIGIN","message":"Missing or null Origin"}
```

The Neon Auth service **is working correctly** (no 404 errors), but it's rejecting requests due to **CORS (Cross-Origin Resource Sharing) configuration**. The service requires proper Origin headers to allow requests from your frontend application.

## Solution: Configure CORS in Neon Console

### Step 1: Go to Neon Console Auth Settings
1. Navigate to: https://console.neon.tech/app/projects/wandering-band-34970686/branches/br-plain-mode-axsxspuv/auth
2. Look for **CORS settings** or **Allowed origins**
3. Add your frontend URL to the allowed origins

### Step 2: Add Allowed Origins
Add these URLs to the Neon Auth CORS configuration:

```
http://localhost:5173
http://localhost:3000
http://127.0.0.1:5173
http://127.0.0.1:3000
```

If you have a production domain, add that as well:
```
https://your-production-domain.com
```

### Step 3: Save Configuration
Save the CORS settings in the Neon Console.

### Step 4: Restart Frontend
After updating CORS settings:
1. Stop the frontend dev server (Ctrl+C)
2. Restart the frontend server
3. Navigate to `http://localhost:5173/auth/sign-up`
4. Try to sign up again

## Verification

After configuring CORS, the sign-up should work because:
- ✅ Neon Auth service is running correctly
- ✅ Frontend and backend have correct configuration
- ✅ CORS will allow requests from your localhost development server
- ✅ The Neon Auth SDK will handle the required Origin headers automatically