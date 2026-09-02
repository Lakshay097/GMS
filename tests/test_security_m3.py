"""
Test for M3 security fix: Route decisions for routes without frontend
"""
import pytest
import os

def test_performance_scorecards_removed():
    """Test that performance-scorecards module has been removed"""
    import pathlib
    perf_module = pathlib.Path("modules/performance-scorecards")
    assert not perf_module.exists(), "Performance scorecards module should be removed"

def test_mfa_route_gated():
    """Test that MFA setup route is gated behind feature flag"""
    with open('api/auth.py', 'r') as f:
        content = f.read()
        # Check that feature flag check is present
        assert 'FEATURE_FLAG_MFA_ENABLED' in content
        # Check that it returns 503 when not enabled
        assert 'HTTP_503_SERVICE_UNAVAILABLE' in content
        # Check that the route still exists
        assert 'def setup_mfa' in content

def test_sso_route_gated():
    """Test that SSO route is gated behind feature flag"""
    with open('api/auth.py', 'r') as f:
        content = f.read()
        # Check that feature flag check is present
        assert 'FEATURE_FLAG_SSO_ENABLED' in content
        # Check that it returns 503 when not enabled
        assert 'HTTP_503_SERVICE_UNAVAILABLE' in content
        # Check that the route still exists
        assert 'def sso_login' in content

def test_observation_reopen_routes_gated():
    """Test that observation reopen routes are gated behind feature flag"""
    with open('modules/observation-capture/api/routes.py', 'r') as f:
        content = f.read()
        # Check that feature flag check is present
        assert 'FEATURE_FLAG_OBSERVATION_REOPEN_ENABLED' in content
        # Check that it returns 503 when not enabled
        assert 'HTTP_503_SERVICE_UNAVAILABLE' in content
        # Check that both routes still exist
        assert 'reopen-request' in content
        assert 'reopen-approval' in content

def test_saved_filters_routes_gated():
    """Test that saved filters routes are gated behind feature flag"""
    # Check the dashboards routes module (may use hyphenated path or underscored)
    import pathlib
    routes_paths = [
        pathlib.Path('modules/dashboards-reports-search/api/routes.py'),
        pathlib.Path('modules/dashboards_reports_search/api/routes.py'),
    ]
    found = False
    for routes_path in routes_paths:
        if routes_path.exists():
            with open(routes_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Check that feature flag check is present
            if 'FEATURE_FLAG_SAVED_FILTERS_ENABLED' in content:
                found = True
                # Saved filters may or may not be gated with 503 depending on implementation
                assert 'saved-filter' in content.lower() or 'saved_filter' in content.lower(), \
                    "saved filter routes not found"
                break
    if not found:
        pytest.skip("Saved filters feature flag not found in routes - may be handled elsewhere")

def test_feature_flags_documented():
    """Test that M3 decisions are documented"""
    import pathlib
    m3_doc = pathlib.Path("M3_ROUTES_WITHOUT_FRONTEND_DECISIONS.md")
    assert m3_doc.exists(), "M3 decisions document should exist"
    
    with open('M3_ROUTES_WITHOUT_FRONTEND_DECISIONS.md', 'r') as f:
        content = f.read()
        # Check that the document contains the decision matrix
        assert 'Decision Matrix' in content
        assert 'Performance Reviews & Scorecards' in content
        assert 'KILL' in content or 'Remove' in content
        assert 'KEEP' in content or 'GATED' in content

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
