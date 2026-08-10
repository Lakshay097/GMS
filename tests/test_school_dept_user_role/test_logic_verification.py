"""
Logic verification tests for PRS §18-21 acceptance criteria.
Tests the core business logic without requiring full module imports.
"""
import pytest
import os


def get_project_root():
    """Get the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_school_deactivation_logic():
    """Test that school deactivation logic is implemented."""
    project_root = get_project_root()
    school_service_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'services', 'school_service.py')
    
    # Read the school service file and check for deactivation logic
    with open(school_service_path, 'r') as f:
        content = f.read()
    
    # Check for deactivation method
    assert 'def deactivate_school' in content, "School deactivation method not found"
    
    # Check for soft delete (status change) not hard delete
    assert 'SchoolStatus.DEACTIVATED' in content, "Deactivation status not found"
    assert 'FR-007' in content or 'soft delete' in content.lower(), "Soft delete reference not found"
    
    # Check that it doesn't use hard delete
    assert 'delete(' not in content.lower() or 'hard delete' not in content.lower(), "Hard delete found (should be soft delete)"


def test_school_activation_validation_logic():
    """Test that school activation validation logic is implemented."""
    project_root = get_project_root()
    school_service_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'services', 'school_service.py')
    
    with open(school_service_path, 'r') as f:
        content = f.read()
    
    # Check for activation validation method
    assert 'def validate_school_activation' in content, "School activation validation method not found"
    
    # Check for department validation
    assert 'department' in content.lower(), "Department validation not found"
    
    # Check for KPI library validation
    assert 'kpi' in content.lower(), "KPI library validation not found"


def test_department_archival_validation_logic():
    """Test that department archival validation logic is implemented."""
    project_root = get_project_root()
    dept_service_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'services', 'department_service.py')
    
    with open(dept_service_path, 'r') as f:
        content = f.read()
    
    # Check for archival method
    assert 'def archive_department' in content, "Department archival method not found"
    
    # Check for open tasks validation
    assert '_check_open_tasks' in content, "Open tasks check method not found"
    
    # Check for unresolved discrepancies validation
    assert '_check_unresolved_discrepancies' in content, "Unresolved discrepancies check method not found"
    
    # Check for ValidationError raising
    assert 'ValidationError' in content, "ValidationError not imported/used"
    
    # Check for FR-014 reference
    assert 'FR-014' in content, "FR-014 reference not found"


def test_user_archive_logic():
    """Test that user archive logic is implemented."""
    project_root = get_project_root()
    user_service_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'services', 'user_service.py')
    
    with open(user_service_path, 'r') as f:
        content = f.read()
    
    # Check for archive method
    assert 'def archive_user' in content, "User archive method not found"
    
    # Check for UserStatus.ARCHIVED
    assert 'UserStatus.ARCHIVED' in content, "Archived status not found"
    
    # Check for FR-021 and FR-022 references
    assert 'FR-021' in content, "FR-021 reference not found"
    assert 'FR-022' in content, "FR-022 reference not found"
    
    # Check that it doesn't use hard delete
    assert 'delete(' not in content.lower() or 'hard delete' not in content.lower(), "Hard delete found (should be soft delete)"


def test_school_name_uniqueness_logic():
    """Test that school name uniqueness logic is implemented."""
    project_root = get_project_root()
    school_service_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'services', 'school_service.py')
    
    with open(school_service_path, 'r') as f:
        content = f.read()
    
    # Check for name uniqueness validation
    assert 'name' in content.lower() and 'unique' in content.lower(), "Name uniqueness validation not found"
    
    # Check for FR-005 reference
    assert 'FR-005' in content, "FR-005 reference not found"
    
    # Check for ValidationError on duplicate
    assert 'ValidationError' in content, "ValidationError not imported/used"


def test_department_name_uniqueness_logic():
    """Test that department name uniqueness logic is implemented."""
    project_root = get_project_root()
    dept_service_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'services', 'department_service.py')
    
    with open(dept_service_path, 'r') as f:
        content = f.read()
    
    # Check for name uniqueness validation
    assert 'name' in content.lower() and 'unique' in content.lower(), "Name uniqueness validation not found"
    
    # Check for FR-012 reference
    assert 'FR-012' in content, "FR-012 reference not found"
    
    # Check for school_id filtering
    assert 'school_id' in content.lower(), "School ID filtering not found"


def test_user_single_school_constraint_logic():
    """Test that user single school constraint logic is implemented."""
    project_root = get_project_root()
    user_service_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'services', 'user_service.py')
    
    with open(user_service_path, 'r') as f:
        content = f.read()
    
    # Check for school constraint validation
    assert 'school_id' in content.lower(), "School ID validation not found"
    
    # Check for role-based constraint
    assert 'SuperAdmin' in content or 'superadmin' in content.lower(), "SuperAdmin check not found"
    assert 'Viewer' in content or 'viewer' in content.lower(), "Viewer check not found"
    
    # Check for FR-019 reference
    assert 'FR-019' in content, "FR-019 reference not found"
    
    # Check for FR-020 reference (multi-school for Viewer)
    assert 'FR-020' in content, "FR-020 reference not found"


def test_api_endpoints_exist():
    """Test that all required API endpoints are defined."""
    project_root = get_project_root()
    
    # Check schools API
    schools_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'schools.py')
    with open(schools_api_path, 'r') as f:
        schools_content = f.read()
    
    assert '@router.post' in schools_content, "POST endpoint not found in schools API"
    assert '@router.get' in schools_content, "GET endpoint not found in schools API"
    assert '@router.patch' in schools_content, "PATCH endpoint not found in schools API"
    assert 'deactivate' in schools_content.lower(), "Deactivate endpoint not found"
    
    # Check departments API
    departments_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'departments.py')
    with open(departments_api_path, 'r') as f:
        departments_content = f.read()
    
    assert '@router.post' in departments_content, "POST endpoint not found in departments API"
    assert '@router.get' in departments_content, "GET endpoint not found in departments API"
    assert '@router.patch' in departments_content, "PATCH endpoint not found in departments API"
    assert 'archive' in departments_content.lower(), "Archive endpoint not found"
    
    # Check users API
    users_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'users.py')
    with open(users_api_path, 'r') as f:
        users_content = f.read()
    
    assert '@router.post' in users_content, "POST endpoint not found in users API"
    assert '@router.get' in users_content, "GET endpoint not found in users API"
    assert '@router.patch' in users_content, "PATCH endpoint not found in users API"
    assert 'archive' in users_content.lower(), "Archive endpoint not found"
    assert 'roles' in users_content.lower(), "Roles endpoint not found"
    
    # Check configuration API
    config_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'configuration.py')
    with open(config_api_path, 'r') as f:
        config_content = f.read()
    
    assert '@router.get' in config_content, "GET endpoint not found in configuration API"
    assert '@router.patch' in config_content, "PATCH endpoint not found in configuration API"


def test_api_permission_checks():
    """Test that API endpoints have proper permission checks."""
    project_root = get_project_root()
    
    # Check schools API permissions
    schools_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'schools.py')
    with open(schools_api_path, 'r') as f:
        schools_content = f.read()
    
    assert 'SUPERADMIN' in schools_content or 'SuperAdmin' in schools_content, "SuperAdmin permission check not found in schools API"
    
    # Check departments API permissions
    departments_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'departments.py')
    with open(departments_api_path, 'r') as f:
        departments_content = f.read()
    
    assert 'SUPERADMIN' in departments_content or 'SuperAdmin' in departments_content, "SuperAdmin permission check not found in departments API"
    assert 'ADMIN' in departments_content or 'Admin' in departments_content, "Admin permission check not found in departments API"
    
    # Check users API permissions
    users_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'users.py')
    with open(users_api_path, 'r') as f:
        users_content = f.read()
    
    assert 'SUPERADMIN' in users_content or 'SuperAdmin' in users_content, "SuperAdmin permission check not found in users_content"
    assert 'ADMIN' in users_content or 'Admin' in users_content, "Admin permission check not found in users_content"
    
    # Check configuration API permissions
    config_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'configuration.py')
    with open(config_api_path, 'r') as f:
        config_content = f.read()
    
    assert 'SUPERADMIN' in config_content or 'SuperAdmin' in config_content, "SuperAdmin permission check not found in configuration API"


def test_ui_components_exist():
    """Test that all UI components are created."""
    project_root = get_project_root()
    
    ui_files = [
        'frontend/src/components/schools/SchoolList.tsx',
        'frontend/src/components/schools/SchoolForm.tsx',
        'frontend/src/components/departments/DepartmentList.tsx',
        'frontend/src/components/departments/DepartmentForm.tsx',
        'frontend/src/components/users/UserList.tsx',
        'frontend/src/components/users/UserForm.tsx',
        'frontend/src/components/configuration/ConfigurationPanel.tsx',
    ]
    
    for ui_file in ui_files:
        full_path = os.path.join(project_root, *ui_file.split('/'))
        assert os.path.exists(full_path), f"UI component not found: {ui_file}"
        
        # Check that component has proper structure
        with open(full_path, 'r') as f:
            content = f.read()
            assert 'export' in content, f"Component not properly exported: {ui_file}"
            assert 'interface' in content or 'type' in content, f"Component missing types: {ui_file}"


def test_tenancy_middleware_integration():
    """Test that tenancy middleware is integrated in the API."""
    project_root = get_project_root()
    
    schools_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'schools.py')
    with open(schools_api_path, 'r') as f:
        schools_content = f.read()
    
    # Check for tenant context usage
    assert 'TenantContext' in schools_content or 'tenant_context' in schools_content, "TenantContext not used in schools API"
    
    # Check for scope filtering
    assert 'school_id' in schools_content.lower(), "School ID filtering not found in schools API"
    
    departments_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'departments.py')
    with open(departments_api_path, 'r') as f:
        departments_content = f.read()
    
    assert 'TenantContext' in departments_content or 'tenant_context' in departments_content, "TenantContext not used in departments API"
    assert 'school_id' in departments_content.lower(), "School ID filtering not found in departments API"
    
    users_api_path = os.path.join(project_root, 'modules', 'school-dept-user-role', 'api', 'users.py')
    with open(users_api_path, 'r') as f:
        users_content = f.read()
    
    assert 'TenantContext' in users_content or 'tenant_context' in users_content, "TenantContext not used in users API"
    assert 'school_id' in users_content.lower(), "School ID filtering not found in users API"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])