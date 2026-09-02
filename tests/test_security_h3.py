"""
Test for H3 security fix: Rate limiting on critical endpoints
"""
import pytest

def test_rate_limiting_on_auth_endpoints():
    """Test that rate limiting is configured on auth endpoints"""
    # This is a code review test to verify rate limiting decorators are present
    with open('api/auth.py', 'r') as f:
        content = f.read()
        # Check that slowapi limiter is imported
        assert 'from slowapi import Limiter' in content
        # Check that limiter is instantiated
        assert 'limiter = Limiter' in content
        # Check that rate limiting decorators are applied to critical endpoints
        assert '@limiter.limit' in content
        # Verify specific rate limits on sensitive endpoints
        assert '@limiter.limit("60/minute")' in content  # session checks (increased for multi-component page loads)
        assert '@limiter.limit("5/minute")' in content    # account linking (prevents enumeration)
        assert '@limiter.limit("3/minute")' in content    # signup (prevents abuse)

def test_rate_limiting_on_observation_endpoints():
    """Test that rate limiting is configured on observation endpoints"""
    with open('modules/observation-capture/api/routes.py', 'r') as f:
        content = f.read()
        # Check that slowapi limiter is imported
        assert 'from slowapi import Limiter' in content
        # Check that limiter is instantiated
        assert 'limiter = Limiter' in content
        # Check that rate limiting is applied to observation submission
        assert '@limiter.limit("30/minute")' in content

def test_rate_limiting_on_audit_discrepancy_endpoints():
    """Test that rate limiting is configured on audit discrepancy endpoints"""
    with open('modules/audit_discrepancy/api/routes.py', 'r') as f:
        content = f.read()
        # Check that slowapi limiter is imported
        assert 'from slowapi import Limiter' in content
        # Check that limiter is instantiated
        assert 'limiter = Limiter' in content
        # Check that rate limiting is applied to discrepancy endpoints
        assert '@limiter.limit' in content
        # Verify specific rate limits
        assert '@limiter.limit("20/minute")' in content  # discrepancy creation
        assert '@limiter.limit("30/minute")' in content  # investigation/approval actions

def test_rate_limiting_dependency_added():
    """Test that slowapi dependency is added to pyproject.toml"""
    with open('pyproject.toml', 'r') as f:
        content = f.read()
        # Check that slowapi is in dependencies
        assert 'slowapi' in content

def test_rate_limiting_exception_handler():
    """Test that rate limiting exception handler is configured in main app"""
    with open('api/main.py', 'r') as f:
        content = f.read()
        # Check that slowapi imports are present
        assert 'from slowapi import Limiter' in content
        assert 'from slowapi.util import get_remote_address' in content
        # Check that limiter is configured
        assert 'limiter = Limiter' in content
        # Check that exception handler is added
        assert 'RateLimitExceeded' in content and 'add_exception_handler' in content

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
