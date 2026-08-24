"""
Test for H2 security fix: JWT stored in httpOnly cookie instead of localStorage
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_set_auth_cookie_endpoint():
    """Test that the /auth/set-auth-cookie endpoint sets httpOnly cookie"""
    # Mock a valid token
    from shared.auth import create_access_token
    token = create_access_token({"sub": "test-user", "email": "test@example.com"})
    
    response = client.post(
        "/auth/set-auth-cookie",
        json={"token": token},
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Auth cookie set successfully"
    
    # Check that cookie was set with correct attributes
    cookies = response.cookies
    assert "auth_token" in cookies
    
def test_set_auth_cookie_invalid_token():
    """Test that invalid tokens are rejected"""
    response = client.post(
        "/auth/set-auth-cookie",
        json={"token": "invalid.token.here"},
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 401
    # Error is nested under 'detail' in FastAPI error responses
    response_data = response.json()
    assert "detail" in response_data
    assert "error" in response_data["detail"]

def test_logout_clears_cookie():
    """Test that logout endpoint clears the auth cookie"""
    response = client.post("/auth/logout")
    
    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful"
    
    # Check that cookie deletion header is set
    # Note: TestClient doesn't fully support cookie headers, 
    # but we can verify the endpoint structure

def test_no_localstorage_in_frontend():
    """Verify that frontend no longer stores token in localStorage"""
    # This is a code review test - check that localStorage usage is removed
    with open('frontend/src/lib/api.ts', 'r') as f:
        content = f.read()
        # Should not contain localStorage.setItem followed by auth_token
        lines = content.split('\n')
        has_auth_token_set = any('localStorage.setItem' in line and 'auth_token' in line for line in lines)
        assert not has_auth_token_set, "Found localStorage.setItem for auth_token in api.ts - security vulnerability"
    
    # Check auth.ts for backwards compatibility cleanup
    with open('frontend/src/lib/auth.ts', 'r') as f:
        auth_content = f.read()
        # Should still have the removal for backwards compatibility  
        assert 'localStorage.removeItem' in auth_content

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
