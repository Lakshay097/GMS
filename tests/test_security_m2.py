"""
Test for M2 security fix: Re-enable evidence upload with proper security
"""
import pytest

def test_evidence_upload_route_enabled():
    """Test that evidence upload route is re-enabled in main.py"""
    with open('api/main.py', 'r') as f:
        content = f.read()
        # Check that evidence_routes import is not commented out
        assert 'from modules.observation_capture.api.evidence_routes import router as evidence_router' in content
        # Check that the router is included
        assert 'v1_router.include_router(evidence_router)' in content
        # Check that it's not inside a commented block
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'evidence_router' in line and 'include_router' in line:
                # Check that this line is not commented
                assert not line.strip().startswith('#'), f"Evidence router inclusion is commented out at line {i+1}"

def test_evidence_upload_requires_authentication():
    """Test that evidence upload endpoint requires authentication"""
    with open('modules/observation-capture/api/evidence_routes.py', 'r') as f:
        content = f.read()
        # Check that upload endpoint has get_current_user dependency
        assert 'get_current_user' in content
        # Check that current_user is used as a dependency
        assert 'current_user = Depends(get_current_user)' in content
        # Check that the upload function exists
        assert 'async def upload_evidence' in content

def test_evidence_upload_rate_limited():
    """Test that evidence upload endpoint is rate limited"""
    with open('modules/observation-capture/api/evidence_routes.py', 'r') as f:
        content = f.read()
        # Check that slowapi limiter is imported
        assert 'from slowapi import Limiter' in content
        # Check that limiter is instantiated
        assert 'limiter = Limiter' in content
        # Check that rate limiting decorator is used
        assert '@limiter.limit' in content
        # Check that upload function exists
        assert 'async def upload_evidence' in content

def test_evidence_content_type_validation():
    """Test that evidence upload validates content type matches file extension"""
    with open('modules/observation-capture/services/evidence_service.py', 'r') as f:
        content = f.read()
        # Check that mimetypes is imported for validation
        assert 'mimetypes' in content
        # Check that content type validation is performed
        assert 'content_type' in content
        assert 'mimetypes.guess_type' in content or 'content_type matches' in content.lower()

def test_deletion_endpoints_require_admin():
    """Test that deletion endpoints require Admin or SuperAdmin role"""
    with open('modules/observation-capture/api/evidence_routes.py', 'r', encoding='utf-8') as f:
        content = f.read()
        # Check that deletion endpoints have role checks via ADMIN_ROLES
        assert 'ADMIN_ROLES' in content, "ADMIN_ROLES check not found"
        # Check that 403 is raised for non-admin users
        assert 'HTTP_403_FORBIDDEN' in content, "HTTP_403_FORBIDDEN not found"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
