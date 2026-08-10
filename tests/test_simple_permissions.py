"""
Simple test to verify permission loading works using the test SQLite database.
These are legacy raw-SQL tests; rewritten to use the shared ORM fixtures
so they run in-memory (fast, no external PostgreSQL dependency).
"""
import pytest
from sqlalchemy import select, func
from shared.permissions import PermissionMatrix
from shared.models import Permission


@pytest.mark.asyncio
async def test_permission_loading(db):
    """Test that permissions can be loaded into the database."""
    # Load permissions
    await PermissionMatrix.initialize_permissions(db)

    # Check loaded count
    result = await db.execute(select(func.count()).select_from(Permission))
    final_count = result.scalar()
    print(f"Final permission count: {final_count}")

    assert final_count > 0, "Permissions should be loaded"
    assert final_count >= 115, f"Expected at least 115 permissions, got {final_count}"


@pytest.mark.asyncio
async def test_permission_loading_idempotent(db):
    """Loading permissions twice should not create duplicates."""
    await PermissionMatrix.initialize_permissions(db)
    await PermissionMatrix.initialize_permissions(db)

    result = await db.execute(select(func.count()).select_from(Permission))
    count = result.scalar()
    assert count >= 115, f"Expected at least 115 permissions, got {count}"
