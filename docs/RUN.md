# Run Guide

Quick reference for running the School Operations & Governance Platform locally.

## Prerequisites

- Python 3.11+
- Node.js 20+
- pnpm 9+
- Docker and Docker Compose (optional)
- Neon account (database)
- Cloudinary account (media storage)

## Quick Start

### 1. Environment Setup

```bash
# Copy environment template
cp .env.example .env.dev

# Edit .env.dev with your credentials:
# - DATABASE_URL (Neon connection string)
# - NEON_AUTH_BASE_URL, NEON_AUTH_COOKIE_SECRET
# - CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
# - QUEUE_PROVIDER (memory, sqs, kafka, upstash-qstash, redis)
# - REDIS_URL (if using Redis)
```

For frontend, create `frontend/.env`:
```bash
VITE_NEON_AUTH_URL=https://your-neon-auth-url
```

### 2. Install Dependencies

```bash
# Backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
pnpm install
cd ..
```

### 3. Database Migrations

```bash
alembic upgrade head
```

## Running the Application

### Option A: Docker Compose (Recommended)

```bash
docker-compose up
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173 (if configured)
- API Docs: http://localhost:8000/docs

### Option B: Manual Start

#### Backend

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend (Separate Terminal)

```bash
cd frontend
pnpm dev
```

Frontend will be available at the Vite dev server URL (typically http://localhost:5173).

## API Documentation

Once the backend is running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Health Check

```bash
curl http://localhost:8000/health
```

## Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# E2E tests
pytest tests/e2e/ -v

# All tests with coverage
pytest tests/ -v --cov=. --cov-report=html
```

## Code Quality Checks

```bash
black --check .
isort --check-only .
flake8 .
mypy .
```

## Common Issues

### Database Connection Failed
- Verify `DATABASE_URL` in `.env.dev`
- Check Neon database is accessible
- Run migrations: `alembic upgrade head`

### Frontend Cannot Connect to Backend
- Ensure backend is running on port 8000
- Check Vite proxy configuration in `frontend/vite.config.ts`
- Verify `VITE_NEON_AUTH_URL` is set

### Import Errors
- Ensure virtual environment is activated
- Verify project root is in Python path
- Check module registration in `modules/__init__.py`

## Stopping the Application

### Docker Compose
```bash
docker-compose down
```

### Manual
- Press Ctrl+C in each terminal

## Additional Resources

- **Development Guide**: docs/DEVELOPMENT.md
- **Deployment Guide**: docs/DEPLOYMENT-GUIDE.md
- **Architecture**: docs/ARCHITECTURE.md
- **API Reference**: docs/API.md
