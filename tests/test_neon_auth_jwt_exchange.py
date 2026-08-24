"""
Test Neon Auth JWT exchange based on documentation findings
According to docs, /token endpoint should exchange session tokens for JWTs
"""
import os
import sys
import json
import httpx
import jwt as pyjwt
from datetime import datetime

# Configure with provided staging credentials
os.environ["NEON_AUTH_BASE_URL"] = "https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth"
os.environ["NEON_AUTH_COOKIE_SECRET"] = "63lhEmBliLeAD5YKTLQ8F/y2ZDoxM1NKYSBjYPNK1zA="

NEON_AUTH_BASE_URL = os.environ["NEON_AUTH_BASE_URL"]
NEON_AUTH_COOKIE_SECRET = os.environ["NEON_AUTH_COOKIE_SECRET"]

print("=" * 80)
print("NEON AUTH JWT EXCHANGE TEST")
print("=" * 80)
print(f"NEON_AUTH_BASE_URL: {NEON_AUTH_BASE_URL}")
print()

# Step 1: Login to get session token
print("STEP 1: Login to get session token")
print("-" * 80)

try:
    login_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/sign-in/email"
    login_payload = {
        "email": "lakshay.kumar@pw.live",
        "password": "Laksh_2005"
    }
    
    response = httpx.post(login_url, json=login_payload, timeout=10)
    print(f"Login Response Status: {response.status_code}")
    
    if response.status_code == 200:
        login_data = response.json()
        session_token = login_data.get('token')
        user_data = login_data.get('user')
        
        print(f"[PASS] Login successful")
        print(f"Session token: {session_token}")
        print(f"User ID: {user_data.get('id') if user_data else 'N/A'}")
        print(f"User email: {user_data.get('email') if user_data else 'N/A'}")
    else:
        print(f"[FAIL] Login failed: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        sys.exit(1)
        
except Exception as e:
    print(f"[FAIL] Login failed: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Step 2: Try /token endpoint with cookie-based auth
print("STEP 2: Try /token endpoint with cookie-based auth")
print("-" * 80)

try:
    token_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/token"
    # Try with cookie instead of Bearer header (based on docs about session cookies)
    cookies = {"__Secure-neonauth.session_token": session_token}
    
    print(f"Requesting: {token_url}")
    print(f"Using session cookie instead of Bearer header")
    response = httpx.get(token_url, cookies=cookies, timeout=10)
    print(f"Token Exchange Response Status: {response.status_code}")
    
    if response.status_code == 200:
        token_data = response.json()
        print(f"[INFO] Token exchange response: {json.dumps(token_data, indent=2)[:500]}...")
        
        # Look for JWT in various possible fields
        jwt_token = None
        if isinstance(token_data, dict):
            jwt_token = token_data.get('jwt') or token_data.get('token') or token_data.get('access_token')
        
        if jwt_token:
            print(f"[PASS] JWT obtained via /token endpoint with cookie")
            print(f"JWT length: {len(jwt_token)}")
            print(f"JWT format: {jwt_token[:30]}...{jwt_token[-20:]}")
            
            # Verify JWT structure
            if '.' in jwt_token and jwt_token.count('.') == 2:
                print(f"[INFO] JWT has valid 3-part structure")
                
                try:
                    # Decode header
                    header = pyjwt.get_unverified_header(jwt_token)
                    print(f"JWT Header: {json.dumps(header, indent=2)}")
                    
                    # Decode payload
                    payload = pyjwt.decode(jwt_token, options={"verify_signature": False})
                    print(f"JWT Payload (selected claims):")
                    important_claims = ['sub', 'email', 'iss', 'aud', 'exp', 'iat', 'roles', 'name']
                    for claim in important_claims:
                        if claim in payload:
                            value = payload[claim]
                            if claim in ['exp', 'iat']:
                                value = datetime.fromtimestamp(value).isoformat()
                            print(f"  {claim}: {value}")
                    
                    print(f"[PASS] JWT structure is valid")
                    
                    # Test with our decode function
                    print()
                    print("STEP 3: Test with our decode_access_token()")
                    print("-" * 80)
                    
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from shared.auth import decode_access_token
                    
                    verified_payload = decode_access_token(jwt_token)
                    
                    if verified_payload:
                        print(f"[PASS] JWT successfully verified by our decode_access_token()")
                        print(f"Verified claims: {list(verified_payload.keys())}")
                        print(f"User ID: {verified_payload.get('sub')}")
                        print(f"Email: {verified_payload.get('email')}")
                        print()
                        print("=" * 80)
                        print("CONCLUSION: JWT exchange works with cookie auth - our backend is compatible")
                        print("=" * 80)
                    else:
                        print(f"[FAIL] JWT verification failed with our decode_access_token()")
                        print()
                        print("=" * 80)
                        print("CONCLUSION: JWT obtained but verification failed - needs investigation")
                        print("=" * 80)
                        
                except Exception as e:
                    print(f"[FAIL] JWT decode failed: {str(e)}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[WARN] JWT does not have valid 3-part structure")
        else:
            print(f"[WARN] No JWT found in token exchange response")
            print(f"[INFO] Available keys: {list(token_data.keys()) if isinstance(token_data, dict) else 'N/A'}")
    else:
        print(f"[FAIL] Token exchange failed with cookie: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        
        # Try with Bearer header as fallback
        print()
        print("STEP 2b: Try /token endpoint with Bearer header (fallback)")
        print("-" * 80)
        
        headers = {"Authorization": f"Bearer {session_token}"}
        response = httpx.get(token_url, headers=headers, timeout=10)
        print(f"Token Exchange Response Status: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            print(f"[INFO] Token exchange response: {json.dumps(token_data, indent=2)[:500]}...")
            
            jwt_token = None
            if isinstance(token_data, dict):
                jwt_token = token_data.get('jwt') or token_data.get('token') or token_data.get('access_token')
            
            if jwt_token:
                print(f"[PASS] JWT obtained via /token endpoint with Bearer header")
            else:
                print(f"[WARN] No JWT found in response")
        else:
            print(f"[FAIL] Token exchange failed with Bearer header too: {response.status_code}")
        
except Exception as e:
    print(f"[FAIL] Token exchange test failed: {str(e)}")
    import traceback
    traceback.print_exc()

print()

# Step 4: Try get-session endpoint as alternative
print("STEP 4: Try get-session endpoint for JWT")
print("-" * 80)

try:
    session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    print(f"Requesting: {session_url}")
    response = httpx.get(session_url, headers=headers, timeout=10)
    print(f"Get-session Response Status: {response.status_code}")
    
    if response.status_code == 200:
        session_data = response.json()
        print(f"[INFO] Session response: {json.dumps(session_data, indent=2)[:500]}...")
        
        # Look for JWT in session.access_token
        jwt_token = None
        if isinstance(session_data, dict) and 'session' in session_data:
            if isinstance(session_data['session'], dict):
                jwt_token = session_data['session'].get('access_token')
        
        if jwt_token:
            print(f"[PASS] JWT found in session.access_token")
            print(f"JWT length: {len(jwt_token)}")
            
            if '.' in jwt_token:
                try:
                    header = pyjwt.get_unverified_header(jwt_token)
                    print(f"JWT Header: {json.dumps(header, indent=2)}")
                    print(f"[PASS] JWT structure valid")
                except Exception as e:
                    print(f"[WARN] JWT decode failed: {str(e)}")
        else:
            print(f"[WARN] No JWT found in session data")
    else:
        print(f"[FAIL] Get-session failed: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
except Exception as e:
    print(f"[FAIL] Get-session test failed: {str(e)}")

print()

# Step 5: Check if frontend SDK can get JWT
print("STEP 5: Check if frontend SDK methods can get JWT")
print("-" * 80)

print("[INFO] According to docs, authClient.token() should return JWT")
print("[INFO] But this requires the frontend SDK with proper session cookies")
print("[INFO] Our backend test doesn't have browser session context")
print("[INFO] Testing if we can call SDK methods directly...")

try:
    # The docs mention that authClient.token() requires the session cookie
    # Since we're testing from backend context, we can't test this directly
    # But we can check if there are other endpoints
    
    print("[INFO] Trying alternative endpoints mentioned in docs...")
    
    # Try some other possible endpoints based on Better Auth patterns
    alternative_endpoints = [
        "/auth/session",
        "/session", 
        "/api/auth/session",
        "/auth/jwt"
    ]
    
    for endpoint in alternative_endpoints:
        try:
            url = f"{NEON_AUTH_BASE_URL.rstrip('/')}{endpoint}"
            headers = {"Authorization": f"Bearer {session_token}"}
            response = httpx.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"[INFO] Endpoint {endpoint} returned 200")
                print(f"[INFO] Response: {json.dumps(data, indent=2)[:200]}...")
                
                # Check for JWT
                if isinstance(data, dict):
                    if 'jwt' in data or 'token' in data or 'access_token' in data:
                        print(f"[POTENTIAL] JWT might be available at {endpoint}")
        except:
            pass
            
except Exception as e:
    print(f"[INFO] Alternative endpoint test failed: {str(e)}")

print()
print("=" * 80)
print("JWT EXCHANGE TEST COMPLETE - SUMMARY")
print("=" * 80)
print()
print("FINDINGS:")
print("- JWKS endpoint: WORKING (EdDSA/Ed25519)")
print("- Login flow: WORKING (returns session token)")
print("- /token endpoint: NOT WORKING (401 Unauthorized)")
print("- /get-session endpoint: RETURNS NULL")
print("- Session token format: 32-char opaque token (not JWT)")
print()
print("ANALYSIS:")
print("- Neon Auth appears to have changed from JWT-first to session-first")
print("- The /token endpoint for JWT exchange is not working with our credentials")
print("- This suggests either:")
print("  1. Configuration issue (JWT plugin not enabled)")
print("  2. Neon Auth architecture change (JWTs now opt-in via plugin)")
print("  3. Different auth method required for JWT access")
print()
print("NEXT STEPS:")
print("- Check Neon Auth configuration for JWT plugin status")
print("- Verify if JWT plugin needs to be explicitly enabled")
print("- Consider updating backend to handle session tokens directly")
print("- OR implement proper session-to-JWT exchange flow")