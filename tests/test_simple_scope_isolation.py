"""
Simple test to verify scope isolation works using the test SQLite database.
These are legacy raw-SQL tests; rewritten to use the shared ORM fixtures
so they run in-memory (fast, no external PostgreSQL dependency).
"""
import pytest
from sqlalchemy import select
from shared.models import School, User, UserRole, UserStatus, SchoolStatus
from shared.middleware.tenancy import apply_tenant_filter, TenantContext
import uuid


@pytest.mark.asyncio
async def test_scope_isolation(db):
    """Test that scope isolation prevents cross-school data access."""
    # Create two schools
    school_a = School(
        id=uuid.uuid4(),
        name="Simple School A",
        code=f"SIMPA{uuid.uuid4().hex[:4]}",
        status=SchoolStatus.ACTIVE
    )
    db.add(school_a)
    school_b = School(
        id=uuid.uuid4(),
        name="Simple School B",
        code=f"SIMPB{uuid.uuid4().hex[:4]}",
        status=SchoolStatus.ACTIVE
    )
    db.add(school_b)
    await db.flush()

    # Create one user per school
    user_a = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="simple_a@test.com",
        full_name="Simple User A",
        school_id=school_a.id,
        status=UserStatus.ACTIVE,
        roles=[UserRole.ADMIN.value]
    )
    db.add(user_a)
    user_b = User(
        id=uuid.uuid4(),
        clerk_user_id=f"clerk-test-{uuid.uuid4()}",
        email="simple_b@test.com",
        full_name="Simple User B",
        school_id=school_b.id,
        status=UserStatus.ACTIVE,
        roles=[UserRole.ADMIN.value]
    )
    db.add(user_b)
    await db.commit()

    # School A user query (tenant-filtered)
    tenant_a = TenantContext(
        user_id=str(user_a.id),
        school_id=str(school_a.id),
        department_id=None,
        roles=[UserRole.ADMIN.value]
    )
    q_a = apply_tenant_filter(select(User), tenant_a)
    users_a = (await db.execute(q_a)).scalars().all()
    assert user_a.id in {u.id for u in users_a}, "Should see own school user"
    assert user_b.id not in {u.id for u in users_a}, "Should NOT see other school user"

    # School B user query (tenant-filtered)
    tenant_b = TenantContext(
        user_id=str(user_b.id),
        school_id=str(school_b.id),
        department_id=None,
        roles=[UserRole.ADMIN.value]
    )
    q_b = apply_tenant_filter(select(User), tenant_b)
    users_b = (await db.execute(q_b)).scalars().all()
    assert user_b.id in {u.id for u in users_b}, "Should see own school user"
    assert user_a.id not in {u.id for u in users_b}, "Should NOT see other school user"
