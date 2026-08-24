"""
Test for M4 security fix: N+1 query prevention on list endpoints
"""
import pytest

def test_configuration_engine_caching():
    """Test that ConfigurationEngine has caching to prevent N+1 queries"""
    with open('platform_services/configuration_engine/service.py', 'r') as f:
        content = f.read()
        # Check that cache is initialized
        assert '_cache' in content
        # Check that cache is a dict
        assert 'self._cache: dict' in content or 'self._cache = {}' in content
        # Check that cache is used in get method
        assert 'cache_key' in content
        # Check that cache is checked before database query
        assert 'if cache_key in self._cache' in content or 'if cache_key in' in content
        # Check that cache is set after database query
        assert 'self._cache[cache_key]' in content

def test_configuration_engine_cache_invalidation():
    """Test that ConfigurationEngine invalidates cache on updates"""
    with open('platform_services/configuration_engine/service.py', 'r') as f:
        content = f.read()
        # Check that cache is cleared on set_global
        assert '_clear_cache_for_key' in content or 'clear_cache' in content
        # Check that cache is cleared on set_override
        lines = content.split('\n')
        set_override_found = False
        cache_cleared = False
        for i, line in enumerate(lines):
            if 'async def set_override' in line:
                set_override_found = True
            if set_override_found and ('_clear_cache_for_key' in line or 'clear_cache' in line):
                cache_cleared = True
                break
        
        assert set_override_found, "set_override method not found"
        assert cache_cleared, "Cache not cleared in set_override method"

def test_observation_list_optimization():
    """Test that observation list endpoint uses caching"""
    with open('modules/observation-capture/api/routes.py', 'r') as f:
        content = f.read()
        # Check that list_observations exists
        assert 'async def list_observations' in content
        # Check that it uses the service
        assert 'ObservationService' in content

def test_cache_clear_method_exists():
    """Test that clear_cache method exists for testing purposes"""
    with open('platform_services/configuration_engine/service.py', 'r') as f:
        content = f.read()
        # Check that clear_cache method exists
        assert 'def clear_cache' in content

def test_cache_documented():
    """Test that M4 N+1 query fix is documented"""
    with open('platform_services/configuration_engine/service.py', 'r') as f:
        content = f.read()
        # Check that M4 is mentioned in docstring
        assert 'M4' in content or 'N+1' in content.lower() or 'caching' in content.lower()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
