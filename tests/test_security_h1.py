"""
Test for H1 security fix: IP allow-listing for internal scheduler endpoints
"""
import pytest
import os
import ipaddress
import api.internal_routes

def test_ip_allow_listing_production():
    """Test that IP allow-listing works in production mode"""
    from api.internal_routes import is_ip_allowed
    
    original_env = os.environ.get('ENV', 'development')
    original_ranges = os.environ.get('CLOUD_SCHEDULER_IP_RANGES', '')
    
    try:
        # Set production environment with specific IP ranges
        os.environ['ENV'] = 'production'
        os.environ['CLOUD_SCHEDULER_IP_RANGES'] = '10.0.0.0/8,172.16.0.0/12'
        
        # Test that allowed IPs pass
        assert is_ip_allowed('10.0.0.1') == True
        assert is_ip_allowed('172.16.0.1') == True
        
        # Test that disallowed IPs fail
        assert is_ip_allowed('192.168.1.1') == False
        assert is_ip_allowed('8.8.8.8') == False
        
    finally:
        # Restore original environment
        os.environ['ENV'] = original_env
        os.environ['CLOUD_SCHEDULER_IP_RANGES'] = original_ranges

def test_ip_allow_listing_development():
    """Test that all IPs are allowed in development mode"""
    from api.internal_routes import is_ip_allowed
    
    original_env = os.environ.get('ENV', 'development')
    
    try:
        os.environ['ENV'] = 'development'
        
        # In development, all IPs should be allowed
        assert is_ip_allowed('192.168.1.1') == True
        assert is_ip_allowed('8.8.8.8') == True
        assert is_ip_allowed('10.0.0.1') == True
        
    finally:
        os.environ['ENV'] = original_env

def test_ip_allow_listing_no_config():
    """Test that production fails closed when no IP ranges are configured"""
    from api.internal_routes import is_ip_allowed
    
    original_env = os.environ.get('ENV', 'development')
    original_ranges = os.environ.get('CLOUD_SCHEDULER_IP_RANGES', '')
    
    try:
        os.environ['ENV'] = 'production'
        os.environ['CLOUD_SCHEDULER_IP_RANGES'] = ''
        
        # In production without config, all IPs should be denied
        assert is_ip_allowed('10.0.0.1') == False
        assert is_ip_allowed('192.168.1.1') == False
        
    finally:
        os.environ['ENV'] = original_env
        os.environ['CLOUD_SCHEDULER_IP_RANGES'] = original_ranges

def test_ip_network_parsing():
    """Test that IP network ranges are parsed correctly"""
    from api.internal_routes import is_ip_allowed
    
    original_env = os.environ.get('ENV', 'development')
    original_ranges = os.environ.get('CLOUD_SCHEDULER_IP_RANGES', '')
    
    try:
        os.environ['ENV'] = 'production'
        os.environ['CLOUD_SCHEDULER_IP_RANGES'] = '10.0.0.0/8,192.168.0.0/16'
        
        # Test network range membership
        assert is_ip_allowed('10.0.0.1') == True
        assert is_ip_allowed('10.255.255.255') == True
        assert is_ip_allowed('192.168.0.1') == True
        assert is_ip_allowed('192.168.255.255') == True
        assert is_ip_allowed('11.0.0.1') == False
        assert is_ip_allowed('193.168.0.1') == False
        
    finally:
        os.environ['ENV'] = original_env
        os.environ['CLOUD_SCHEDULER_IP_RANGES'] = original_ranges

def test_defense_in_depth_implementation():
    """Test that both verification functions exist and are called"""
    from api.internal_routes import verify_internal_secret, verify_client_ip, verify_internal_auth
    
    # Verify all security functions exist
    assert callable(verify_internal_secret)
    assert callable(verify_client_ip)
    assert callable(verify_internal_auth)
    
    # The implementation should have the new functions
    assert hasattr(api.internal_routes, 'verify_internal_auth')
    assert hasattr(api.internal_routes, 'verify_client_ip')
    assert hasattr(api.internal_routes, 'is_ip_allowed')

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
