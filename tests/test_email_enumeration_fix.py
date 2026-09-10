"""
Test email enumeration prevention (M1) in the self-managed auth flow.

Old Clerk flow endpoints (/auth/link-account) are gone. The equivalent
enumeration-safety guarantees now live in:
  - POST /auth/login           → uniform "Invalid email or password"
  - POST /auth/forgot-password → uniform response regardless of account existence
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from api.main import app
from shared.database import get_db
from shared.models import UserStatus
from shared.auth import hash_password


@pytest.fixture
def client():
    return TestClient(app)


def _mock_user(email="existing@example.com"):
    user = MagicMock()
    user.id = "11111111-1111-1111-1111-111111111111"
    user.email = email
    user.full_name = "Existing User"
    user.school_id = "test-school-id"
    user.department_id = None
    user.roles = ["viewer"]
    user.mfa_enabled = False
    user.status = UserStatus.ACTIVE
    user.failed_login_count = 0
    user.locked_until = None
    user.password_hash = hash_password("CorrectHorse1")
    return res_user(user)


def res_user(u):
    return u


def _db_result(value):
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = value
    return mock_db_result


def test_login_uniform_error_existing_user_wrong_password(client):
    """Wrong password for an existing user → generic 401, no hint the account exists."""
    user = _mock_user()

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=_db_result(user))
    mock_session.commit = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post("/auth/login", json={"email": user.email, "password": "WrongPass99"})
        assert response.status_code == 401
        body = response.json()
        assert body["detail"]["error"]["code"] == "INVALID_CREDENTIALS"
        assert body["detail"]["error"]["message"] == "Invalid email or password"
    finally:
        app.dependency_overrides.clear()


def test_login_uniform_error_unknown_email(client):
    """Unknown email → identical generic 401 (cannot probe for registered emails)."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=_db_result(None))
    mock_session.commit = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post("/auth/login", json={"email": "ghost@example.com", "password": "Whatever123"})
        assert response.status_code == 401
        body = response.json()
        assert body["detail"]["error"]["code"] == "INVALID_CREDENTIALS"
        assert body["detail"]["error"]["message"] == "Invalid email or password"
    finally:
        app.dependency_overrides.clear()


def test_forgot_password_uniform_response_existing_and_unknown(client):
    """/auth/forgot-password returns the same body whether or not the email exists."""
    # Unknown email
    mock_session_unknown = AsyncMock()
    mock_session_unknown.execute = AsyncMock(return_value=_db_result(None))
    mock_session_unknown.commit = AsyncMock()

    async def db_unknown():
        yield mock_session_unknown

    app.dependency_overrides[get_db] = db_unknown
    try:
        resp_unknown = client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    finally:
        app.dependency_overrides.clear()

    # Existing email
    user = _mock_user()
    mock_session_existing = AsyncMock()
    mock_session_existing.execute = AsyncMock(return_value=_db_result(user))
    mock_session_existing.commit = AsyncMock()
    mock_session_existing.add = MagicMock()

    async def db_existing():
        yield mock_session_existing

    app.dependency_overrides[get_db] = db_existing
    try:
        resp_existing = client.post("/auth/forgot-password", json={"email": user.email})
    finally:
        app.dependency_overrides.clear()

    assert resp_unknown.status_code == resp_existing.status_code == 200
    assert resp_unknown.json() == resp_existing.json()
    # Neither reveals account existence
    assert "registered" in resp_unknown.json()["message"]
    assert resp_unknown.json()["success"] is True
