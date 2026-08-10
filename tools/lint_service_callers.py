#!/usr/bin/env python3
"""
Service-Layer Authorization Guardrail

This script enforces the ADR-09 decision: only authorized callers may directly
import or instantiate the 15 audited core services. Unauthorized direct service
calls bypass API-layer authorization and are prohibited.

Authorized callers:
- API routes (*/api/*_routes.py)
- Background schedulers (compliance_scheduler/service.py, checklist_scheduler/service.py)
- Service-to-service calls (internal module communication per module boundary rule)
- Test files (tests/)

Run this script as part of CI to catch any new unauthorized service callers.
"""

import ast
import sys
from pathlib import Path
from typing import Set, List, Tuple


# The 15 audited services that require authorization checks at the API layer
PROTECTED_SERVICES = {
    "ConfigurationEngine": "platform_services/configuration_engine/service.py",
    "ApprovalChainService": "modules/audit_discrepancy/services/approval_chain_service.py",
    "DiscrepancyService": "modules/audit_discrepancy/services/discrepancy_service.py",
    "TaskService": "modules/task_management/services/task_service.py",
    "PerformanceReviewService": "modules/performance_scorecards/services/performance_review_service.py",
    "NotificationService": "platform_services/notification_service/service.py",
    "ObservationService": "modules/observation-capture/services/observation_service.py",
    "ComplianceScheduler": "platform_services/compliance_scheduler/service.py",
    "AuditLogService": "platform_services/audit_log_service/service.py",
    "WorkflowEngine": "platform_services/workflow_engine/service.py",
    "MasterDataService": "platform_services/master_data_service/service.py",
    "UserService": "modules/school-dept-user-role/services/user_service.py",
    "SchoolService": "modules/school-dept-user-role/services/school_service.py",
    "KpiService": "modules/kra-kpi-library/services/kpi_service.py",
    "DashboardService": "modules/dashboards-reports-search/services/dashboard_service.py",
}

# Authorized caller patterns (files that are allowed to call protected services)
AUTHORIZED_CALLER_PATTERNS = [
    # API routes - these enforce require_permission() middleware
    r"^.*/api/.*routes\.py$",
    
    # Background schedulers - system context, no human actor
    r"^platform_services/compliance_scheduler/service\.py$",
    r"^platform_services/checklist_scheduler/service\.py$",
    r"^modules/task_management/services/escalation_scheduler\.py$",  # Task escalation scheduler
    
    # Service-to-service calls - internal module communication per module boundary rule
    r"^modules/audit_discrepancy/services/discrepancy_service\.py$",  # Calls ApprovalChainService
    r"^modules/observation-capture/services/observation_service\.py$",  # Calls ConfigurationEngine, RuleEngine
    r"^modules/task_management/services/task_service\.py$",  # Calls NotificationService
    
    # Test files - allowed for testing purposes
    r"^tests/.*\.py$",
]

# Service files themselves are allowed to import themselves (for typing, etc.)
SERVICE_FILE_PATTERNS = [
    r"^platform_services/configuration_engine/service\.py$",
    r"^modules/audit_discrepancy/services/approval_chain_service\.py$",
    r"^modules/audit_discrepancy/services/discrepancy_service\.py$",
    r"^modules/task.*/services/task_service\.py$",  # Matches both task-escalation and task_management
    r"^modules/performance.*/services/performance_review_service\.py$",
    r"^platform_services/notification_service/service\.py$",
    r"^modules/observation.*/services/observation_service\.py$",
    r"^platform_services/compliance_scheduler/service\.py$",
    r"^platform_services/audit_log_service/service\.py$",
    r"^platform_services/workflow_engine/service\.py$",
    r"^platform_services/master_data_service/service\.py$",
    r"^modules/school.*/services/user_service\.py$",
    r"^modules/school.*/services/school_service\.py$",
    r"^modules/kra.*/services/kpi_service\.py$",
    r"^modules/dashboards.*/services/dashboard_service\.py$",
]

# Additional files that are part of the service modules (e.g., __init__.py, schemas.py)
SERVICE_MODULE_PATTERNS = [
    r"^platform_services/configuration_engine/.*\.py$",
    r"^modules/audit_discrepancy/.*\.py$",
    r"^modules/task.*/.*\.py$",  # Matches both task-escalation and task_management
    r"^modules/performance.*/.*\.py$",  # Matches performance-scorecards
    r"^platform_services/notification_service/.*\.py$",
    r"^modules/observation.*/.*\.py$",  # Matches observation-capture
    r"^platform_services/compliance_scheduler/.*\.py$",
    r"^platform_services/audit_log_service/.*\.py$",
    r"^platform_services/workflow_engine/.*\.py$",
    r"^platform_services/master_data_service/.*\.py$",
    r"^modules/school.*/.*\.py$",  # Matches school-dept-user-role
    r"^modules/kra.*/.*\.py$",  # Matches kra-kpi-library
    r"^modules/dashboards.*/.*\.py$",  # Matches dashboards-reports-search
    r"^modules/settings.*/.*\.py$",  # Matches settings_master_data
    r"^modules/checklist.*/.*\.py$",  # Matches checklist-recurring
    r"^modules/notifications/.*\.py$",
]

# Combine all allowed patterns
ALL_ALLOWED_PATTERNS = AUTHORIZED_CALLER_PATTERNS + SERVICE_FILE_PATTERNS + SERVICE_MODULE_PATTERNS


def is_authorized_caller(file_path: Path) -> bool:
    """Check if a file is an authorized caller of protected services."""
    import re
    
    # Get relative path from project root
    try:
        rel_path = file_path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        # File is outside project root, treat as unauthorized
        return False
    
    # Check against all allowed patterns
    for pattern in ALL_ALLOWED_PATTERNS:
        if re.match(pattern, rel_path):
            return True
    
    return False


def extract_service_imports(file_path: Path) -> Set[str]:
    """Extract imports of protected services from a Python file."""
    imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            # Check for direct imports: from ... import ServiceName
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in PROTECTED_SERVICES:
                        imports.add(alias.name)
            
            # Check for module imports: import module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    # Check if this import could be importing a protected service
                    for service_name, service_path in PROTECTED_SERVICES.items():
                        service_module = service_path.replace('/', '.').replace('/service.py', '')
                        if alias.name == service_module or alias.name.startswith(service_module + '.'):
                            imports.add(service_name)
    
    except (SyntaxError, UnicodeDecodeError):
        # Skip files that can't be parsed
        pass
    
    return imports


def check_file(file_path: Path) -> List[Tuple[str, str]]:
    """Check a single file for unauthorized service imports."""
    violations = []
    
    # Skip if this is an authorized caller
    if is_authorized_caller(file_path):
        return violations
    
    # Extract service imports
    service_imports = extract_service_imports(file_path)
    
    # Report violations
    for service_name in service_imports:
        violations.append((str(file_path), service_name))
    
    return violations


def scan_project(root_dir: Path) -> List[Tuple[str, str]]:
    """Scan all Python files in the project for unauthorized service imports."""
    all_violations = []
    
    # Find all Python files
    for py_file in root_dir.rglob('*.py'):
        # Skip the lint script itself
        if py_file.name == 'lint_service_callers.py':
            continue
        
        violations = check_file(py_file)
        all_violations.extend(violations)
    
    return all_violations


def main():
    """Main entry point."""
    root_dir = Path.cwd()
    
    print(f"Scanning project for unauthorized service imports...")
    print(f"Project root: {root_dir}")
    print(f"Protected services: {len(PROTECTED_SERVICES)}")
    print(f"Authorized caller patterns: {len(AUTHORIZED_CALLER_PATTERNS)}")
    print()
    
    violations = scan_project(root_dir)
    
    if violations:
        print("X VIOLATIONS FOUND:")
        print("=" * 80)
        for file_path, service_name in violations:
            service_location = PROTECTED_SERVICES.get(service_name, "unknown")
            print(f"  {file_path}")
            print(f"    -> Unauthorized import of {service_name} ({service_location})")
            print()
        
        print("=" * 80)
        print(f"Total violations: {len(violations)}")
        print()
        print("To fix this violation:")
        print("1. If this is a new API route, ensure it follows the pattern */api/*_routes.py")
        print("2. If this is a new scheduler, add its path to AUTHORIZED_CALLER_PATTERNS")
        print("3. If this is a new service-to-service call, add its path to AUTHORIZED_CALLER_PATTERNS")
        print("4. If this is a test file, ensure it's under tests/")
        print("5. Otherwise, refactor to call the service through the API layer")
        print()
        print("See ADR-09: Service-Layer Authorization Boundary for context.")
        
        sys.exit(1)
    else:
        print("OK No violations found. All service imports are from authorized callers.")
        sys.exit(0)


if __name__ == '__main__':
    main()