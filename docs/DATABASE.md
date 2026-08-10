# Database Documentation

## Overview

The platform uses **Neon** (serverless PostgreSQL) as its primary database. Database access is handled through SQLAlchemy 2.0 async ORM with Alembic for migrations.

## Connection Management

### Configuration (`shared/database.py`)

The database connection is configured via the `DATABASE_URL` environment variable.

```
python
DATABASE_URL = os.getenv("DATABASE_URL")
```

### Async URL Conversion

The system automatically converts a standard PostgreSQL URL to an async-compatible URL:

```
postgresql:// → postgresql+asyncpg://
```

### Connection Pooling

```python
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("LOG_LEVEL", "info") == "debug",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
```

- **Pool size**: 10 connections
- **Max overflow**: 20
- **Pool pre-ping**: Enabled (checks connection health)

### Session Management

```
python
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
```

### FastAPI Dependency

The `get_db` dependency provides a database session to API endpoints:

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

## Migrations

### Alembic Configuration

- **Config file**: `alembic.ini`
- **Migration directory**: `migrations/`
- **Environment**: `migrations/env.py`

### Migration Versions

```
migrations/versions/
├── 20260806_1509_4e2ed61991ff_initial_schema_users_roles_schools_.py
├── 20260807_kra_kpi_library.py
└── 20260807_platform_services.py
```

### Running Migrations

```
bash
alembic upgrade head
```

### Creating New Migrations

```
bash
alembic revision --autogenerate -m "description"
```

## Data Model

### Core Entities

The data model follows the specs in `specs/Data-Model.md`. Key entities include:

- **Schools** - Educational institutions
- **Departments** - Departments within schools
- **Users** - Platform users with roles
- **UserSchoolGrants** - Multi-school access grants for Viewers
- **KRAs** - Key Result Areas
- **KPIs** - Key Performance Indicators
- **Observations** - KPI observations with auto-results
- **AuditLogEntries** - Append-only audit trail

### Row-Level Tenant Isolation (R-03, ADR-02)

Every table includes `school_id` and `department_id` columns for tenant isolation:

- SuperAdmin has access to all schools
- Viewer has multi-school access via `user_school_grants`
- Other roles are filtered by primary `school_id`

### Immutability

Critical entities (Observations, KPIs, Scorecards, Audit Logs) are append-only:
- No hard deletes
- Soft lifecycle (active/archived/deactivated)
- Full audit history retained permanently

## ORM Models

### Base Class

```python
Base = declarative_base()
```

### Shared Models (`shared/models.py`)

Defines shared models and enums such as:
- `UserRole` - Role enum (superadmin, admin, staff, viewer)
- `SchoolStatus` - School lifecycle status
- `UserStatus` - User lifecycle status
- `DepartmentStatus` - Department lifecycle status

### Platform Models (`shared/platform_models.py`)

Defines platform-wide models.

## Initialization

### Database Initialization

```
python
async def init_db():
    """Initialize database - create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

> **Note**: In production, use Alembic migrations instead of `init_db()`.

### Shutdown

```python
async def close_db():
    """Close database connections."""
    await engine.dispose()
```

## Environment Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `LOG_LEVEL` | Logging level (debug enables SQL echo) |

### Example `.env` Configuration

```
DATABASE_URL=postgresql+asyncpg://user:password@host/database
LOG_LEVEL=info
```

## Testing

Tests use SQLite (aiosqlite) for unit testing:

```
python
# tests/conftest.py
# Uses aiosqlite for in-memory testing
```

Key test files:
- `tests/conftest.py` - Test fixtures and setup
- `tests/test_school_dept_user_role/conftest.py` - Module-specific fixtures
- `tests/unit/` - Unit tests for platform services
