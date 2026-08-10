# Architecture Documentation

## Overview

The School Operations & Governance Platform is a **modular monolith** built with FastAPI (Python 3.11) and React (TypeScript). It follows a service-oriented internal communication pattern with row-level tenant isolation.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                     │
│                    frontend/src/ (Vite + TS)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP /api/v1/*
┌──────────────────────────▼──────────────────────────────────┐
│                     API Gateway (FastAPI)                   │
│                        api/main.py                          │
│  ┌──────────────┬──────────────┬─────────────────────────┐  │
│  │ Auth Router  │ Module APIs  │ Platform Service APIs   │  │
│  │ api/auth.py  │ modules/*/   │ platform_services/*/    │  │
│  └──────────────┴──────────────┴─────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Shared Layer (shared/)                   │
│  • Database (SQLAlchemy async)  • Auth (Neon Auth)          │
│  • Middleware (tenancy, permissions)  • Errors              │
│  • Idempotency  • Task Queue  • Media (Cloudinary)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Data Layer (PostgreSQL)                  │
│                    Neon (serverless)                        │
└─────────────────────────────────────────────────────────────┘
```

## Key Architectural Principles

### 1. Modular Monolith (ADR-01)
- All modules share a single codebase and database
- Modules communicate through internal service interfaces
- Phase 3 service extraction is a deployment change, not a rewrite

### 2. Row-Level Tenant Isolation (R-03, ADR-02)
- Every table includes `school_id` and `department_id` columns
- The tenancy middleware (`shared/middleware/tenancy.py`) enforces mandatory query-layer filtering
- SuperAdmin has access to all schools
- Viewer can have multi-school access via `user_school_grants`
- Other roles are filtered by their primary `school_id`

### 3. Immutability
- Critical entities (Observations, KPIs, Scorecards, Audit Logs) are append-only
- No hard deletes on core entities - only soft lifecycle (active/archived/deactivated)
- Full audit history retained permanently

### 4. Data-Defined Workflows
- State machines for Task, Discrepancy, and Checklist are data-driven
- Workflow transitions are validated by the Workflow Engine

### 5. Cross-Cutting Platform Services
Eight platform services provide shared functionality:
1. **Configuration Engine** - Global and school-scoped configuration
2. **Rule Engine** - KPI calculation and business rules
3. **Workflow Engine** - State machine transitions
4. **Notification Service** - Email/SMS/WhatsApp notifications
5. **Audit Log Service** - Append-only audit trail
6. **Master Data Service** - Reference data management
7. **Checklist Scheduler** - Recurring checklist generation
8. **Compliance Scheduler** - KPI compliance-cycle records

## Directory Structure

```
/
├── api/                          # API gateway / BFF
│   ├── main.py                   # FastAPI application entry point
│   └── auth.py                   # Authentication router
├── modules/                      # Business modules (PRS functional areas)
│   ├── school-dept-user-role/    # PRS §18-21
│   ├── kra-kpi-library/          # PRS §22-23
│   ├── observation-capture/      # PRS §24
│   ├── audit-discrepancy/        # PRS §25-26
│   ├── task-escalation/          # PRS §27
│   ├── checklist-recurring/      # PRS §23-new, §27 extension
│   ├── performance-scorecards/   # PRS §28-29
│   ├── dashboards-reports-search/ # PRS §30-31, §33
│   ├── notifications/            # PRS §32
│   └── settings-master-data/     # PRS §34-35
├── platform_services/            # Cross-cutting platform services
│   ├── configuration_engine/
│   ├── rule_engine/
│   ├── workflow_engine/
│   ├── notification_service/
│   ├── audit_log_service/
│   ├── master_data_service/
│   ├── checklist_scheduler/
│   └── compliance_scheduler/
├── shared/                       # Shared utilities and middleware
│   ├── middleware/               # Tenancy, permissions
│   ├── errors/                   # Error contract
│   ├── idempotency/              # Idempotency middleware
│   ├── database.py               # Database connection
│   ├── auth.py                   # Neon Auth integration
│   ├── media.py                  # Cloudinary integration
│   └── task_queue.py             # Async job queue interface
├── frontend/                     # React frontend
│   └── src/
│       ├── components/           # UI components
│       ├── lib/                  # Frontend utilities
│       └── App.tsx               # Main app with routing
├── migrations/                   # Alembic database migrations
├── tests/                        # Test suites
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── specs/                        # Read-only specification documents
└── docs/                         # This documentation
```

## Module Boundary Rule

Per coding-standards.md §1:
- A module writes only to its own tables
- To read/write another module's data, call that module's internal service interface
- No direct cross-table writes between modules

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (Python 3.11) |
| Database | Neon (serverless PostgreSQL) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Authentication | Neon Auth (Better Auth-backed) |
| Media Storage | Cloudinary |
| Async Job Queue | SQS (configurable via `QUEUE_PROVIDER`) |
| Cache/Session | Redis-class store |
| Search Index | OpenSearch/Elasticsearch-class |
| Frontend | React 19 + TypeScript + Vite |
| API Docs | OpenAPI (Swagger UI, ReDoc) |

## API Versioning

- All endpoints are under `/api/v1/...`
- OpenAPI documentation is auto-generated from source annotations
- The API version is defined in `api/main.py` as `API_VERSION = "1.0.0"`

## Error Handling

All errors follow the shared error contract in `shared/errors/`:
- 400: Validation error
- 401: Authentication error
- 403: Permission/scope error
- 404: Not found (deliberately indistinguishable from not-visible)
- 409: Conflict/immutability violation
- 422: Business-rule violation
- 500: Internal error (always logged to Audit Log)

## Feature Flags

Feature flags follow the naming convention: `<phase>.<module>.<capability>`
- Defined in `platform_services/configuration_engine/constants.py`
- Default to off in Production until explicitly enabled per school
