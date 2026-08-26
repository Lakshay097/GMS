# Platform Services Documentation

## Overview

Cross-cutting platform services provide shared functionality across all business modules. They are located in the `platform_services/` directory and follow the snake_case naming convention.

## Directory Structure

```
platform_services/
├── __init__.py
├── interfaces.py                # Service interface contracts
├── configuration_engine/        # Configuration Engine
├── rule_engine/                 # Rule Engine
├── workflow_engine/             # Workflow Engine
├── notification_service/        # Notification Service
├── audit_log_service/           # Audit Log Service
├── master_data_service/         # Master Data Service
├── checklist_scheduler/         # Checklist Scheduler
└── compliance_scheduler/        # Compliance Scheduler
```

> **Note**: The platform services use **snake_case** directory names (e.g., `configuration_engine`) rather than the kebab-case specified in some specs documents. This is a deliberate deviation to ensure Python import compatibility. The specs documents have been updated to reflect this convention.

## Services

### 1. Configuration Engine

**Path**: `platform_services/configuration_engine/`
**Files**: `service.py`, `constants.py`, `__init__.py`

**Purpose**: Manages global and school-scoped configuration.

**Key Features**:
- Global configuration defaults
- School-scoped configuration overrides
- Configuration scope tiers (global default + school override)
- Feature flag definitions in `constants.py`

**Integration**: Used by `modules/school-dept-user-role/services/configuration_service.py`

### 2. Rule Engine

**Path**: `platform_services/rule_engine/`
**Files**: `service.py`, `strategies.py`, `kpi_calculation.py`, `__init__.py`

**Purpose**: Evaluates business rules and calculates KPI values.

**Key Features**:
- KPI calculation logic in `kpi_calculation.py`
- Strategy pattern for different rule types in `strategies.py`
- Rule evaluation service

### 3. Workflow Engine

**Path**: `platform_services/workflow_engine/`
**Files**: `service.py`, `__init__.py`

**Purpose**: Manages state machine transitions for workflows.

**Key Features**:
- Data-defined workflow state machines
- Transition validation
- Workflow lifecycle management

### 4. Notification Service

**Path**: `platform_services/notification_service/`
**Files**: `service.py`, `providers.py`, `localization.py`, `__init__.py`

**Purpose**: Sends notifications across multiple channels.

**Key Features**:
- Multiple provider support (Email, SMS, WhatsApp) in `providers.py`
- Email provider integrated with Resend API
- Notification delivery service
- SMS/WhatsApp disabled by default pending cost approval
- Localization support for notification templates

**Configuration**:
- `EMAIL_PROVIDER_API_KEY`: Resend API key
- `EMAIL_FROM`: Sender email address (default: onboarding@resend.dev)

### 5. Audit Log Service

**Path**: `platform_services/audit_log_service/`
**Files**: `service.py`, `event_types.py`, `__init__.py`

**Purpose**: Provides append-only audit logging.

**Key Features**:
- Event type definitions in `event_types.py`
- Append-only audit entries (R-19)
- Permanent audit history retention

### 6. Master Data Service

**Path**: `platform_services/master_data_service/`
**Files**: `service.py`, `__init__.py`

**Purpose**: Manages reference/master data.

**Key Features**:
- Default department templates
- Reference data management
- Simplified for Phase 1

### 7. Checklist Scheduler

**Path**: `platform_services/checklist_scheduler/`
**Files**: `service.py`, `__init__.py`

**Purpose**: Generates recurring checklist instances.

**Key Features**:
- Recurring checklist generation
- Schedule-based instance creation

### 8. Compliance Scheduler

**Path**: `platform_services/compliance_scheduler/`
**Files**: `service.py`, `holiday_resolver.py`, `__init__.py`

**Purpose**: Generates KPI compliance-cycle records (PRS §23.16-23.17).

**Key Features**:
- KPI compliance-cycle record generation
- Holiday resolution in `holiday_resolver.py`
- Distinct from checklist-scheduler; generates KPI compliance-cycle records, not ChecklistInstances

## Service Interfaces

The `platform_services/interfaces.py` file defines the service interface contracts. Each platform service implements these interfaces to ensure consistent integration.

## Integration Pattern

Business modules integrate with platform services through their service interfaces:

```python
# Example: Using Configuration Engine from a module service
from platform_services.configuration_engine.service import ConfigurationEngine

config_engine = ConfigurationEngine()
timezone = await config_engine.get_school_config(school_id, "timezone")
```

## Testing

Unit tests for platform services are in `tests/unit/`:
- `test_configuration_engine.py`
- `test_rule_engine.py`
- `test_workflow_engine.py`
- `test_notification_service.py`
- `test_audit_log_service.py`
- `test_master_data_service.py`
- `test_checklist_scheduler.py`
- `test_compliance_scheduler.py`
- `test_kpi_calculation.py`

Integration tests for service contracts are in `tests/integration/test_platform_service_contracts.py`.
