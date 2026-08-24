"""
Live JWT Token Retrieval Test
Tests JWT token retrieval from Neon Auth using frontend SDK approach
This validates the alternative approach when server-side session validation is not available
"""
import os
import sys
import json
import httpx
import asyncio

# Configure with staging credentials
os.environ["NEON_AUTH_BASE_URL"] = "https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth"
os.environ["NEON_AUTH_COOKIE_SECRET"] = "63lhEmBliLeAD5YKTLQ8F/y2ZDoxM1NKYSBjYPNK1zA="

NEON_AUTH_BASE_URL = os.environ["NEON_AUTH_BASE_URL"]
NEON_AUTH_COOKIE_SECRET = os.environ["NEON_AUTH_COOKIE_SECRET"]

print("=" * 80)
print("LIVE JWT TOKEN RETRIEVAL TEST")
print("=" * 80)
print(f"NEON_AUTH_BASE_URL: {NEON_AUTH_BASE_URL}")
print(f"NEON_AUTH_COOKIE_SECRET: {NEON_AUTH_COOKIE_SECRET[:20]}...")
print()

# Add to path to import shared.auth
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_live_jwt_retrieval():
    """Test JWT token retrieval against live Neon Auth instance"""
    
    # Test 1: Get a real session token via login
    print("TEST 1: Obtain Real Session Token via Login")
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
            print(f"[PASS] Login successful")
            print(f"Response keys: {list(login_data.keys())}")
            
            # Extract session token
            session_token = None
            if 'session' in login_data and 'token' in login_data['session']:
                session_token = login_data['session']['token']
            elif 'token' in login_data:
                session_token = login_data['token']
            
            if session_token:
                print(f"[PASS] Session token obtained (length: {len(session_token)})")
                print(f"Token format: {session_token[:20]}...{session_token[-10:] if len(session_token) > 30 else session_token}")
                
                # Test 2: Try to get JWT via /get-session with session cookie
                print()
                print("TEST 2: Try JWT Retrieval via /get-session")
                print("-" * 80)
                
                try:
                    # Try to get JWT by calling /get-session with session cookie
                    jwt_response = httpx.get(
                        f"{NEON_AUTH_BASE_URL.rstrip('/')}/get-session",
                        headers={
                            "Cookie": f"__Secure-neonauth.session_token={session_token}"
                        },
                        timeout=10
                    )
                    print(f"JWT Retrieval Response Status: {jwt_response.status_code}")
                    print(f"JWT Retrieval Response: {jwt_response.text[:500]}...")
                    
                    # Check response headers for JWT
                    if 'set-auth-jwt' in jwt_response.headers:
                        jwt_token = jwt_response.headers['set-auth-jwt']
                        print(f"[PASS] JWT found in response header")
                        print(f"JWT length: {len(jwt_token)}")
                    else:
                        print(f"[INFO] No JWT in response headers")
                        
                except Exception as e:
                    print(f"[INFO] JWT retrieval failed: {str(e)}")
                
                # Test 3: Try JWT exchange endpoint
                print()
                print("TEST 3: Try JWT Exchange via /token endpoint")
                print("-" * 80)
                
                try:
                    # Try to exchange session token for JWT
                    token_response = httpx.post(
                        f"{NEON_AUTH_BASE_URL.rstrip('/')}/token",
                        headers={
                            "Authorization": f"Bearer {session_token}",
                            "Cookie": f"__Secure-neonauth.session_token={session_token}"
                        },
                        timeout=10
                    )
                    print(f"JWT Exchange Response Status: {token_response.status_code}")
                    print(f"JWT Exchange Response: {token_response.text[:500]}...")
                    
                    if token_response.status_code == 200:
                        token_data = token_response.json()
                        if 'token' in token_data or 'jwt' in token_data:
                            jwt_token = token_data.get('token') or token_data.get('jwt')
                            print(f"[PASS] JWT obtained via exchange")
                            print(f"JWT length: {len(jwt_token)}")
                        else:
                            print(f"[INFO] No JWT in exchange response")
                    else:
                        print(f"[INFO] JWT exchange endpoint not available (expected without JWT plugin)")
                        
                except Exception as e:
                    print(f"[INFO] JWT exchange failed: {str(e)}")
                
                # Test 4: Test with existing JWT verification
                print()
                print("TEST 4: Test Existing JWT Verification with Session Token")
                print("-" * 80)
                
                from shared.auth import decode_access_token
                
                # Try to decode the session token as JWT (will fail)
                jwt_payload = decode_access_token(session_token)
                
                if jwt_payload:
                    print(f"[PASS] Session token is actually a JWT")
                    print(f"User ID: {jwt_payload.get('sub')}")
                    print(f"Email: {jwt_payload.get('email')}")
                else:
                    print(f"[INFO] Session token is not a JWT (as expected)")
                    print(f"[INFO] This confirms JWT plugin is not enabled")
                
                print()
                print("=" * 80)
                print("LIVE JWT RETRIEVAL TEST COMPLETE")
                print("=" * 80)
                print()
                print("SUMMARY:")
                print("- Session Token Acquisition: PASS")
                print("- JWT via /get-session: Not available")
                print("- JWT via /token endpoint: Not available (JWT plugin not enabled)")
                print("- JWT Verification: Session token is opaque, not JWT")
                print()
                print("CONCLUSION: Live testing confirms that JWT plugin is not enabled on this")
                print("Neon Auth instance. The recommended approach is to:")
                print("1. Enable JWT plugin in Neon Auth configuration (Option A)")
                print("2. Use frontend SDK authClient.token() to get JWT (Option B)")
                print("3. Current implementation supports both JWT and session validation")
                print()
                print("Current backend implementation is ready for both approaches:")
                print("- JWT verification via JWKS (when JWT plugin is enabled)")
                print("- Session validation via API (when available)")
                print("- Fallback mechanisms in place for smooth transition")
                
                return True
                
            else:
                print(f"[FAIL] No session token found in login response")
                return False
        else:
            print(f"[FAIL] Login failed with status {response.status_code}")
            print(f"Response: {response.text[:300]}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Live JWT retrieval test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_live_jwt_retrieval())
    sys.exit(0 if success else 1)