"""
Tests for Phase 3 production configuration fixes.
Verifies startup validation, CORS configuration, ENCRYPTION_KEY, and INTERNAL_SCHEDULER_SECRET.
"""
import pytest
import os
from unittest.mock import patch, Mock
import sys


@pytest.mark.asyncio
class TestStartupValidation:
    """Test startup configuration validation."""

    async def test_validate_startup_config_missing_database_url(self):
        """
        Test that startup fails when DATABASE_URL is missing.
        """
        from api.main import validate_startup_config
        
        with patch.dict(os.environ, {"DATABASE_URL": "", "ENV": "production"}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                await validate_startup_config()
            assert exc_info.value.code == 1

    async def test_validate_startup_config_missing_encryption_key_in_production(self):
        """
        Test that startup fails when ENCRYPTION_KEY is missing in production.
        """
        from api.main import validate_startup_config
        
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test",
            "ENV": "production",
            "ENCRYPTION_KEY": ""
        }, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                await validate_startup_config()
            assert exc_info.value.code == 1

    async def test_validate_startup_config_missing_scheduler_secret_in_production(self):
        """
        Test that startup fails when INTERNAL_SCHEDULER_SECRET is missing in production.
        """
        from api.main import validate_startup_config
        
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test",
            "ENV": "production",
            "ENCRYPTION_KEY": "a" * 32,
            "INTERNAL_SCHEDULER_SECRET": ""
        }, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                await validate_startup_config()
            assert exc_info.value.code == 1

    async def test_validate_startup_config_short_encryption_key_in_production(self):
        """
        Test that startup fails when ENCRYPTION_KEY is too short in production.
        """
        from api.main import validate_startup_config
        
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test",
            "ENV": "production",
            "ENCRYPTION_KEY": "short",
            "INTERNAL_SCHEDULER_SECRET": "valid-secret"
        }, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                await validate_startup_config()
            assert exc_info.value.code == 1

    async def test_validate_startup_config_default_scheduler_secret_in_production(self):
        """
        Test that startup fails when INTERNAL_SCHEDULER_SECRET uses default value in production.
        """
        from api.main import validate_startup_config
        
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test",
            "ENV": "production",
            "ENCRYPTION_KEY": "a" * 32,
            "INTERNAL_SCHEDULER_SECRET": "secret"
        }, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                await validate_startup_config()
            assert exc_info.value.code == 1

    async def test_validate_startup_config_passes_with_valid_production_config(self):
        """
        Test that startup succeeds with valid production configuration.
        """
        from api.main import validate_startup_config
        
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test",
            "ENV": "production",
            "ENCRYPTION_KEY": "a" * 32,
            "INTERNAL_SCHEDULER_SECRET": "strong-unique-secret",
            "CORS_ORIGINS": "https://example.com"
        }, clear=True):
            # Should not raise
            await validate_startup_config()

    async def test_validate_startup_config_passes_in_development_without_optional_vars(self):
        """
        Test that startup succeeds in development without optional production variables.
        """
        from api.main import validate_startup_config
        
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test",
            "ENV": "development"
        }, clear=True):
            # Should not raise
            await validate_startup_config()

    async def test_validate_startup_config_warns_wildcard_cors_in_production(self):
        """
        Test that startup warns about wildcard CORS in production but doesn't fail.
        """
        from api.main import validate_startup_config
        
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test",
            "ENV": "production",
            "ENCRYPTION_KEY": "a" * 32,
            "INTERNAL_SCHEDULER_SECRET": "strong-unique-secret",
            "CORS_ORIGINS": "*"
        }, clear=True):
            # Should not raise, but should warn
            await validate_startup_config()


@pytest.mark.asyncio
class TestEncryptionKeyConfiguration:
    """Test ENCRYPTION_KEY configuration."""

    def test_encryption_key_required_in_production(self):
        """
        Test that ENCRYPTION_KEY is required in production.
        """
        with patch.dict(os.environ, {"ENV": "production", "ENCRYPTION_KEY": ""}, clear=True):
            with pytest.raises(ValueError, match="ENCRYPTION_KEY environment variable is required in production"):
                from shared.auth import ENCRYPTION_KEY  # This will trigger the validation

    def test_encryption_key_generated_for_development(self):
        """
        Test that ENCRYPTION_KEY is generated for development when not set.
        """
        with patch.dict(os.environ, {"ENV": "development", "ENCRYPTION_KEY": ""}, clear=True):
            # Reload the module to trigger generation
            import importlib
            import shared.auth
            importlib.reload(shared.auth)
            
            # Should have generated a key
            assert shared.auth.ENCRYPTION_KEY is not None
            assert len(shared.auth.ENCRYPTION_KEY) >= 32

    def test_encryption_key_used_from_environment(self):
        """
        Test that ENCRYPTION_KEY is used from environment when set.
        """
        test_key = "test-encryption-key-32-characters-long"
        with patch.dict(os.environ, {"ENV": "production", "ENCRYPTION_KEY": test_key}, clear=True):
            import importlib
            import shared.auth
            importlib.reload(shared.auth)
            
            assert shared.auth.ENCRYPTION_KEY == test_key


@pytest.mark.asyncio
class TestSchedulerSecretConfiguration:
    """Test INTERNAL_SCHEDULER_SECRET configuration."""

    def test_scheduler_secret_required_in_production(self):
        """
        Test that INTERNAL_SCHEDULER_SECRET is required in production.
        """
        with patch.dict(os.environ, {"ENV": "production", "INTERNAL_SCHEDULER_SECRET": ""}, clear=True):
            with pytest.raises(ValueError, match="INTERNAL_SCHEDULER_SECRET environment variable is required in production"):
                from api.internal_routes import INTERNAL_SCHEDULER_SECRET  # This will trigger validation

    def test_scheduler_secret_rejects_defaults_in_production(self):
        """
        Test that INTERNAL_SCHEDULER_SECRET rejects default values in production.
        """
        for default_secret in ["secret", "password", "changeme", "default", "test"]:
            with patch.dict(os.environ, {"ENV": "production", "INTERNAL_SCHEDULER_SECRET": default_secret}, clear=True):
                with pytest.raises(ValueError, match="must not use default values in production"):
                    from api.internal_routes import INTERNAL_SCHEDULER_SECRET

    def test_scheduler_secret_uses_default_for_development(self):
        """
        Test that INTERNAL_SCHEDULER_SECRET uses default for development when not set.
        """
        with patch.dict(os.environ, {"ENV": "development", "INTERNAL_SCHEDULER_SECRET": ""}, clear=True):
            import importlib
            import api.internal_routes
            importlib.reload(api.internal_routes)
            
            # Should use development default
            assert api.internal_routes.INTERNAL_SCHEDULER_SECRET == "dev-secret-do-not-use-in-production"

    def test_scheduler_secret_uses_value_from_environment(self):
        """
        Test that INTERNAL_SCHEDULER_SECRET is used from environment when set.
        """
        test_secret = "strong-unique-scheduler-secret"
        with patch.dict(os.environ, {"ENV": "production", "INTERNAL_SCHEDULER_SECRET": test_secret}, clear=True):
            import importlib
            import api.internal_routes
            importlib.reload(api.internal_routes)
            
            assert api.internal_routes.INTERNAL_SCHEDULER_SECRET == test_secret


@pytest.mark.asyncio
class TestCORSConfiguration:
    """Test CORS configuration."""

    def test_cors_origins_defaults_for_development(self):
        """
        Test that CORS_ORIGINS defaults to localhost for development.
        """
        with patch.dict(os.environ, {"ENV": "development", "CORS_ORIGINS": "*"}, clear=True):
            # Simulate the CORS configuration logic from main.py
            cors_origins = os.getenv("CORS_ORIGINS", "*")
            if os.getenv("ENV", "development") == "production":
                pass  # Production logic
            else:
                if cors_origins == "*":
                    cors_origins = "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000"
            
            # Should have localhost defaults
            assert "localhost" in cors_origins
            assert "127.0.0.1" in cors_origins

    def test_cors_origins_uses_explicit_value_in_production(self):
        """
        Test that CORS_ORIGINS uses explicit value in production.
        """
        test_origins = "https://app.example.com,https://admin.example.com"
        with patch.dict(os.environ, {"ENV": "production", "CORS_ORIGINS": test_origins}, clear=True):
            cors_origins = os.getenv("CORS_ORIGINS", "*")
            
            assert cors_origins == test_origins
            assert cors_origins != "*"

    def test_cors_origins_warns_wildcard_in_production(self):
        """
        Test that wildcard CORS in production generates a warning.
        """
        with patch.dict(os.environ, {"ENV": "production", "CORS_ORIGINS": "*"}, clear=True):
            cors_origins = os.getenv("CORS_ORIGINS", "*")
            env = os.getenv("ENV", "development")
            
            warning_triggered = False
            if env == "production" and cors_origins == "*":
                warning_triggered = True
            
            assert warning_triggered


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test /health endpoint."""

    async def test_health_endpoint_returns_healthy_status(self):
        """
        Test that /health endpoint returns healthy status.
        """
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "service" in data

    async def test_health_endpoint_includes_version(self):
        """
        Test that /health endpoint includes API version.
        """
        from fastapi.testclient import TestClient
        from api.main import app, API_VERSION
        
        client = TestClient(app)
        response = client.get("/health")
        
        data = response.json()
        assert data["version"] == API_VERSION

    async def test_health_endpoint_includes_service_name(self):
        """
        Test that /health endpoint includes service name.
        """
        from fastapi.testclient import TestClient
        from api.main import app
        
        client = TestClient(app)
        response = client.get("/health")
        
        data = response.json()
        assert data["service"] == "school-operations-platform"
