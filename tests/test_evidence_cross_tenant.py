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


def test_evidence_deletion_eligibility_cross_tenant_blocked(client):
    """Test that users cannot check deletion eligibility for evidence from other schools."""
    from shared.auth import create_access_token
    
    # User from school 1
    test_token = create_access_token({
        "sub": "user-1",
        "email": "user1@school1.com",
        "roles": ["admin"],
        "school_id": "school-1-id"
    })
    
    with patch('shared.middleware.tenancy.get_db') as mock_db:
        # Mock user lookup
        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.email = "user1@school1.com"
        mock_user.roles = ["admin"]
        mock_user.school_id = "school-1-id"
        mock_user.department_id = None
        mock_user.neon_auth_user_id = "user-1"
        
        from shared.models import User
        mock_user.__class__ = User
        
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        # Mock observation from school 2 (different school)
        mock_observation = MagicMock()
        mock_observation.id = "obs-1"
        mock_observation.school_id = "school-2-id"  # Different school
        mock_observation.department_id = None
        
        from shared.platform_models import Observation
        mock_observation.__class__ = Observation
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_observation
        mock_session.execute.return_value = mock_user_result
        mock_db().__aenter__.return_value = mock_session
        
        response = client.get(
            "/api/v1/evidence/deletion-eligibility/obs-1/evidence-1",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        
        # Should be blocked due to cross-tenant access
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]


def test_evidence_deletion_cross_tenant_blocked(client):
    """Test that users cannot delete evidence from other schools."""
    from shared.auth import create_access_token
    
    # User from school 1
    test_token = create_access_token({
        "sub": "user-1",
        "email": "user1@school1.com",
        "roles": ["admin"],
        "school_id": "school-1-id"
    })
    
    with patch('shared.middleware.tenancy.get_db') as mock_db:
        # Mock user lookup
        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.email = "user1@school1.com"
        mock_user.roles = ["admin"]
        mock_user.school_id = "school-1-id"
        mock_user.department_id = None
        mock_user.neon_auth_user_id = "user-1"
        
        from shared.models import User
        mock_user.__class__ = User
        
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        # Mock observation from school 2 (different school)
        mock_observation = MagicMock()
        mock_observation.id = "obs-1"
        mock_observation.school_id = "school-2-id"  # Different school
        mock_observation.department_id = None
        
        from shared.platform_models import Observation
        mock_observation.__class__ = Observation
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_observation
        mock_session.execute.return_value = mock_user_result
        mock_db().__aenter__.return_value = mock_session
        
        response = client.post(
            "/api/v1/evidence/delete",
            headers={"Authorization": f"Bearer {test_token}"},
            json={
                "observation_id": "obs-1",
                "public_id": "evidence-1",
                "reason": "Test deletion"
            }
        )
        
        # Should be blocked due to cross-tenant access
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]


def test_evidence_same_tenant_allowed(client):
    """Test that users can access evidence from their own school."""
    from shared.auth import create_access_token
    
    # User from school 1
    test_token = create_access_token({
        "sub": "user-1",
        "email": "user1@school1.com",
        "roles": ["admin"],
        "school_id": "school-1-id"
    })
    
    with patch('shared.middleware.tenancy.get_db') as mock_db:
        # Mock user lookup
        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.email = "user1@school1.com"
        mock_user.roles = ["admin"]
        mock_user.school_id = "school-1-id"
        mock_user.department_id = None
        mock_user.neon_auth_user_id = "user-1"
        
        from shared.models import User
        mock_user.__class__ = User
        
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user
        
        # Mock observation from school 1 (same school)
        mock_observation = MagicMock()
        mock_observation.id = "obs-1"
        mock_observation.school_id = "school-1-id"  # Same school
        mock_observation.department_id = None
        mock_observation.submitted_at = "2024-01-01"
        
        from shared.platform_models import Observation
        mock_observation.__class__ = Observation
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_observation
        mock_session.execute.return_value = mock_user_result
        mock_db().__aenter__.return_value = mock_session
        
        # Mock evidence service
        with patch('modules.observation_capture.services.evidence_service.EvidenceService') as mock_evidence_service:
            mock_service_instance = MagicMock()
            mock_service_instance.is_evidence_deletion_eligible = AsyncMock(return_value={
                "eligible": True,
                "retention_period_days": 90,
                "submitted_at": "2024-01-01",
                "retention_eligible_at": "2024-04-01",
                "days_until_eligible": -100,
                "public_id": "evidence-1"
            })
            mock_evidence_service.return_value = mock_service_instance
            
            response = client.get(
                "/api/v1/evidence/deletion-eligibility/obs-1/evidence-1",
                headers={"Authorization": f"Bearer {test_token}"}
            )
            
            # Should be allowed for same tenant
            assert response.status_code == 200