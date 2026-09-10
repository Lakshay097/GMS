"""
Session-cookie authentication tests.

The old Clerk flow (set-auth-cookie / Bearer JWT) is gone; authentication is a
Secure, HttpOnly session cookie issued by POST /auth/login and validated
against the auth_sessions table.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from shared.auth import hash_password, hash_session_token
from shared.models import UserStatus


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


def _mock_user(email="test@example.com"):
    user = MagicMock()
    user.id = "11111111-1111-1111-1111-111111111111"
    user.email = email
    user.full_name = "Test User"
    user.school_id = None
    user.department_id = None
    user.roles = ["viewer"]
    user.mfa_enabled = False
    user.status = UserStatus.ACTIVE
    user.failed_login_count = 0
    user.locked_until = None
    user.password_hash = hash_password("CorrectHorse1")
    return user


def _patch_db_scalar(result_user):
    """Build an execute() mock returning scalar_one_or_none() -> result_user."""
    res = MagicMock()
    res.scalar_one_or_none.return_value = result_user
    return res


def test_login_sets_session_cookie(client):
    """POST /auth/login with valid credentials sets an HttpOnly session cookie."""
    user = _mock_user()

    def fake_execute(_stmt):
        return _patch_db_scalar(user)

    with patch("api.auth.select", side_effect=None), \
         patch.object(client.app, "dependency_overrides", {}) as _overrides:
        from shared.database import get_db

        async def fake_db():
            session = MagicMock()
            session.execute = AsyncMock(side_effect=fake_execute)
            session.add = MagicMock()
            session.commit = AsyncMock()
            return session

        client.app.dependency_overrides[get_db] = fake_db
        resp = client.post("/auth/login", json={"email": user.email, "password": "CorrectHorse1"})

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid"] is True
    assert data["user"]["email"] == user.email
    set_cookie = resp.headers.get("set-cookie", "")
    assert "schoolops_session=" in set_cookie
    assert "httponly" in set_cookie.lower()


def test_login_wrong_password_rejected(client):
    """A wrong password yields a uniform 401 (no account enumeration)."""
    user = _mock_user()

    def fake_execute(_stmt):
        return _patch_db_scalar(user)

    from shared.database import get_db

    async def fake_db():
        session = MagicMock()
        session.execute = AsyncMock(side_effect=fake_execute)
        session.commit = AsyncMock()
        return session

    client.app.dependency_overrides[get_db] = fake_db
    resp = client.post("/auth/login", json={"email": user.email, "password": "WrongPass99"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["error"]["code"] == "INVALID_CREDENTIALS"
    client.app.dependency_overrides.clear()


def test_login_unknown_email_same_error_as_wrong_password(client):
    """Unknown email and wrong password produce identical responses."""
    from shared.database import get_db

    async def fake_db():
        session = MagicMock()
        session.execute = AsyncMock(side_effect=lambda _s: _patch_db_scalar(None))
        session.commit = AsyncMock()
        return session

    client.app.dependency_overrides[get_db] = fake_db
    resp_unknown = client.post("/auth/login", json={"email": "ghost@example.com", "password": "Whatever123"})
    client.app.dependency_overrides.clear()

    user = _mock_user()

    async def fake_db2():
        session = MagicMock()
        session.execute = AsyncMock(side_effect=lambda _s: _patch_db_scalar(user))
        session.commit = AsyncMock()
        return session

    client.app.dependency_overrides[get_db] = fake_db
    resp_wrong_pw = client.post("/auth/login", json={"email": user.email, "password": "WrongPass99"})
    client.app.dependency_overrides.clear()

    assert resp_unknown.status_code == resp_wrong_pw.status_code == 401
    assert resp_unknown.json() == resp_wrong_pw.json()


def test_logout_clears_cookie(client):
    """Logout clears the cookie and returns success even without a session row."""
    resp = client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Logout successful"
    set_cookie = resp.headers.get("set-cookie", "")
    # Starlette deletes cookies by setting an empty Max-Age/expiry
    assert "schoolops_session=" in set_cookie


def test_get_session_without_cookie_is_invalid(client):
    """GET /auth/get-session without a cookie reports an invalid session."""
    resp = client.get("/auth/get-session")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
    assert resp.json()["user"] is None
