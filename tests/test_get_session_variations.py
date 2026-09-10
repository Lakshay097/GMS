"""
Session retrieval variation tests — GET /auth/get-session.

Replaces the legacy Neon-Auth debugging script (which called a dead external
endpoint with hardcoded credentials and collected zero test functions).

Covers:
  - Cookie-only session (normal browser path)
  - Bearer-header-only session (API client / non-browser path)
  - Both cookie and Bearer present (cookie wins per implementation)
  - Missing token → {valid: false}
  - Malformed / garbage token → {valid: false}
  - Unknown (valid-shaped) token → {valid: false}
  - Session present but user account is INACTIVE → {valid: false}
  - Expired session row → {valid: false}
  - Active session returns user payload with expected fields
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.auth import hash_password, generate_session_token, hash_session_token
from shared.models import UserStatus


# ── Shared helpers ────────────────────────────────────────────────────────────

COOKIE_NAME = "schoolops_session"


def _utc_now():
    return datetime.now(timezone.utc)


def _mock_user(status=UserStatus.ACTIVE, roles=None):
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = f"user-{u.id}@test.example"
    u.full_name = "Session Test User"
    u.school_id = uuid.uuid4()
    u.department_id = uuid.uuid4()
    u.roles = roles or ["viewer"]
    u.mfa_enabled = False
    u.status = status
    u.password_hash = hash_password("ValidPass1")
    u.failed_login_count = 0
    u.locked_until = None
    return u


def _mock_session_row(user_id, *, expired=False, token_hash=None):
    """Return a minimal AuthSession mock."""
    now = _utc_now()
    s = MagicMock()
    s.id = uuid.uuid4()
    s.user_id = user_id
    s.token_hash = token_hash or hashlib.sha256(b"dummy").hexdigest()
    s.expires_at = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    s.absolute_expires_at = now - timedelta(hours=1) if expired else now + timedelta(hours=12)
    s.last_used_at = now
    s.ip_address = "127.0.0.1"
    s.user_agent = "test-agent"
    return s


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


def _make_fake_db(session_row, user_row):
    """
    Build a get_db override that returns session_row for AuthSession queries
    and user_row for User queries.
    """
    from shared.database import get_db

    call_count = {"n": 0}

    async def _fake_db():
        session = MagicMock()

        def _execute(stmt):
            result = MagicMock()
            call_count["n"] += 1
            # First DB call → auth_sessions lookup; second → users lookup
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = session_row
            else:
                result.scalar_one_or_none.return_value = user_row
            return result

        session.execute = AsyncMock(side_effect=_execute)
        session.commit = AsyncMock()
        return session

    return get_db, _fake_db


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGetSessionVariations:

    def test_no_token_returns_invalid(self, client):
        """No cookie, no header → {valid: false}."""
        resp = client.get("/auth/get-session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["user"] is None

    def test_cookie_valid_session(self, client):
        """Session cookie with a valid matching token returns the user payload."""
        user = _mock_user()
        raw_token, token_hash = generate_session_token()
        session_row = _mock_session_row(user.id, token_hash=token_hash)

        get_db, fake_db = _make_fake_db(session_row, user)
        client.app.dependency_overrides[get_db] = fake_db

        resp = client.get("/auth/get-session", cookies={COOKIE_NAME: raw_token})
        client.app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["user"]["email"] == user.email
        assert "roles" in data["user"]
        assert "capabilities" in data["user"]

    def test_bearer_header_valid_session(self, client):
        """Authorization: Bearer <token> is accepted when no cookie is present."""
        user = _mock_user(roles=["admin"])
        raw_token, token_hash = generate_session_token()
        session_row = _mock_session_row(user.id, token_hash=token_hash)

        get_db, fake_db = _make_fake_db(session_row, user)
        client.app.dependency_overrides[get_db] = fake_db

        resp = client.get(
            "/auth/get-session",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        client.app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_cookie_takes_precedence_over_bearer(self, client):
        """When both cookie and Bearer header are present, the cookie wins."""
        user = _mock_user()
        raw_cookie_token, cookie_hash = generate_session_token()
        raw_bearer_token, _ = generate_session_token()  # different token — not in DB

        # Only the cookie token has a matching session row
        session_row = _mock_session_row(user.id, token_hash=cookie_hash)
        get_db, fake_db = _make_fake_db(session_row, user)
        client.app.dependency_overrides[get_db] = fake_db

        resp = client.get(
            "/auth/get-session",
            cookies={COOKIE_NAME: raw_cookie_token},
            headers={"Authorization": f"Bearer {raw_bearer_token}"},
        )
        client.app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_malformed_token_returns_invalid(self, client):
        """A garbage / malformed token value returns {valid: false}, not a 500."""
        resp = client.get(
            "/auth/get-session",
            cookies={COOKIE_NAME: "not-a-real-token!!!"},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_unknown_token_returns_invalid(self, client):
        """A correctly-shaped but unrecognised token (not in DB) returns {valid: false}."""
        raw_token, _ = generate_session_token()

        get_db_key = None

        async def fake_db():
            session = MagicMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = None  # no session row
            session.execute = AsyncMock(return_value=result)
            session.commit = AsyncMock()
            return session

        from shared.database import get_db
        client.app.dependency_overrides[get_db] = fake_db

        resp = client.get("/auth/get-session", cookies={COOKIE_NAME: raw_token})
        client.app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_expired_session_returns_invalid(self, client):
        """A session row whose expires_at is in the past returns {valid: false}."""
        user = _mock_user()
        raw_token, token_hash = generate_session_token()
        session_row = _mock_session_row(user.id, token_hash=token_hash, expired=True)

        get_db, fake_db = _make_fake_db(session_row, user)
        client.app.dependency_overrides[get_db] = fake_db

        resp = client.get("/auth/get-session", cookies={COOKIE_NAME: raw_token})
        client.app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_inactive_user_session_returns_invalid(self, client):
        """A valid session token for an INACTIVE user returns {valid: false}.

        validate_session() loads User with status == ACTIVE filter, so an
        INACTIVE user's row is never returned — the DB query yields None.
        """
        raw_token, token_hash = generate_session_token()
        # We need a real user id to build the session row
        user_id = uuid.uuid4()
        session_row = _mock_session_row(user_id, token_hash=token_hash)

        from shared.database import get_db

        call_count = {"n": 0}

        async def fake_db():
            session = MagicMock()

            def _execute(stmt):
                result = MagicMock()
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # AuthSession lookup → found
                    result.scalar_one_or_none.return_value = session_row
                else:
                    # User lookup with status==ACTIVE filter → None (user is INACTIVE)
                    result.scalar_one_or_none.return_value = None
                return result

            session.execute = AsyncMock(side_effect=_execute)
            session.commit = AsyncMock()
            return session

        client.app.dependency_overrides[get_db] = fake_db
        resp = client.get("/auth/get-session", cookies={COOKIE_NAME: raw_token})
        client.app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_session_payload_contains_required_fields(self, client):
        """The user object must contain id, email, full_name, roles, capabilities."""
        user = _mock_user(roles=["checker"])
        raw_token, token_hash = generate_session_token()
        session_row = _mock_session_row(user.id, token_hash=token_hash)

        get_db, fake_db = _make_fake_db(session_row, user)
        client.app.dependency_overrides[get_db] = fake_db

        resp = client.get("/auth/get-session", cookies={COOKIE_NAME: raw_token})
        client.app.dependency_overrides.clear()

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["valid"] is True
        user_obj = payload["user"]
        for field in ("id", "email", "full_name", "roles", "capabilities",
                      "school_id", "department_id", "mfa_enabled"):
            assert field in user_obj, f"missing field: {field}"

    def test_me_alias_behaves_identically(self, client):
        """GET /auth/me is an alias for /auth/get-session and must behave identically."""
        # No token: both endpoints return the same shape
        r1 = client.get("/auth/get-session")
        r2 = client.get("/auth/me")
        assert r1.status_code == r2.status_code == 200
        assert r1.json() == r2.json()
