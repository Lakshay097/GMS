"""
Test Neon Auth service connectivity and configuration
"""
import sys
import asyncio
import httpx
from pathlib import Path
import os
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

async def test_neon_auth_service():
    """Test Neon Auth service connectivity"""
    print("=" * 60)
    print("Testing Neon Auth Service")
    print("=" * 60)
    
    neon_auth_url = os.getenv("NEON_AUTH_BASE_URL")
    neon_auth_secret = os.getenv("NEON_AUTH_COOKIE_SECRET")
    
    print(f"\nNeon Auth Base URL: {neon_auth_url}")
    print(f"Neon Auth Secret: {neon_auth_secret[:10] if neon_auth_secret else 'NOT SET'}...")
    
    if not neon_auth_url:
        print("[ERROR] NEON_AUTH_BASE_URL not set")
        return
    
    # Test 1: Basic connectivity
    print("\n" + "=" * 60)
    print("Test 1: Basic Connectivity")
    print("=" * 60)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(neon_auth_url, timeout=5)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            
            if response.status_code == 200:
                print("[OK] Neon Auth service is reachable")
            else:
                print(f"[WARNING] Unexpected status code: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to connect to Neon Auth: {e}")
    
    # Test 2: Sign-up endpoint
    print("\n" + "=" * 60)
    print("Test 2: Sign-up Endpoint")
    print("=" * 60)
    
    signup_url = f"{neon_auth_url}/sign-up/email"
    print(f"Testing: {signup_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            # Test with proper headers
            headers = {
                "Content-Type": "application/json",
                "Origin": "http://localhost:5175"
            }
            
            test_data = {
                "email": "test-user@example.com",
                "password": "TestPassword123!",
                "name": "Test User"
            }
            
            response = await client.post(signup_url, json=test_data, headers=headers, timeout=10)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code in [200, 201]:
                print("[OK] Sign-up endpoint responded successfully")
            elif response.status_code == 400:
                print("[INFO] Sign-up failed (likely user already exists or validation error)")
            else:
                print(f"[WARNING] Unexpected status code: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to test sign-up endpoint: {e}")
    
    # Test 3: Sign-in endpoint
    print("\n" + "=" * 60)
    print("Test 3: Sign-in Endpoint")
    print("=" * 60)
    
    signin_url = f"{neon_auth_url}/sign-in/email"
    print(f"Testing: {signin_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Content-Type": "application/json",
                "Origin": "http://localhost:5175"
            }
            
            # Try with the existing user
            signin_data = {
                "email": "lakshay.kumar@pw.live",
                "password": "YourPasswordHere"  # User would need to provide actual password
            }
            
            response = await client.post(signin_url, json=signin_data, headers=headers, timeout=10)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                print("[OK] Sign-in endpoint responded successfully")
                # Try to extract token
                try:
                    data = response.json()
                    if "token" in data or "session" in data:
                        print("[OK] Sign-in returned token/session data")
                except:
                    pass
            elif response.status_code == 401:
                print("[INFO] Sign-in failed (invalid credentials)")
            else:
                print(f"[WARNING] Unexpected status code: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to test sign-in endpoint: {e}")
    
    # Test 4: JWKS endpoint
    print("\n" + "=" * 60)
    print("Test 4: JWKS Endpoint (for token verification)")
    print("=" * 60)
    
    jwks_url = f"{neon_auth_url}/.well-known/jwks.json"
    print(f"Testing: {jwks_url}")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=5)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print("[OK] JWKS endpoint is accessible")
                try:
                    jwks_data = response.json()
                    keys = jwks_data.get("keys", [])
                    print(f"[OK] Found {len(keys)} signing keys")
                except:
                    print("[WARNING] Could not parse JWKS response")
            else:
                print(f"[WARNING] JWKS endpoint returned: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to test JWKS endpoint: {e}")
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print("If all tests pass, Neon Auth service is working correctly.")
    print("If sign-up/sign-in fail, check:")
    print("1. CORS configuration in Neon Console")
    print("2. Email/password requirements")
    print("3. Whether user already exists")

if __name__ == "__main__":
    asyncio.run(test_neon_auth_service())