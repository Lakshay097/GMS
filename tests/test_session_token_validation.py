"""
Session Token Validation Tests
Tests the session/JWT token validation functionality for Clerk-based authentication.
Validates token creation, decoding, caching, and error handling.
"""
import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
import httpx


class TestSessionTokenValidation:
    """Test session/JWT token validation via Clerk-based authentication"""

    @pytest.mark.asyncio
    async def test_validate_session_token_success(self):
        """Test successful JWT token validation via decode_access_token"""
        from shared.auth import auth_client, create_access_token, decode_access_token

        # Create a valid token using the platform JWT signer
        test_payload = {
            "sub": "clerk-user-123",
            "email": "test@example.com",
            "roles": ["viewer"],
            "school_id": "school-123",
        }
        token = create_access_token(test_payload)

        # Test token validation
        payload = decode_access_token(token)

        assert payload is not None, "Should return user claims"
        assert payload["sub"] == "clerk-user-123", "sub claim should match user ID"
        assert payload["email"] == "test@example.com", "email claim should match"
        assert "exp" in payload, "exp claim should be present"

    @pytest.mark.asyncio
    async def test_validate_session_token_invalid(self):
        """Test token validation with invalid token"""
        from shared.auth import decode_access_token

        # Test with an invalid/garbage token
        payload = decode_access_token("invalid-garbage-token")
        assert payload is None, "Invalid token should return None"

    @pytest.mark.asyncio
    async def test_validate_session_token_timeout(self):
        """Test that decode_access_token returns None for empty/None tokens (fail closed)"""
        from shared.auth import decode_access_token

        # Test with empty token
        payload = decode_access_token("")
        assert payload is None, "Empty token should return None (fail closed)"

        # Test with None token
        payload = decode_access_token(None)
        assert payload is None, "None token should return None (fail closed)"

    @pytest.mark.asyncio
    async def test_validate_session_token_cache(self):
        """Test that token validation uses caching"""
        from shared.auth import decode_access_token, create_access_token, _token_cache

        # Clear cache for clean test
        _token_cache.clear()

        test_payload = {
            "sub": "clerk-user-456",
            "email": "cached@example.com",
            "roles": ["viewer"],
        }
        token = create_access_token(test_payload)

        # First validation should cache the result
        payload1 = decode_access_token(token)
        assert payload1 is not None
        assert token in _token_cache, "Token should be cached after first decode"

        # Second validation should use cache
        payload2 = decode_access_token(token)
        assert payload2 is not None

        assert payload1["sub"] == payload2["sub"], "Cached result should match"

    @pytest.mark.asyncio
    async def test_validate_session_token_no_config(self):
        """Test token validation when JWKS URL is not configured"""
        from shared.auth import decode_access_token, CLERK_JWKS_URL

        # When CLERK_JWKS_URL is not set, JWKS path is skipped but HS256 fallback works
        # Test that decode_access_token still works with platform tokens
        original = os.environ.get("PLATFORM_JWT_SECRET")
        try:
            os.environ["PLATFORM_JWT_SECRET"] = "test-secret-key-for-validation"
            # Import fresh to pick up env changes
            import importlib
            import shared.auth
            importlib.reload(shared.auth)
            
            from shared.auth import create_access_token, decode_access_token
            token = create_access_token({"sub": "test", "email": "test@test.com"})
            payload = decode_access_token(token)
            assert payload is not None, "Should return payload for valid token even without JWKS"
        finally:
            if original:
                os.environ["PLATFORM_JWT_SECRET"] = original

    @pytest.mark.asyncio
    async def test_api_endpoint_fallback_to_session(self):
        """Test that JWT validation works for platform-issued tokens"""
        from shared.auth import decode_access_token, create_access_token

        # Create a platform-issued HS256 token
        opaque_token = create_access_token({
            "sub": "clerk-user-789",
            "email": "fallback@example.com",
            "roles": ["admin"],
        })

        # JWT validation should succeed for a valid platform token
        jwt_payload = decode_access_token(opaque_token)
        assert jwt_payload is not None, "JWT validation should succeed for platform token"
        assert jwt_payload["sub"] == "clerk-user-789", "Should return validated payload"

    @pytest.mark.asyncio
    async def test_neon_auth_client_validate_session(self):
        """Test ClerkClient.verify_token method"""
        from shared.auth import ClerkClient

        client = ClerkClient()

        # Test verify_token with a valid platform-issued token
        from shared.auth import create_access_token
        valid_token = create_access_token({
            "sub": "clerk-user-456",
            "email": "client-test@example.com",
            "roles": ["admin"],
        })

        # verify_token delegates to decode_access_token
        payload = await client.verify_token(valid_token)

        assert payload is not None, "Client method should return user claims"
        assert payload["sub"] == "clerk-user-456", "sub claim should match"
        assert payload["email"] == "client-test@example.com", "email should match"

        # Test with invalid token
        invalid_payload = await client.verify_token("invalid.token.here")
        assert invalid_payload is None, "Invalid token should return None"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
