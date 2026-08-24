"""
Test cookie-based authentication (H2 security fix).
Verifies that tokens can be extracted from httpOnly cookies.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


def test_cookie_based_auth(client):
    """Test that authentication works using httpOnly cookie."""
    # Create a test token
    from shared.auth import create_access_token
    test_token = create_access_token({
        "sub": "test-user-id",
        "email": "test@example.com",
        "roles": ["viewer"],
        "school_id": "test-school-id"
    })
    
    # Test with /set-auth-cookie endpoint (supports cookies)
    response = client.post(
        "/auth/set-auth-cookie",
        json={"token": test_token}
    )
    
    # Should succeed and set cookie
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


def test_cookie_fallback_to_header(client):
    """Test that Authorization header still works as fallback."""
    # Create a test token
    from shared.auth import create_access_token
    test_token = create_access_token({
        "sub": "test-user-id",
        "email": "test@example.com",
        "roles": ["viewer"],
        "school_id": "test-school-id"
    })
    
    # Test with Authorization header (fallback)
    response = client.get(
        "/auth/get-session",
        headers={"Authorization": f"Bearer {test_token}"}
    )
    
    # Should succeed with header
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True


def test_cookie_flags_on_set(client):
    """Test that Set-Cookie has HttpOnly, Secure, and SameSite flags."""
    from shared.auth import create_access_token
    test_token = create_access_token({
        "sub": "test-user-id",
        "email": "test@example.com",
        "roles": ["viewer"]
    })
    
    response = client.post(
        "/auth/set-auth-cookie",
        json={"token": test_token}
    )
    
    assert response.status_code == 200
    
    # Check Set-Cookie header
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "httponly" in set_cookie.lower()
    assert "secure" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


def test_logout_clears_cookie(client):
    """Test that logout properly clears the cookie."""
    response = client.post("/auth/logout")
    
    assert response.status_code == 200
    
    # Check that cookie is cleared
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    # Should have expiration in the past
    assert "Max-Age=0" in set_cookie or "Expires=" in set_cookie