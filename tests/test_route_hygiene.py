"""
Test for Route Hygiene security fixes: SuperAdmin controls, CORS, KPI import, Boto3
"""
import pytest

def test_school_deactivate_requires_confirmation():
    """Test that school deactivation requires confirmation parameter"""
    with open('modules/school-dept-user-role/api/schools.py', 'r') as f:
        content = f.read()
        # Check that confirm parameter exists
        assert 'confirm: bool = Query' in content
        # Check that confirmation is required
        assert 'CONFIRMATION_REQUIRED' in content
        # Check that destructive action requires confirmation
        assert 'Destructive action requires confirmation' in content

def test_user_archive_requires_confirmation():
    """Test that user archiving requires confirmation parameter"""
    with open('modules/school-dept-user-role/api/users.py', 'r', encoding='utf-8') as f:
        content = f.read()
        # Check that confirm parameter exists (body or query)
        assert 'confirm' in content.lower(), "confirm parameter not found"
        # Check that confirmation is required
        assert 'CONFIRMATION_REQUIRED' in content, "CONFIRMATION_REQUIRED not found"
        # Check that destructive action requires confirmation
        assert 'Destructive action requires confirmation' in content, "Confirmation message not found"

def test_kpi_deprecate_requires_confirmation():
    """Test that KPI deprecation requires confirmation parameter"""
    with open('modules/kra-kpi-library/api/routes.py', 'r') as f:
        content = f.read()
        # Check that confirm parameter exists
        assert 'confirm: bool = Query' in content
        # Check that confirmation is required
        assert 'CONFIRMATION_REQUIRED' in content
        # Check that destructive action requires confirmation
        assert 'Destructive action requires confirmation' in content

def test_kpi_import_hidden_from_schema():
    """Test that KPI import endpoint is hidden from public docs"""
    with open('modules/kra-kpi-library/api/routes.py', 'r') as f:
        content = f.read()
        # Check that import endpoint has include_in_schema=False
        assert '@router.post("/kpis/import", include_in_schema=False)' in content

def test_cors_configuration_proper():
    """Test that CORS is properly configured"""
    with open('api/main.py', 'r') as f:
        content = f.read()
        # Check that CORS middleware is configured
        assert 'CORSMiddleware' in content
        # Check that environment is checked
        assert 'CORS_ORIGINS' in content
        # Check that wildcard warning exists for production
        assert 'WARNING: CORS_ORIGINS' in content

def test_boto3_legitimate_use():
    """Test that boto3 is used for legitimate purposes"""
    with open('shared/task_queue.py', 'r') as f:
        content = f.read()
        # Check that boto3 is used for SQS
        assert 'boto3' in content
        assert 'sqs' in content.lower()
        # Check that it's in a try/except for import
        assert 'try:' in content and 'import boto3' in content

def test_boto3_in_dependencies():
    """Test that boto3 is in dependencies"""
    with open('pyproject.toml', 'r') as f:
        content = f.read()
        # Check that boto3 is in dependencies
        assert 'boto3' in content

def test_route_hygiene_documented():
    """Test that route hygiene decisions are documented"""
    import pathlib
    doc = pathlib.Path("ROUTE_HYGIENE_DECISIONS.md")
    assert doc.exists(), "Route hygiene decisions document should exist"
    
    with open('ROUTE_HYGIENE_DECISIONS.md', 'r') as f:
        content = f.read()
        # Check that the document contains the decision matrix
        assert 'SuperAdmin' in content
        assert 'confirmation' in content.lower()
        assert 'CORS' in content
        assert 'boto3' in content

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
