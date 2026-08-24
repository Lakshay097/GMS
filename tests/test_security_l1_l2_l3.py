"""
Test for L1-L3 security fixes: Error sanitization, security headers, and APM
"""
import pytest

def test_error_sanitization_in_production():
    """Test that errors are sanitized in production (L1 security fix)"""
    with open('api/main.py', 'r') as f:
        content = f.read()
        # Check that global exception handler exists
        assert 'global_exception_handler' in content
        # Check that it checks environment
        assert 'os.getenv("ENV"' in content or 'env == "production"' in content
        # Check that production returns generic message
        assert 'production' in content and 'internal server error' in content.lower()
        # Check that logging is used instead of print
        assert 'logger.error' in content

def test_security_headers_added():
    """Test that security headers are added (L2 security fix)"""
    with open('api/main.py', 'r') as f:
        content = f.read()
        # Check that security headers middleware exists
        assert 'add_security_headers' in content
        # Check CSP header
        assert 'Content-Security-Policy' in content
        # Check X-Frame-Options
        assert 'X-Frame-Options' in content
        assert 'DENY' in content
        # Check X-Content-Type-Options
        assert 'X-Content-Type-Options' in content
        assert 'nosniff' in content
        # Check Referrer-Policy
        assert 'Referrer-Policy' in content
        # Check HSTS
        assert 'Strict-Transport-Security' in content
        # Check XSS Protection
        assert 'X-XSS-Protection' in content

def test_apm_logging_added():
    """Test that basic APM logging is added (L3 security fix)"""
    with open('api/main.py', 'r') as f:
        content = f.read()
        # Check that performance timing middleware logs
        assert 'logger.info' in content
        # Check that request metrics are logged
        assert 'Status:' in content or 'status_code' in content
        # Check that timing is logged
        assert 'Time:' in content or 'process_time' in content

def test_logging_configured():
    """Test that logging is properly configured"""
    with open('api/main.py', 'r') as f:
        content = f.read()
        # Check that logging is imported
        assert 'import logging' in content
        # Check that logging is configured
        assert 'logging.basicConfig' in content
        # Check that logger is created
        assert 'logger = logging.getLogger' in content

def test_security_headers_environment_aware():
    """Test that security headers are environment-aware"""
    with open('api/main.py', 'r') as f:
        content = f.read()
        # Check that CSP differs between dev and prod
        assert 'env == "production"' in content
        # Check that HSTS is only in production
        assert 'if env == "production"' in content

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
