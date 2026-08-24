"""
Test Clerk JWT generation and verification
This script tests the Clerk JWT flow without requiring the full frontend
"""
import os
import httpx
import json
import jwt as pyjwt
from shared.auth import decode_access_token, create_access_token

# Clerk configuration
CLERK_SECRET_KEY = "sk_test_3Vl885kbImIyNuBUqNaw7etRpqn2JOG8zRFpYmxtfk"
CLERK_JWKS_URL = "https://popular-spaniel-5660.clerk.accounts.dev/.well-known/jwks.json"

def test_jwks_endpoint():
    """Test that Clerk JWKS endpoint is accessible"""
    print("Testing Clerk JWKS endpoint...")
    try:
        response = httpx.get(CLERK_JWKS_URL, timeout=10)
        print(f"JWKS Status: {response.status_code}")
        if response.status_code == 200:
            jwks_data = response.json()
            print(f"Keys found: {len(jwks_data.get('keys', []))}")
            if jwks_data.get('keys'):
                first_key = jwks_data['keys'][0]
                print(f"First key type: {first_key.get('kty')}")
                print(f"First key algorithm: {first_key.get('alg')}")
                print("PASS: JWKS endpoint is accessible")
                return True
        else:
            print("FAIL: JWKS endpoint returned non-200 status")
            return False
    except Exception as e:
        print(f"FAIL: Error accessing JWKS endpoint: {e}")
        return False

def test_backend_token_generation():
    """Test that our backend can generate tokens"""
    print("\nTesting backend token generation...")
    try:
        test_claims = {
            "sub": "test-user-id",
            "email": "test@example.com",
            "roles": ["viewer"],
            "school_id": "test-school-id"
        }
        token = create_access_token(test_claims)
        print(f"Generated token: {token[:50]}...")

        # Test decoding
        decoded = decode_access_token(token)
        if decoded:
            print(f"PASS: Token generated and decoded successfully")
            print(f"Decoded claims: {json.dumps(decoded, indent=2)}")
            return True
        else:
            print("FAIL: Failed to decode generated token")
            return False
    except Exception as e:
        print(f"FAIL: Error in token generation test: {e}")
        return False

def test_clerk_backend_integration():
    """Test that our backend auth module is configured for Clerk"""
    print("\nTesting Clerk backend integration...")
    try:
        from shared.auth import _get_jwks_client

        jwks_client = _get_jwks_client()
        if jwks_client:
            print("PASS: JWKS client initialized successfully")
            print(f"JWKS URL: {CLERK_JWKS_URL}")
            return True
        else:
            print("FAIL: JWKS client failed to initialize")
            return False
    except Exception as e:
        print(f"FAIL: Error in Clerk integration test: {e}")
        return False

def main():
    print("=" * 60)
    print("Clerk JWT Integration Test")
    print("=" * 60)

    results = {
        "JWKS Endpoint": test_jwks_endpoint(),
        "Backend Token Generation": test_backend_token_generation(),
        "Clerk Backend Integration": test_clerk_backend_integration()
    }

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")

    all_passed = all(results.values())
    print("=" * 60)
    if all_passed:
        print("SUCCESS: All tests passed!")
    else:
        print("WARNING: Some tests failed")
    print("=" * 60)

if __name__ == "__main__":
    main()
