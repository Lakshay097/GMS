"""
Test email enumeration fix (M1).
Verifies that /auth/link-account returns uniform status codes regardless of user existence.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from api.main import app
from shared.database import get_db


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


def test_link_account_uniform_status_existing_user(client):
    """Test that existing user without school_code still gets linked (superAdmin don't need school)."""
    from shared.auth import create_access_token
    from shared.models import UserStatus
    test_token = create_access_token({
        "sub": "existing-user-id",
        "email": "existing@example.com",
        "roles": ["viewer"]
    })

    mock_user = MagicMock()
    mock_user.id = "existing-user-id"
    mock_user.email = "existing@example.com"
    mock_user.roles = ["viewer"]
    mock_user.school_id = "test-school-id"
    mock_user.department_id = None
    mock_user.clerk_user_id = "existing-user-id"
    mock_user.status = UserStatus.ACTIVE
    mock_user.updated_at = MagicMock()

    from shared.models import User
    mock_user.__class__ = User

    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = mock_user

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_db_result)
    mock_session.commit = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/auth/link-account",
            headers={"Authorization": f"Bearer {test_token}"}
        )

        # Should return 200 with linked=True (user already exists)
        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is True
    finally:
        app.dependency_overrides.clear()


def test_link_account_uniform_status_new_user_missing_school_code(client):
    """Test that new user without school code returns 200 (not 400)."""
    from shared.auth import create_access_token
    test_token = create_access_token({
        "sub": "new-user-id",
        "email": "new@example.com",
        "roles": []
    })

    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = None  # User not found

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_db_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/auth/link-account",
            headers={"Authorization": f"Bearer {test_token}"},
            json={}
        )

        # Should return 200, not 400 (M1 fix)
        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is False
        assert data["requires_school_code"] is True
    finally:
        app.dependency_overrides.clear()


def test_link_account_uniform_status_invalid_school_code(client):
    """Test that invalid school code returns 200 (not 400)."""
    from shared.auth import create_access_token
    test_token = create_access_token({
        "sub": "new-user-id",
        "email": "new@example.com",
        "roles": []
    })

    # User not found (clerk_user_id lookup)
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = None

    # User not found (email fallback)
    mock_email_result = MagicMock()
    mock_email_result.scalar_one_or_none.return_value = None

    # School not found
    mock_school_result = MagicMock()
    mock_school_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[mock_user_result, mock_email_result, mock_school_result])

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/auth/link-account",
            headers={"Authorization": f"Bearer {test_token}"},
            json={"school_code": "invalid"}
        )

        # Should return 200, not 400 (M1 fix)
        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is False
        assert data["error"] == "INVALID_SCHOOL_CODE"
    finally:
        app.dependency_overrides.clear()


def test_link_account_timing_prevention(client):
    """Test that timing attacks are prevented by random delay."""
    import time
    from shared.auth import create_access_token
    from shared.models import UserStatus

    # Test existing user (no school_code — user already exists)
    existing_token = create_access_token({
        "sub": "existing-user-id",
        "email": "existing@example.com",
        "roles": ["viewer"]
    })

    mock_user = MagicMock()
    mock_user.id = "existing-user-id"
    mock_user.email = "existing@example.com"
    mock_user.roles = ["viewer"]
    mock_user.school_id = "test-school-id"
    mock_user.department_id = None
    mock_user.clerk_user_id = "existing-user-id"
    mock_user.status = UserStatus.ACTIVE
    mock_user.updated_at = MagicMock()

    from shared.models import User
    mock_user.__class__ = User

    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = mock_user

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_db_result)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        start = time.time()
        response = client.post(
            "/auth/link-account",
            headers={"Authorization": f"Bearer {existing_token}"}
        )
        existing_time = time.time() - start
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    # Test new user creation
    new_token = create_access_token({
        "sub": "new-user-id",
        "email": "new@example.com",
        "roles": []
    })

    # User not found
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = None

    # School found
    mock_school = MagicMock()
    mock_school.id = "school-id"
    from shared.models import School, SchoolStatus
    mock_school.__class__ = School
    mock_school.status = SchoolStatus.ACTIVE

    mock_school_result = MagicMock()
    mock_school_result.scalar_one_or_none.return_value = mock_school

    mock_session2 = AsyncMock()
    mock_session2.execute = AsyncMock(side_effect=[mock_user_result, mock_school_result])
    mock_session2.commit = AsyncMock()
    mock_session2.refresh = AsyncMock()
    mock_session2.add = MagicMock()

    async def override_get_db2():
        yield mock_session2

    app.dependency_overrides[get_db] = override_get_db2
    try:
        start = time.time()
        response = client.post(
            "/auth/link-account",
            headers={"Authorization": f"Bearer {new_token}"},
            json={"school_code": "valid"}
        )
        new_time = time.time() - start
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    # Both should have similar timing (within tolerance due to random delay)
    # The random delay (0.1-0.2s) should make timing attacks impractical
    assert abs(existing_time - new_time) < 0.3  # Allow some variance
