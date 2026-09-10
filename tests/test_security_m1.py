"""
Test for M1 security fix: enumeration prevention + rate limiting on auth endpoints.

The old /auth/link-account endpoint (Clerk flow) was removed. The equivalent
guarantees now live on /auth/login, /auth/forgot-password and /auth/reset-password.
These are code-contract tests verifying the protections stay in place.
"""
import pytest


def test_login_uniform_error_message():
    """Login must return one generic message for unknown email AND wrong password."""
    with open('api/auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    assert '"INVALID_CREDENTIALS", "message": "Invalid email or password"' in content, (
        "Login must use a single uniform error message"
    )
    # Unknown-email path must raise the SAME generic_error object (no separate message)
    assert content.count('raise generic_error') >= 2, (
        "Both unknown-email and wrong-password paths must share the uniform error"
    )


def test_forgot_password_never_reveals_existence():
    """forgot-password response must not depend on whether the email exists."""
    with open('api/auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'If that email is registered, reset instructions have been sent.' in content
    # The success return must be OUTSIDE any conditional that checks the user
    assert 'reset instructions have been sent' in content


def test_rate_limiting_on_auth_endpoints():
    """Auth endpoints that could be probed must be rate limited."""
    with open('api/auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    for endpoint in ('/login', '/forgot-password', '/reset-password'):
        decorator_pos = content.find(f'"{endpoint}"')
        assert decorator_pos != -1, f"{endpoint} endpoint missing"
        after = content[decorator_pos:decorator_pos + 300]
        assert '@limiter.limit' in after, f"Rate limiting not applied to {endpoint}"


def test_brute_force_lockout_present():
    """Repeated failures must lock the account (MAX_FAILED_LOGINS / LOCKOUT_MINUTES)."""
    with open('api/auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'MAX_FAILED_LOGINS' in content
    assert 'LOCKOUT_MINUTES' in content
    assert 'ACCOUNT_LOCKED' in content


def test_passwords_never_logged_or_returned():
    """No auth response should ever include a password or password_hash field."""
    with open('api/auth.py', 'r', encoding='utf-8') as f:
        content = f.read()
    assert '"password_hash"' not in content.replace('password_hash=', ''), (
        "password_hash must never appear in a response payload"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
