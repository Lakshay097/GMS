"""
Create user lakshay.kumar@pw.live with SuperAdmin role
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.models import User, UserStatus, UserRole, School, SchoolStatus
from shared.datetime_utils import utc_now
from shared.database import get_db
from uuid import uuid4

async def create_lakshay_user():
    """Create lakshay.kumar@pw.live user with SuperAdmin role"""
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
                    name="Gurukul Jaipur",
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

            # Check if user already exists by email
            user_result = await session.execute(
                select(User).where(User.email == "lakshay.kumar@pw.live")
            )
            existing_user = user_result.scalar_one_or_none()

            if existing_user:
                print(f"User already exists with ID: {existing_user.id}")
                print(f"Current roles: {existing_user.roles}")
                
                # Update to SuperAdmin if not already
                if UserRole.SUPERADMIN.value not in existing_user.roles:
                    existing_user.roles = [UserRole.SUPERADMIN.value]
                    existing_user.updated_at = utc_now()
                    await session.commit()
                    print("Updated user to SuperAdmin role")
                return existing_user.id

            # Create user with SuperAdmin role
            test_user = User(
                id=uuid4(),
                clerk_user_id=None,  # Will be set after Clerk signup
                email="lakshay.kumar@pw.live",
                full_name="Lakshay Kumar",
                school_id=school_id,
                department_id=None,
                status=UserStatus.ACTIVE,
                roles=[UserRole.SUPERADMIN.value],
                mfa_enabled=False,
                language_preference="en",
                created_at=utc_now(),
                updated_at=utc_now()
            )

            session.add(test_user)
            await session.commit()
            await session.refresh(test_user)

            print(f"PASS: Created user successfully:")
            print(f"   ID: {test_user.id}")
            print(f"   Email: {test_user.email}")
            print(f"   Full Name: {test_user.full_name}")
            print(f"   School ID: {test_user.school_id}")
            print(f"   Roles: {test_user.roles}")
            print(f"   Status: {test_user.status}")

            return test_user.id

        except Exception as e:
            print(f"FAIL: Error creating user: {e}")
            await session.rollback()
            raise

if __name__ == "__main__":
    asyncio.run(create_lakshay_user())
