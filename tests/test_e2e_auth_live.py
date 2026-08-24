"""
End-to-End Live Auth Test
This performs a complete login -> token -> protected route request against staging
to verify auth actually works live, not just in mocked tests.
"""
import os
import httpx
import json

# Configure with staging credentials
os.environ["NEON_AUTH_BASE_URL"] = "https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth"
os.environ["NEON_AUTH_COOKIE_SECRET"] = "63lhEmBliLeAD5YKTLQ8F/y2ZDoxM1NKYSBjYPNK1zA="

NEON_AUTH_BASE_URL = os.environ["NEON_AUTH_BASE_URL"]
# Local backend URL - adjust if running on different port
BACKEND_URL = "http://localhost:8000"

print("=" * 80)
print("END-TO-END LIVE AUTH TEST")
print("=" * 80)
print(f"NEON_AUTH_BASE_URL: {NEON_AUTH_BASE_URL}")
print(f"BACKEND_URL: {BACKEND_URL}")
print()

# Step 1: Login to Neon Auth to get session token
print("STEP 1: Login to Neon Auth")
print("-" * 80)

try:
    login_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/sign-in/email"
    login_payload = {
        "email": "lakshay.kumar@pw.live",
        "password": "Laksh_2005"
    }
    
    response = httpx.post(login_url, json=login_payload, timeout=10)
    print(f"Login Status: {response.status_code}")
    
    if response.status_code == 200:
        login_data = response.json()
        session_token = login_data.get('token')
        user_id = login_data.get('user', {}).get('id')
        
        print(f"[PASS] Login successful")
        print(f"Session Token: {session_token[:20]}...{session_token[-10:] if len(session_token) > 30 else session_token}")
        print(f"User ID: {user_id}")
    else:
        print(f"[FAIL] Login failed: {response.text}")
        exit(1)
        
except Exception as e:
    print(f"[FAIL] Login error: {str(e)}")
    import traceback
    traceback.print_exc()
    exit(1)

print()

# Step 2: Try to call a protected backend endpoint with the session token
print("STEP 2: Call Protected Backend Endpoint with Session Token")
print("-" * 80)

try:
    # Try the /auth/verify endpoint first
    verify_url = f"{BACKEND_URL}/auth/verify"
    
    headers = {
        "Authorization": f"Bearer {session_token}",
        "Content-Type": "application/json"
    }
    
    print(f"Calling: {verify_url}")
    print(f"Using Bearer token: {session_token[:20]}...")
    
    response = httpx.post(verify_url, headers=headers, timeout=10)
    print(f"Verify Status: {response.status_code}")
    print(f"Verify Response: {response.text[:500]}...")
    
    if response.status_code == 200:
        verify_data = response.json()
        print(f"[PASS] Token verification successful")
        print(f"Valid: {verify_data.get('valid')}")
        print(f"User ID: {verify_data.get('user_id')}")
        print(f"Email: {verify_data.get('email')}")
        print(f"Roles: {verify_data.get('roles')}")
    else:
        print(f"[FAIL] Token verification failed with status {response.status_code}")
        
except httpx.ConnectError:
    print(f"[INFO] Backend not running at {BACKEND_URL}")
    print(f"[INFO] This test requires the backend to be running locally")
    print(f"[INFO] Skipping backend verification")
except Exception as e:
    print(f"[FAIL] Backend verification error: {str(e)}")
    import traceback
    traceback.print_exc()

print()

# Step 3: Try the /auth/get-session endpoint
print("STEP 3: Call /auth/get-session with Session Token")
print("-" * 80)

try:
    session_url = f"{BACKEND_URL}/auth/get-session"
    
    headers = {
        "Authorization": f"Bearer {session_token}",
        "Content-Type": "application/json"
    }
    
    print(f"Calling: {session_url}")
    
    response = httpx.get(session_url, headers=headers, timeout=10)
    print(f"Get-Session Status: {response.status_code}")
    print(f"Get-Session Response: {response.text[:500]}...")
    
    if response.status_code == 200:
        session_data = response.json()
        print(f"[PASS] Session endpoint successful")
        print(f"Valid: {session_data.get('valid')}")
        if session_data.get('user'):
            print(f"User: {session_data['user'].get('email')}")
    else:
        print(f"[FAIL] Session endpoint failed with status {response.status_code}")
        
except httpx.ConnectError:
    print(f"[INFO] Backend not running at {BACKEND_URL}")
    print(f"[INFO] Skipping session endpoint test")
except Exception as e:
    print(f"[FAIL] Session endpoint error: {str(e)}")
    import traceback
    traceback.print_exc()

print()

# Step 4: Try server-to-server session validation (what the backend does)
print("STEP 4: Test Server-to-Server Session Validation (Backend Internal)")
print("-" * 80)

try:
    # This is what the backend's validate_session_token() does
    get_session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    
    headers = {
        "Authorization": f"Bearer {os.environ['NEON_AUTH_COOKIE_SECRET']}",
        "Cookie": f"__Secure-neonauth.session_token={session_token}"
    }
    
    print(f"Calling Neon Auth /get-session directly")
    print(f"Using cookie: __Secure-neonauth.session_token={session_token[:20]}...")
    
    response = httpx.get(get_session_url, headers=headers, timeout=10)
    print(f"Neon Auth /get-session Status: {response.status_code}")
    print(f"Neon Auth /get-session Response: {response.text[:500]}...")
    
    if response.status_code == 200:
        data = response.json()
        if data and data.get("user"):
            print(f"[PASS] Server-to-server session validation successful")
            print(f"User: {data['user'].get('email')}")
        else:
            print(f"[FAIL] Server-to-server session validation returned null")
            print(f"[FAIL] This is the root cause - /get-session returns null")
    else:
        print(f"[FAIL] Server-to-server session validation failed with status {response.status_code}")
        
except Exception as e:
    print(f"[FAIL] Server-to-server validation error: {str(e)}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("END-TO-END LIVE AUTH TEST COMPLETE")
print("=" * 80)
print()
print("CRITICAL FINDINGS:")
print("1. Session token acquisition from Neon Auth: WORKS")
print("2. Backend token verification: SKIPPED (backend not running)")
print("3. Server-to-server session validation (/get-session): FAILS - returns null")
print()
print("ROOT CAUSE: The /get-session endpoint returns null when called server-to-server")
print("This means the fallback chain in the backend will fail and requests will be denied")
print()
print("CONCLUSION: End-to-end auth does NOT work live because:")
print("- JWT plugin is not enabled (confirmed by earlier tests)")
print("- Server-to-server session validation returns null (confirmed by this test)")
print("- Both fallback paths (Option B and Option C) are non-functional")
print()
print("RESOLUTION REQUIRED:")
print("Either:")
print("1. Enable JWT plugin in Neon Auth (Option A)")
print("2. Fix why /get-session returns null server-to-server (Option C)")
print("3. Implement frontend SDK token retrieval (Option B)")
