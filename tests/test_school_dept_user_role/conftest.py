"""
Pytest configuration and fixtures for school/department/user/configuration tests.
"""
import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from shared.database import Base
from shared.models import Permission
from shared.permissions import PermissionMatrix


@pytest.fixture(scope="function")
async def db_session():
    """
    Create a test database session for each test.
    Uses an in-memory SQLite database for fast testing.
    """
    # Create async engine for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Seed initial permissions
    async with async_session() as session:
        permission_matrix = PermissionMatrix()
        for module, action, role, scope, is_allowed in permission_matrix.INITIAL_PERMISSIONS:
            permission = Permission(
                module=module.value,
                action=action.value,
                role=role.value if hasattr(role, 'value') else str(role).lower(),
                scope_constraint=scope.value if scope else None,
                is_allowed=is_allowed
            )
            session.add(permission)
        await session.commit()
    
    # Provide session to test
    async with async_session() as session:
        yield session
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)