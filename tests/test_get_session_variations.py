"""
Test variations of /get-session calls to understand why it returns null
"""
import os
import httpx
import json

os.environ["NEON_AUTH_BASE_URL"] = "https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth"
os.environ["NEON_AUTH_COOKIE_SECRET"] = "63lhEmBliLeAD5YKTLQ8F/y2ZDoxM1NKYSBjYPNK1zA="

NEON_AUTH_BASE_URL = os.environ["NEON_AUTH_BASE_URL"]
NEON_AUTH_COOKIE_SECRET = os.environ["NEON_AUTH_COOKIE_SECRET"]

print("=" * 80)
print("GET-SESSION VARIATIONS TEST")
print("=" * 80)

# First, get a real session token
print("STEP 0: Get Session Token")
print("-" * 80)

login_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/sign-in/email"
login_payload = {
    "email": "lakshay.kumar@pw.live",
    "password": "Laksh_2005"
}

response = httpx.post(login_url, json=login_payload, timeout=10)
session_token = response.json().get('token')
print(f"Session token: {session_token[:20]}...{session_token[-10:]}")
print()

# Variation 1: Cookie only (no Authorization header)
print("VARIATION 1: Cookie only (no Authorization header)")
print("-" * 80)

try:
    get_session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    
    headers = {
        "Cookie": f"__Secure-neonauth.session_token={session_token}"
    }
    
    response = httpx.get(get_session_url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    print()
except Exception as e:
    print(f"Error: {str(e)}")
    print()

# Variation 2: Authorization header only (no cookie)
print("VARIATION 2: Authorization header only (no cookie)")
print("-" * 80)

try:
    get_session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    
    headers = {
        "Authorization": f"Bearer {NEON_AUTH_COOKIE_SECRET}"
    }
    
    response = httpx.get(get_session_url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    print()
except Exception as e:
    print(f"Error: {str(e)}")
    print()

# Variation 3: Both Authorization and Cookie (current implementation)
print("VARIATION 3: Both Authorization and Cookie (current implementation)")
print("-" * 80)

try:
    get_session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    
    headers = {
        "Authorization": f"Bearer {NEON_AUTH_COOKIE_SECRET}",
        "Cookie": f"__Secure-neonauth.session_token={session_token}"
    }
    
    response = httpx.get(get_session_url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    print()
except Exception as e:
    print(f"Error: {str(e)}")
    print()

# Variation 4: Cookie with different name
print("VARIATION 4: Cookie with different name (session_token)")
print("-" * 80)

try:
    get_session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    
    headers = {
        "Authorization": f"Bearer {NEON_AUTH_COOKIE_SECRET}",
        "Cookie": f"session_token={session_token}"
    }
    
    response = httpx.get(get_session_url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    print()
except Exception as e:
    print(f"Error: {str(e)}")
    print()

# Variation 5: Try POST instead of GET
print("VARIATION 5: POST instead of GET")
print("-" * 80)

try:
    get_session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    
    headers = {
        "Authorization": f"Bearer {NEON_AUTH_COOKIE_SECRET}",
        "Cookie": f"__Secure-neonauth.session_token={session_token}",
        "Content-Type": "application/json"
    }
    
    response = httpx.post(get_session_url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    print()
except Exception as e:
    print(f"Error: {str(e)}")
    print()

# Variation 6: Try with session token in Authorization header instead
print("VARIATION 6: Session token in Authorization header")
print("-" * 80)

try:
    get_session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    
    headers = {
        "Authorization": f"Bearer {session_token}",
        "Cookie": f"__Secure-neonauth.session_token={session_token}"
    }
    
    response = httpx.get(get_session_url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    print()
except Exception as e:
    print(f"Error: {str(e)}")
    print()

# Variation 7: Try without any auth (what browser might do)
print("VARIATION 7: No auth headers (just cookie)")
print("-" * 80)

try:
    get_session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    
    headers = {
        "Cookie": f"__Secure-neonauth.session_token={session_token}"
    }
    
    response = httpx.get(get_session_url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    print()
except Exception as e:
    print(f"Error: {str(e)}")
    print()

print("=" * 80)
print("VARIATIONS TEST COMPLETE")
print("=" * 80)
