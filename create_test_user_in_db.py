"""
Create a test user in our database that matches the Clerk user
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.models import User, UserStatus, UserRole, School, SchoolStatus
from shared.datetime_utils import utc_now
from shared.database import get_db
from uuid import uuid4
import os

# Clerk user ID from our test - will be updated dynamically
CLERK_USER_ID = None

async def create_test_user():
    """Create a test user that matches our Clerk test user"""
    async for session in get_db():
        try:
            # First, check if we have a school to use
            school_result = await session.execute(
                select(School).where(School.code == "GUR-JAI")
            )
            school = school_result.scalar_one_or_none()

            if not school:
                print("No school found with code GUR-JAI, creating one...")
                school = School(
                    id=uuid4(),
                    name="Test School for Clerk Migration",
                    code="GUR-JAI",
                    status=SchoolStatus.ACTIVE,
                    created_at=utc_now(),
                    updated_at=utc_now()
                )
                session.add(school)
                await session.commit()
                await session.refresh(school)
                school_id = school.id
                print(f"Created school with ID: {school_id}")
            else:
                school_id = school.id
                print(f"Using existing school with ID: {school_id}")

            # Check if we have the clerk_user_id set
            global CLERK_USER_ID
            if not CLERK_USER_ID:
                print("No CLERK_USER_ID set, using a placeholder")
                CLERK_USER_ID = f"manual-test-{os.urandom(8).hex()}"

            # Check if user already exists by clerk_user_id
            user_result = await session.execute(
                select(User).where(User.clerk_user_id == CLERK_USER_ID)
            )
            existing_user = user_result.scalar_one_or_none()

            if existing_user:
                print(f"User already exists with ID: {existing_user.id}")
                return existing_user.id

            # Create test user with unique email
            test_user = User(
                id=uuid4(),
                clerk_user_id=CLERK_USER_ID,
                email=f"test-clerk-{CLERK_USER_ID.split('_')[-1] if '_' in CLERK_USER_ID else CLERK_USER_ID}@example.com",
                full_name="Test Clerk User",
                school_id=school_id,
                department_id=None,
                status=UserStatus.ACTIVE,
                roles=[UserRole.VIEWER.value],
                mfa_enabled=False,
                language_preference="en",
                created_at=utc_now(),
                updated_at=utc_now()
            )

            session.add(test_user)
            await session.commit()
            await session.refresh(test_user)

            print(f"PASS: Created test user successfully:")
            print(f"   ID: {test_user.id}")
            print(f"   Clerk User ID: {test_user.clerk_user_id}")
            print(f"   Email: {test_user.email}")
            print(f"   School ID: {test_user.school_id}")
            print(f"   Roles: {test_user.roles}")

            return test_user.id

        except Exception as e:
            print(f"FAIL: Error creating test user: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        CLERK_USER_ID = sys.argv[1]
    asyncio.run(create_test_user())
