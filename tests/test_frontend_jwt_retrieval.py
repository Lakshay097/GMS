"""
Test frontend JWT retrieval using proper SDK configuration
This mimics what the frontend should do after login
"""
import os
import json
import httpx
import jwt as pyjwt
from datetime import datetime

os.environ["NEON_AUTH_BASE_URL"] = "https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth"
os.environ["NEON_AUTH_COOKIE_SECRET"] = "63lhEmBliLeAD5YKTLQ8F/y2ZDoxM1NKYSBjYPNK1zA="

NEON_AUTH_BASE_URL = os.environ["NEON_AUTH_BASE_URL"]

print("=" * 80)
print("FRONTEND JWT RETRIEVAL TEST")
print("=" * 80)

# Step 1: Login and get session token
print("STEP 1: Login to get session token")
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
    session_token = login_data.get('token')
    user_id = login_data.get('user', {}).get('id')
    
    print(f"Session token: {session_token}")
    print(f"User ID: {user_id}")
else:
    print(f"Login failed: {response.text}")
    exit(1)

print()

# Step 2: Try getSession with JWT header extraction
print("STEP 2: Try getSession with set-auth-jwt header extraction")
print("-" * 80)

try:
    session_url = f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session"
    cookies = {"__Secure-neonauth.session_token": session_token}
    
    print(f"Requesting: {session_url}")
    print(f"Using session cookie: __Secure-neonauth.session_token")
    
    response = httpx.get(session_url, cookies=cookies, timeout=10)
    print(f"Get-session status: {response.status_code}")
    
    # Check for set-auth-jwt header
    jwt_from_header = response.headers.get('set-auth-jwt')
    if jwt_from_header:
        print(f"[PASS] JWT found in set-auth-jwt header")
        print(f"JWT length: {len(jwt_from_header)}")
        print(f"JWT format: {jwt_from_header[:30]}...{jwt_from_header[-20:]}")
        
        # Verify JWT structure
        if '.' in jwt_from_header and jwt_from_header.count('.') == 2:
            print(f"[INFO] JWT has valid 3-part structure")
            
            try:
                # Decode header
                header = pyjwt.get_unverified_header(jwt_from_header)
                print(f"JWT Header: {json.dumps(header, indent=2)}")
                
                # Decode payload
                payload = pyjwt.decode(jwt_from_header, options={"verify_signature": False})
                print(f"JWT Payload (selected claims):")
                important_claims = ['sub', 'email', 'iss', 'aud', 'exp', 'iat', 'roles', 'name']
                for claim in important_claims:
                    if claim in payload:
                        value = payload[claim]
                        if claim in ['exp', 'iat']:
                            value = datetime.fromtimestamp(value).isoformat()
                        print(f"  {claim}: {value}")
                
                print(f"[PASS] JWT structure is valid")
                
                # Test with our backend decode function
                print()
                print("STEP 3: Test with our backend decode_access_token()")
                print("-" * 80)
                
                import sys
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from shared.auth import decode_access_token
                
                verified_payload = decode_access_token(jwt_from_header)
                
                if verified_payload:
                    print(f"[PASS] JWT successfully verified by our backend decode_access_token()")
                    print(f"Verified claims: {list(verified_payload.keys())}")
                    print(f"User ID: {verified_payload.get('sub')}")
                    print(f"Email: {verified_payload.get('email')}")
                    print()
                    print("=" * 80)
                    print("SUCCESS: JWT retrieval via getSession header works")
                    print("=" * 80)
                    print()
                    print("RESOLUTION: Update frontend to use getSession() with header extraction")
                    print("Add onSuccess handler to extract set-auth-jwt header")
                else:
                    print(f"[FAIL] JWT verification failed with our backend decode_access_token()")
            except Exception as e:
                print(f"[FAIL] JWT decode failed: {str(e)}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[WARN] JWT does not have valid 3-part structure")
    else:
        print(f"[INFO] No set-auth-jwt header found")
        print(f"[INFO] Available headers: {list(response.headers.keys())}")
        
        # Also check response body
        try:
            body = response.json()
            print(f"[INFO] Response body: {json.dumps(body, indent=2)[:300]}...")
        except:
            print(f"[INFO] Response body: {response.text[:300]}")
            
except Exception as e:
    print(f"[FAIL] Error: {str(e)}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("FRONTEND JWT RETRIEVAL TEST COMPLETE")
print("=" * 80)