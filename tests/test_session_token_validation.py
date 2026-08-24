"""
Session Token Validation Test
Tests the new session token validation functionality for Neon Auth
when JWT plugin is not enabled and opaque session tokens are used.
"""
import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
import httpx


class TestSessionTokenValidation:
    """Test session token validation via Neon Auth API"""

    @pytest.mark.asyncio
    async def test_validate_session_token_success(self):
        """Test successful session token validation"""
        from shared.auth import auth_client, validate_session_token

        # Mock the HTTP client to simulate successful Neon Auth API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "id": "neon-user-123",
                "email": "test@example.com",
                "name": "Test User"
            },
            "session": {
                "token": "opaque-session-token-123",
                "expiresAt": 1234567890
            }
        }

        with patch('httpx.AsyncClient') as mock_http_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response
            mock_http_client.return_value = mock_client_instance

            # Test session token validation
            payload = await validate_session_token("opaque-session-token-123")

            assert payload is not None, "Should return user claims"
            assert payload["sub"] == "neon-user-123", "sub claim should match user ID"
            assert payload["email"] == "test@example.com", "email claim should match"
            assert payload["exp"] == 1234567890, "exp claim should match session expiration"
            assert payload["session_token"] == "opaque-session-token-123", "should track session token origin"

    @pytest.mark.asyncio
    async def test_validate_session_token_invalid(self):
        """Test session token validation with invalid token"""
        from shared.auth import validate_session_token

        # Mock the HTTP client to simulate failed Neon Auth API response
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch('httpx.AsyncClient') as mock_http_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response
            mock_http_client.return_value = mock_client_instance

            # Test session token validation with invalid token
            payload = await validate_session_token("invalid-session-token")

            assert payload is None, "Invalid session token should return None"

    @pytest.mark.asyncio
    async def test_validate_session_token_timeout(self):
        """Test session token validation with timeout (fail closed)"""
        from shared.auth import validate_session_token

        # Mock the HTTP client to simulate timeout
        with patch('httpx.AsyncClient') as mock_http_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.side_effect = httpx.TimeoutException("Request timeout")
            mock_http_client.return_value = mock_client_instance

            # Test session token validation with timeout
            payload = await validate_session_token("session-token")

            assert payload is None, "Timeout should fail closed and return None"

    @pytest.mark.asyncio
    async def test_validate_session_token_cache(self):
        """Test that session token validation uses caching"""
        from shared.auth import validate_session_token, _token_cache

        # Clear cache for clean test
        _token_cache.clear()

        # Mock the HTTP client to simulate successful Neon Auth API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "id": "neon-user-123",
                "email": "test@example.com",
                "name": "Test User"
            },
            "session": {
                "token": "cached-session-token",
                "expiresAt": 1234567890
            }
        }

        with patch('httpx.AsyncClient') as mock_http_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response
            mock_http_client.return_value = mock_client_instance

            # First validation should call API
            payload1 = await validate_session_token("cached-session-token")
            assert payload1 is not None
            assert mock_client_instance.get.call_count == 1, "Should call API once"

            # Second validation should use cache
            payload2 = await validate_session_token("cached-session-token")
            assert payload2 is not None
            assert mock_client_instance.get.call_count == 1, "Should not call API again (cached)"

            assert payload1["sub"] == payload2["sub"], "Cached result should match"

    @pytest.mark.asyncio
    async def test_validate_session_token_no_config(self):
        """Test session token validation without proper configuration"""
        from shared.auth import validate_session_token

        # Temporarily clear environment variables
        original_base_url = os.environ.get("NEON_AUTH_BASE_URL")
        original_secret = os.environ.get("NEON_AUTH_COOKIE_SECRET")

        try:
            os.environ["NEON_AUTH_BASE_URL"] = ""
            os.environ["NEON_AUTH_COOKIE_SECRET"] = ""

            # Test session token validation without config
            payload = await validate_session_token("session-token")

            assert payload is None, "Should return None when not configured"

        finally:
            # Restore environment variables
            if original_base_url:
                os.environ["NEON_AUTH_BASE_URL"] = original_base_url
            if original_secret:
                os.environ["NEON_AUTH_COOKIE_SECRET"] = original_secret

    @pytest.mark.asyncio
    async def test_api_endpoint_fallback_to_session(self):
        """Test that API endpoints fall back to session validation when JWT fails"""
        from shared.auth import decode_access_token, validate_session_token, auth_client

        # Mock JWT validation to fail
        with patch('shared.auth._get_jwks_client') as mock_jwks:
            mock_jwks.return_value = None

            # Mock session validation to succeed on the auth client
            mock_payload = {
                "sub": "neon-user-123",
                "email": "test@example.com",
                "exp": 1234567890,
                "session_token": "opaque-token"
            }

            with patch.object(auth_client, 'validate_session_token') as mock_validate:
                mock_validate.return_value = mock_payload

                # Test with an opaque token that's not a valid JWT
                opaque_token = "32-character-opaque-session-token"

                # JWT validation should fail
                jwt_payload = decode_access_token(opaque_token)
                assert jwt_payload is None, "JWT validation should fail for opaque token"

                # Session validation should succeed
                session_payload = await validate_session_token(opaque_token)
                assert session_payload is not None, "Session validation should succeed"
                assert session_payload["sub"] == "neon-user-123", "Should return session-validated payload"

    @pytest.mark.asyncio
    async def test_neon_auth_client_validate_session(self):
        """Test NeonAuthClient.validate_session_token method"""
        from shared.auth import NeonAuthClient

        client = NeonAuthClient()

        # Mock the HTTP client to simulate successful Neon Auth API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "id": "neon-user-456",
                "email": "client-test@example.com",
                "name": "Client Test User"
            },
            "session": {
                "token": "client-session-token",
                "expiresAt": 1234567890
            }
        }

        with patch('httpx.AsyncClient') as mock_http_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response
            mock_http_client.return_value = mock_client_instance

            # Test client method
            payload = await client.validate_session_token("client-session-token")

            assert payload is not None, "Client method should return user claims"
            assert payload["sub"] == "neon-user-456", "sub claim should match"
            assert payload["email"] == "client-test@example.com", "email claim should match"

            # Verify the correct API endpoint was called
            call_args = mock_client_instance.get.call_args
            assert "/get-session" in call_args[0][0], "Should call /get-session endpoint"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])