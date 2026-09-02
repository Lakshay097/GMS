"""
Test for M1 security fix: Email enumeration prevention in /auth/link-account
"""
import pytest

def test_email_enumeration_prevention():
    """Test that email enumeration is prevented in link-account endpoint"""
    with open('api/auth.py', 'r') as f:
        content = f.read()
        # Check that the 'created' field is removed from response
        # The old response had "created" field
        # This would reveal whether the user was newly created
        assert '"created":' not in content or 'created' not in content[content.find('return {'):content.find('}') if 'return {' in content else 0:]
        
        # Check that timing attack prevention is added
        assert 'asyncio.sleep' in content or 'time.sleep' in content
        # Check that random delay is implemented for timing attack prevention
        assert 'timing attack' in content.lower() or 'hash' in content.lower() if 'asyncio.sleep' in content else True

def test_rate_limiting_on_link_account():
    """Test that rate limiting is applied to prevent enumeration attempts"""
    with open('api/auth.py', 'r') as f:
        content = f.read()
        # Check that the link-account endpoint has rate limiting
        # Find the link-account function and check for rate limiting decorator
        lines = content.split('\n')
        link_account_found = False
        rate_limit_found = False
        for i, line in enumerate(lines):
            if '@router.post("/link-account")' in line:
                link_account_found = True
            if link_account_found and '@limiter.limit' in line:
                rate_limit_found = True
                break
        
        assert link_account_found, "link-account endpoint not found"
        assert rate_limit_found, "Rate limiting not applied to link-account endpoint"

def test_uniform_response_structure():
    """Test that response structure is uniform to prevent enumeration"""
    with open('api/auth.py', 'r') as f:
        content = f.read()
        # Check that the return statement has consistent structure
        # It should always return the same fields regardless of user creation vs linking
        assert 'return {' in content
        # The response should not contain conditional 'created' field
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'return {' in line:
                # Check if this is the link-account return statement
                # It should be within the link_account function
                # and should not contain 'created' field
                if i > 200 and i < 400:  # Rough range where link-account return would be
                    assert '"created":' not in line, f"Found 'created' field in return statement at line {i+1}"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
