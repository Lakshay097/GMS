# Business Modules Documentation

## Overview

The platform is organized into business modules following the PRS (Product Requirements Specification) functional areas. Each module follows the modular monolith architecture with strict module boundary rules.

## Module Structure

Each module follows a consistent structure:
```
modules/<module-name>/
├── __init__.py           # Module registration
├── api/                  # API layer (FastAPI routers)
│   ├── __init__.py
│   └── routes.py         # Endpoint definitions
├── services/             # Service layer (business logic)
│   ├── __init__.py
│   └── <service>.py
├── models/               # Database models (if module-specific)
│   └── __init__.py
└── schemas.py            # Pydantic schemas
```

## Module Registration

Hyphenated module folders are registered under dotted import names via `modules/__init__.py`:

```python
_register_dash_module("modules.school_dept_user_role", "school-dept-user-role")
_register_dash_module("modules.kra_kpi_library", "kra-kpi-library")
```

This allows imports like `from modules.school_dept_user_role.api.schools import router` even though the folder is named `school-dept-user-role`.

## Implemented Modules

### 1. School-Dept-User-Role (PRS §18-21)

**Purpose**: School management, department management, user management, and configuration management.

**API Layer**: `modules/school-dept-user-role/api/`
- `schools.py` - School CRUD + lifecycle
- `departments.py` - Department CRUD + lifecycle
- `users.py` - User CRUD + lifecycle
- `configuration.py` - Global and school-scoped configuration

**Service Layer**: `modules/school-dept-user-role/services/`
- `school_service.py` - School business logic
- `department_service.py` - Department business logic
- `user_service.py` - User business logic
- `configuration_service.py` - Configuration business logic

**Models**: `modules/school-dept-user-role/models/`

**Key Features**:
- School creation restricted to SuperAdmin only (FR-001)
- Atomic school creation with default departments and KPI library import (FR-006)
- School name uniqueness validation (FR-005)
- School deactivation (soft delete, never hard delete) (FR-007)
- Department belongs to exactly one School (FR-011)
- Department name uniqueness within school (FR-012)
- Department archival (not delete) with historical record preservation (FR-013)
- User never hard-deleted, only archived (FR-021)
- Multiple concurrent roles per user (FR-023)
- Email and phone uniqueness validation (FR-024)
- Global configuration managed only by SuperAdmin (R-44)

**UI Components**: `frontend/src/components/{schools,departments,users,configuration}/`

### 2. KRA-KPI-Library (PRS §22-23)

**Purpose**: Key Result Areas (KRAs) and Key Performance Indicators (KPIs) management.

**API Layer**: `modules/kra-kpi-library/api/routes.py`

**Service Layer**: `modules/kra-kpi-library/services/`
- `kra_service.py` - KRA business logic
- `kpi_service.py` - KPI business logic

**Schemas**: `modules/kra-kpi-library/schemas.py`

**Key Features**:
- KRA creation/update (SuperAdmin only)
- KPI creation/update with versioning
- KPI deprecation
- KPI import from seed file
- KPI assignment to departments
- Observation submission with auto-result calculation

### 3. Observation-Capture (PRS §24)

**Purpose**: Capture and manage observations for KPIs.

**Status**: Placeholder module (not yet implemented)

### 4. Audit-Discrepancy (PRS §25-26)

**Purpose**: Audit management and discrepancy resolution.

**Status**: Placeholder module (not yet implemented)

### 5. Task-Escalation (PRS §27)

**Purpose**: Task management and escalation workflows.

**Status**: Placeholder module (not yet implemented)

### 6. Checklist-Recurring (PRS §23-new, §27 extension)

**Purpose**: Recurring checklist generation and management.

**Status**: Placeholder module (not yet implemented)

### 7. Performance-Scorecards (PRS §28-29)

**Purpose**: Performance scorecard generation and management.

**Status**: Placeholder module (not yet implemented)

### 8. Dashboards-Reports-Search (PRS §30-31, §33)

**Purpose**: Dashboards, reports, and search functionality.

**Status**: Placeholder module (not yet implemented)

### 9. Notifications (PRS §32)

**Purpose**: User notification preferences and delivery.

**Status**: Placeholder module (not yet implemented)

### 10. Settings-Master-Data (PRS §34-35)

**Purpose**: Settings and master data management (Discrepancy Category, Holiday Calendar, Working Days, Asset).

**Status**: Placeholder module (not yet implemented)

## Module Boundary Rule

Per coding-standards.md §1:
- A module writes only to its own tables
- To read/write another module's data, call that module's internal service interface
- No direct cross-table writes between modules

## Integration with Platform Services

Modules integrate with platform services through their service interfaces:
- **Configuration Engine**: School timezone, working days, configuration management
- **Audit Log Service**: All lifecycle operations logged via append-only audit entries
- **Master Data Service**: Default department templates, reference data
- **Rule Engine**: KPI calculation and business rules
- **Workflow Engine**: State machine transitions
- **Notification Service**: User notifications
- **Checklist Scheduler**: Recurring checklist generation
- **Compliance Scheduler**: KPI compliance-cycle records

## Testing

Each module has corresponding tests in `tests/`:
- `tests/test_school_dept_user_role/` - School/Dept/User/Role module tests
- `tests/unit/` - Unit tests for platform services
- `tests/integration/` - Integration tests
- `tests/e2e/` - End-to-end workflow tests
