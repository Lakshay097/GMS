# School Operations & Governance Platform

A modular monolith platform for school operations and governance, built with FastAPI, Neon Postgres, and following the architecture specified in the `/specs` directory.

## Architecture

This platform follows a **modular monolith** architecture (Architecture §2, ADR-01) with service-oriented internal communication. Key architectural principles:

- **Row-level tenant isolation** using `school_id` and `department_id` (R-03, ADR-02)
- **Immutability** for critical entities (Observations, KPIs, Scorecards, Audit Logs)
- **Data-defined workflows** for state machines (Task, Discrepancy, Checklist)
- **Cross-cutting platform services** (Configuration Engine, Rule Engine, Workflow Engine, etc.)
- **Feature flags** for phased rollout per coding-standards.md §2

## Technology Stack

- **Database**: Neon (serverless PostgreSQL)
- **Authentication**: Neon Auth (Better Auth-backed)
- **Media Storage**: Cloudinary
- **Async Job Queue**: SQS (configurable via `QUEUE_PROVIDER`)
- **Cache/Session**: Redis-class store
- **Search Index**: OpenSearch/Elasticsearch-class
- **API**: REST with OpenAPI documentation
- **Framework**: FastAPI (Python 3.11)

## Project Structure

```
/
├── modules/                          # Business modules (PRS functional areas)
│   ├── school-dept-user-role/
│   ├── kra-kpi-library/
│   ├── observation-capture/
│   ├── audit-discrepancy/
│   ├── task-escalation/
│   ├── checklist-recurring/
│   ├── performance-scorecards/
│   ├── dashboards-reports-search/
│   ├── notifications/
│   └── settings-master-data/
├── platform_services/                # Cross-cutting platform services
│   ├── configuration_engine/
│   ├── rule_engine/
│   ├── workflow_engine/
│   ├── notification_service/
│   ├── audit_log_service/
│   ├── master_data_service/
│   ├── checklist_scheduler/
│   └── compliance_scheduler/
├── shared/                           # Shared utilities and middleware
│   ├── middleware/                   # Tenancy, permissions
│   ├── errors/                       # Error contract
│   ├── idempotency/                  # Idempotency middleware
│   ├── database.py                   # Database connection
│   ├── auth.py                       # Neon Auth integration
│   ├── media.py                      # Cloudinary integration
│   └── task_queue.py                 # Async job queue interface
├── api/                              # API gateway / BFF
│   └── main.py                       # FastAPI application entry point
├── migrations/                       # Alembic database migrations
├── tests/                            # Test suites
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── specs/                            # Read-only specification documents
├── .env.example                      # Environment configuration template
├── requirements.txt                  # Python dependencies
├── Dockerfile                        # Container image definition
├── docker-compose.yml                # Local development environment
└── alembic.ini                       # Alembic configuration
```

## Setup Instructions

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for local development)
- Neon account (for database and auth)
- Cloudinary account (for media storage)

### Environment Configuration

1. Copy the environment template:
   ```bash
   cp .env.example .env.dev
   ```

2. Fill in the required values in `.env.dev`:
   - `DATABASE_URL`: Neon connection string
   - `NEON_AUTH_PROJECT_ID`, `NEON_AUTH_SECRET_KEY`: Neon Auth credentials
   - `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`: Cloudinary credentials
   - `QUEUE_PROVIDER`: Set to `sqs` or `kafka` per env-and-secrets.md §5
   - `REDIS_URL`: Redis connection string
   - Other values as specified in `env-and-secrets.md`

### Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run database migrations:
   ```bash
   alembic upgrade head
   ```

### Running the Application

#### Local Development

Using Docker Compose:
```bash
docker-compose up
```

The API will be available at `http://localhost:8000`

#### Direct Python Execution

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### API Documentation

Once running, access the interactive API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Testing

### Run Unit Tests
```bash
pytest tests/unit/ -v
```

### Run Integration Tests
```bash
pytest tests/integration/ -v
```

### Run E2E Tests
```bash
pytest tests/e2e/ -v
```

### Run All Tests with Coverage
```bash
pytest tests/ -v --cov=. --cov-report=html
```

## CI/CD

The project includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that:

- Runs unit and integration tests on every PR
- Performs code quality checks (Black, isort, Flake8, mypy)
- Runs security scans with Trivy
- Builds Docker images
- Deploys to staging (develop branch) and production (main branch)
- Blocks merge on test failure per phases.md §1.5

## Module Boundary Rule

Per coding-standards.md §1:
- A module writes only to its own tables
- To read/write another module's data, call that module's internal service interface
- No direct cross-table writes between modules

## Feature Flags

Feature flags follow the naming convention: `<phase>.<module>.<capability>` per coding-standards.md §2.

Pre-defined Phase 1 flags are in `platform_services/configuration_engine/constants.py`. SMS/WhatsApp notifications are disabled by default pending cost approval (assumptions-log.md D2).

## Open Items

See `assumptions-log.md` for the current status of open items. Items marked `BLOCKING` are hard stops that must be resolved before proceeding with related features.

## Specifications

All specification documents are in the `/specs` directory and are read-only:
- `PRS_School_Governance_Platform_v1_5.md` - Product Requirements
- `Architecture.md` - System architecture
- `Data-Model.md` - Physical data model
- `API-Spec.md` - REST API specification
- `Design.md` - Design synthesis
- `phases.md` - Delivery roadmap
- `rules.md` - Binding rulebook (BR-xx, R-xx, AP#, ADR-xx, C#)
- `assumptions-log.md` - Open item resolutions
- `coding-standards.md` - Coding conventions
- `env-and-secrets.md` - Environment configuration
- `test-plan.md` - Test scenarios

## License

[To be determined]
