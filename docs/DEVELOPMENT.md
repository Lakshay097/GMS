# Development Guide

## Overview

This guide covers the development workflow for the School Operations & Governance Platform, including setup, running locally, testing, and contributing.

## Prerequisites

- Python 3.11+
- Node.js 20+ (for frontend)
- pnpm 9+ (package manager for frontend)
- Docker and Docker Compose (for local development)
- Neon account (for database and auth)
- Cloudinary account (for media storage)

## Setup

### 1. Clone the Repository

```
bash
git clone <repository-url>
cd SchoolOP
```

### 2. Backend Setup

Create a virtual environment:

```
bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Install Python dependencies:

```
bash
pip install -r requirements.txt
```

### 3. Frontend Setup

```
bash
cd frontend
pnpm install
cd ..
```

### 4. Environment Configuration

Copy the environment template:

```
bash
cp .env.example .env.dev
```

Fill in the required values in `.env.dev`:
- `DATABASE_URL`: Neon connection string
- `NEON_AUTH_BASE_URL`, `NEON_AUTH_COOKIE_SECRET`: Neon Auth credentials
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`: Cloudinary credentials
- `QUEUE_PROVIDER`: Set to `sqs` or `kafka` per env-and-secrets.md §5
- `REDIS_URL`: Redis connection string

For the frontend, create `frontend/.env`:
```
VITE_NEON_AUTH_URL=https://your-neon-auth-url
```

### 5. Database Migrations

```
bash
alembic upgrade head
```

## Running the Application

### Backend

#### Using Docker Compose

```
bash
docker-compose up
```

The API will be available at `http://localhost:8000`

#### Direct Python Execution

```
bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```
bash
cd frontend
pnpm dev
```

The app will be available at the Vite dev server URL (typically `http://localhost:5173`).

### Accessing API Documentation

Once the backend is running:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Testing

### Run Unit Tests

```
bash
pytest tests/unit/ -v
```

### Run Integration Tests

```
bash
pytest tests/integration/ -v
```

### Run E2E Tests

```
bash
pytest tests/e2e/ -v
```

### Run All Tests with Coverage

```
bash
pytest tests/ -v --cov=. --cov-report=html
```

## Code Quality

The project uses the following tools:
- **Black** - Code formatting
- **isort** - Import sorting
- **Flake8** - Linting
- **mypy** - Type checking

Configuration is in `pyproject.toml`.

### Run Code Quality Checks

```
bash
black --check .
isort --check-only .
flake8 .
mypy .
```

## Project Conventions

### Directory Naming

- **Business modules**: kebab-case (e.g., `school-dept-user-role`)
- **Platform services**: snake_case (e.g., `configuration_engine`)
- **Shared utilities**: snake_case (e.g., `task_queue.py`)

> **Note**: Platform services use snake_case directory names to ensure Python import compatibility, even though some spec documents reference kebab-case. See `docs/PLATFORM_SERVICES.md` for details.

### Module Structure

Each module follows:
```
modules/<module-name>/
├── __init__.py
├── api/                  # API layer (FastAPI routers)
├── services/             # Service layer (business logic)
├── models/               # Database models (if module-specific)
└── schemas.py            # Pydantic schemas
```

### Module Boundary Rule

- A module writes only to its own tables
- To read/write another module's data, call that module's internal service interface
- No direct cross-table writes between modules

### API Conventions

- All endpoints under `/api/v1/...`
- OpenAPI-documented from source annotations
- List endpoints use pagination envelope: `{ "data": [...], "pagination": {...} }`
- Errors follow shared contract in `shared/errors/`

### Role Values

Role values are lowercase: `superadmin`, `admin`, `staff`, `viewer`

## CI/CD

The project includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that:
- Runs unit and integration tests on every PR
- Performs code quality checks (Black, isort, Flake8, mypy)
- Runs security scans with Trivy
- Builds Docker images
- Deploys to staging (develop branch) and production (main branch)
- Blocks merge on test failure per phases.md §1.5

## Troubleshooting

### Database Connection Issues

- Ensure `DATABASE_URL` is set correctly in `.env.dev`
- Verify the Neon database is accessible
- Check that migrations have been run: `alembic upgrade head`

### Frontend-Backend Connection Issues

- Ensure the backend is running on port 8000
- Configure the Vite proxy in `frontend/vite.config.ts` to forward `/api` requests:
  
```typescript
  export default defineConfig({
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true
        }
      }
    }
  })
  
```
- Ensure the `VITE_NEON_AUTH_URL` environment variable is set

### Import Errors

- Ensure the project root is in the Python path (handled by `api/main.py`)
- Verify module registration in `modules/__init__.py` for hyphenated module folders
- Use snake_case imports for platform services (e.g., `from platform_services.configuration_engine.service import ConfigurationEngine`)

## Learn More

- `docs/ARCHITECTURE.md` - System architecture
- `docs/API.md` - API reference
- `docs/MODULES.md` - Business modules
- `docs/PLATFORM_SERVICES.md` - Platform services
- `docs/DATABASE.md` - Database documentation
- `docs/FRONTEND.md` - Frontend documentation
- `specs/` - Read-only specification documents
