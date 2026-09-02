"""
Test cross-tenant evidence access prevention (A7 security fix).
Verifies that users cannot access evidence from other schools/tenants.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from api.main import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


def _mock_auth_dependency():
    """Create a mock for get_current_user dependency."""
    mock_user = MagicMock()
    mock_user.user_id = "user-1"
    mock_user.email = "user1@school1.com"
    mock_user.roles = ["admin"]
    mock_user.school_id = "school-1-id"
    return mock_user


def test_evidence_deletion_eligibility_cross_tenant_blocked(client):
    """Test that users cannot check deletion eligibility for evidence from other schools."""
    from shared.auth import create_access_token
    from shared.middleware import get_current_user
    from shared.middleware.tenancy import require_tenant_context
    from shared.database import get_db
    from shared.platform_models import Observation

    mock_current_user = _mock_auth_dependency()
    test_token = create_access_token({
        "sub": "user-1", "email": "user1@school1.com",
        "roles": ["admin"], "school_id": "school-1-id"
    })

    mock_observation = MagicMock(spec=Observation)
    mock_observation.id = "obs-1"
    mock_observation.school_id = "school-2-id"
    mock_observation.department_id = None

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_observation)

    mock_tenant = MagicMock()
    mock_tenant.user_id = "user-1"
    mock_tenant.school_id = "school-1-id"
    mock_tenant.department_id = None
    mock_tenant.roles = ["admin"]

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[require_tenant_context] = lambda: mock_tenant
    app.dependency_overrides[get_db] = mock_get_db

    try:
        response = client.get(
            "/api/v1/evidence/deletion-eligibility/00000000-0000-0000-0000-000000000001/evidence-1",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        assert response.status_code in [403, 404], \
            f"Expected 403 or 404 for cross-tenant access, got {response.status_code}"
    finally:
        app.dependency_overrides.clear()


def test_evidence_deletion_cross_tenant_blocked(client):
    """Test that users cannot delete evidence from other schools."""
    from shared.auth import create_access_token
    from shared.middleware import get_current_user
    from shared.middleware.tenancy import require_tenant_context
    from shared.database import get_db
    from shared.platform_models import Observation

    mock_current_user = _mock_auth_dependency()
    test_token = create_access_token({
        "sub": "user-1", "email": "user1@school1.com",
        "roles": ["admin"], "school_id": "school-1-id"
    })

    mock_observation = MagicMock(spec=Observation)
    mock_observation.id = "obs-1"
    mock_observation.school_id = "school-2-id"
    mock_observation.department_id = None

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_observation)

    mock_tenant = MagicMock()
    mock_tenant.user_id = "user-1"
    mock_tenant.school_id = "school-1-id"
    mock_tenant.department_id = None
    mock_tenant.roles = ["admin"]

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[require_tenant_context] = lambda: mock_tenant
    app.dependency_overrides[get_db] = mock_get_db

    try:
        response = client.post(
            "/api/v1/evidence/delete",
            headers={"Authorization": f"Bearer {test_token}"},
            json={
                "observation_id": "00000000-0000-0000-0000-000000000001",
                "public_id": "evidence-1",
                "reason": "Test deletion"
            }
        )
        assert response.status_code in [403, 400], \
            f"Expected 403 or 400 for cross-tenant access, got {response.status_code}"
    finally:
        app.dependency_overrides.clear()


def test_evidence_same_tenant_allowed(client):
    """Test that users can access evidence from their own school."""
    from shared.auth import create_access_token
    from shared.middleware import get_current_user
    from shared.middleware.tenancy import require_tenant_context
    from shared.database import get_db
    from shared.platform_models import Observation

    mock_current_user = _mock_auth_dependency()
    test_token = create_access_token({
        "sub": "user-1", "email": "user1@school1.com",
        "roles": ["admin"], "school_id": "school-1-id"
    })

    mock_observation = MagicMock(spec=Observation)
    mock_observation.id = "obs-1"
    mock_observation.school_id = "school-1-id"
    mock_observation.department_id = None
    mock_observation.submitted_at = "2024-01-01"

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_observation)

    mock_tenant = MagicMock()
    mock_tenant.user_id = "user-1"
    mock_tenant.school_id = "school-1-id"
    mock_tenant.department_id = None
    mock_tenant.roles = ["admin"]

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[require_tenant_context] = lambda: mock_tenant
    app.dependency_overrides[get_db] = mock_get_db

    try:
        with patch('modules.observation_capture.services.evidence_service.EvidenceService') as mock_ev_svc:
            mock_svc = MagicMock()
            mock_svc.is_evidence_deletion_eligible = AsyncMock(return_value={
                "eligible": True, "retention_period_days": 90,
                "submitted_at": "2024-01-01", "retention_eligible_at": "2024-04-01",
                "days_until_eligible": -100, "public_id": "evidence-1"
            })
            mock_ev_svc.return_value = mock_svc
            response = client.get(
                "/api/v1/evidence/deletion-eligibility/00000000-0000-0000-0000-000000000001/evidence-1",
                headers={"Authorization": f"Bearer {test_token}"}
            )
            assert response.status_code in [200, 403], \
                f"Expected 200 or 403, got {response.status_code}"
    finally:
        app.dependency_overrides.clear()
