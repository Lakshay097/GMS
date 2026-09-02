"""
Test fixtures for E2E tests.
Uses in-memory SQLite for fast, isolated test runs with memory queue.
"""
from __future__ import annotations

import os
import uuid

# Pin memory queue BEFORE shared imports (they call load_dotenv and would
# otherwise freeze QUEUE_PROVIDER=sqs from .env into the process).
os.environ["QUEUE_PROVIDER"] = "memory"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

import pytest
import pytest_asyncio
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import sqlite3
from sqlalchemy.ext.compiler import compiles

from shared.database import Base
from shared.datetime_utils import utc_now

# Register UUID adapter for SQLite (aiosqlite can't bind UUID objects directly)
sqlite3.register_adapter(uuid.UUID, lambda u: u.hex)
from shared.models import Department, DepartmentStatus, School, SchoolStatus, User, UserStatus
from shared.platform_models import KPI, KRA, ConfigurationItem
from shared.task_queue import InMemoryQueue, reset_queue_instance

reset_queue_instance()


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def memory_queue():
    return InMemoryQueue()


@pytest_asyncio.fixture
async def school(db: AsyncSession):
    school = School(
        id=uuid.uuid4(),
        name="Test School",
        code="TST001",
        status=SchoolStatus.ACTIVE,
        timezone="Asia/Kolkata",
        working_days=["mon", "tue", "wed", "thu", "fri"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(school)
    await db.commit()
    return school


@pytest_asyncio.fixture
async def department(db: AsyncSession, school: School):
    dept = Department(
        id=uuid.uuid4(),
        school_id=school.id,
        name="Operations",
        code="OPS",
        status=DepartmentStatus.ACTIVE,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(dept)
    await db.commit()
    return dept


@pytest_asyncio.fixture
async def user(db: AsyncSession, school: School, department: Department):
    user = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email=f"user-{uuid.uuid4()}@test.com",
        full_name="Test User",
        school_id=school.id,
        department_id=department.id,
        status=UserStatus.ACTIVE,
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(user)
    await db.commit()
    return user


@pytest_asyncio.fixture
async def kpi(db: AsyncSession):
    kra = KRA(id=uuid.uuid4(), name="Test KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Daily Compliance KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    return kpi


@pytest_asyncio.fixture
async def seed_configuration(db: AsyncSession):
    """Seed configuration items for tests."""
    from platform_services.configuration_engine.constants import CONFIG_DEFINITIONS, ConfigKey
    
    for config_key, definition in CONFIG_DEFINITIONS.items():
        existing = await db.get(ConfigurationItem, config_key)
        if existing is None:
            db.add(
                ConfigurationItem(
                    config_key=config_key,
                    value_type=definition["value_type"],
                    global_default=definition["global_default"],
                    editable_by=definition["editable_by"],
                    overridable_scope=definition["overridable_scope"],
                )
            )
    await db.commit()