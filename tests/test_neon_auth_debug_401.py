"""
Debug 401 on /token and null on /get-session
Investigate auth context and cookie handling
"""
import os
import json
import httpx

os.environ["NEON_AUTH_BASE_URL"] = "https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth"
os.environ["NEON_AUTH_COOKIE_SECRET"] = "63lhEmBliLeAD5YKTLQ8F/y2ZDoxM1NKYSBjYPNK1zA="

NEON_AUTH_BASE_URL = os.environ["NEON_AUTH_BASE_URL"]
NEON_AUTH_COOKIE_SECRET = os.environ["NEON_AUTH_COOKIE_SECRET"]

print("=" * 80)
print("DEBUG 401/NULL RESPONSES")
print("=" * 80)

# Step 1: Login and capture exact response structure
print("STEP 1: Analyze login response structure")
print("-" * 80)

login_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/sign-in/email"
login_payload = {
    "email": "lakshay.kumar@pw.live",
    "password": "Laksh_2005"
}

response = httpx.post(login_url, json=login_payload, timeout=10)
print(f"Login status: {response.status_code}")

if response.status_code == 200:
    login_data = response.json()
    print(f"Full login response: {json.dumps(login_data, indent=2)}")
    
    session_token = login_data.get('token')
    user_id = login_data.get('user', {}).get('id')
    
    print(f"\nSession token: {session_token}")
    print(f"User ID: {user_id}")
else:
    print(f"Login failed: {response.text}")
    exit(1)

print()

# Step 2: Test /token with detailed auth context debugging
print("STEP 2: Debug /token endpoint with different auth methods")
print("-" * 80)

token_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/token"

# Method 1: Bearer token with session token
print("Method 1: Bearer header with session token")
headers = {"Authorization": f"Bearer {session_token}"}
response = httpx.get(token_url, headers=headers, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:300]}")
print(f"Headers sent: {headers}")

print()

# Method 2: Cookie with expected Neon Auth cookie name
print("Method 2: Cookie with Neon Auth session cookie name")
cookies = {"__Secure-neonauth.session_token": session_token}
response = httpx.get(token_url, cookies=cookies, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:300]}")
print(f"Cookies sent: {cookies}")

print()

# Method 3: Cookie with custom name (our current approach)
print("Method 3: Cookie with custom name (our current approach)")
cookies = {"auth_token": session_token}
response = httpx.get(token_url, cookies=cookies, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:300]}")
print(f"Cookies sent: {cookies}")

print()

# Method 4: Both Bearer and Cookie
print("Method 4: Both Bearer header and Cookie")
headers = {"Authorization": f"Bearer {session_token}"}
cookies = {"__Secure-neonauth.session_token": session_token}
response = httpx.get(token_url, headers=headers, cookies=cookies, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:300]}")

print()

# Method 5: Try with NEON_AUTH_COOKIE_SECRET as Bearer
print("Method 5: Bearer with NEON_AUTH_COOKIE_SECRET (server-to-server)")
headers = {"Authorization": f"Bearer {NEON_AUTH_COOKIE_SECRET}"}
response = httpx.get(token_url, headers=headers, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:300]}")

print()

# Step 3: Debug /get-session endpoint
print("STEP 3: Debug /get-session endpoint")
print("-" * 80)

session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"

print("Method 1: Bearer with session token")
headers = {"Authorization": f"Bearer {session_token}"}
response = httpx.get(session_url, headers=headers, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:300]}")

print()

print("Method 2: Cookie with Neon Auth session cookie name")
cookies = {"__Secure-neonauth.session_token": session_token}
response = httpx.get(session_url, cookies=cookies, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:300]}")

print()

print("Method 3: No auth (anonymous)")
response = httpx.get(session_url, timeout=10)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:300]}")

print()

# Step 4: Try different endpoint variations
print("STEP 4: Try endpoint variations")
print("-" * 80)

variations = [
    "/auth/token",
    "/auth/session/token", 
    "/v1/token",
    "/api/token",
    "/jwt",
    "/auth/jwt"
]

for variation in variations:
    try:
        url = f"{NEON_AUTH_BASE_URL.rstrip('/')}{variation}"
        headers = {"Authorization": f"Bearer {session_token}"}
        response = httpx.get(url, headers=headers, timeout=5)
        print(f"{variation}: {response.status_code}")
        if response.status_code != 404:
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"{variation}: Error - {str(e)}")

print()

# Step 5: Check if there's a configuration or info endpoint
print("STEP 5: Check for configuration/info endpoints")
print("-" * 80)

info_endpoints = [
    "/.well-known/openid-configuration",
    "/.well-known/oauth-authorization-server",
    "/auth/config",
    "/config",
    "/health",
    "/info"
]

for endpoint in info_endpoints:
    try:
        url = f"{NEON_AUTH_BASE_URL.rstrip('/')}{endpoint}"
        response = httpx.get(url, timeout=5)
        print(f"{endpoint}: {response.status_code}")
        if response.status_code == 200:
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"{endpoint}: Error - {str(e)}")

print()
print("=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)