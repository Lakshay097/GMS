"""
Diagnostic: Check all users in DB and verify the list_users query path.
Run: python check_users.py
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, func, text
from shared.database import AsyncSessionLocal
from shared.models import User, UserStatus, UserRole


async def check():
    async with AsyncSessionLocal() as db:
        # 1. Count all users
        count_result = await db.execute(select(func.count(User.id)))
        total = count_result.scalar()
        print(f"Total users in DB: {total}")

        # 2. List ALL users with full details
        result = await db.execute(
            select(User).order_by(User.created_at)
        )
        users = result.scalars().all()

        print(f"\n{'='*70}")
        print("ALL USERS:")
        print(f"{'='*70}")

        for i, u in enumerate(users, 1):
            roles_raw = u.roles
            roles_display = repr(roles_raw)
            # Check if roles is a proper list
            is_list = isinstance(roles_raw, list)
            role_values = [r.value if hasattr(r, 'value') else r for r in (roles_raw or [])]
            normalized = [r.lower() if isinstance(r, str) else r for r in role_values]

            print(f"\n  User #{i}:")
            print(f"    id:              {u.id}")
            print(f"    clerk_user_id:   {u.clerk_user_id}")
            print(f"    email:           {u.email}")
            print(f"    full_name:       {u.full_name}")
            print(f"    roles (raw):     {roles_display}")
            print(f"    roles is list:   {is_list}")
            print(f"    roles values:    {role_values}")
            print(f"    roles normalized:{normalized}")
            print(f"    status:          {u.status}")
            print(f"    school_id:       {u.school_id}")
            print(f"    department_id:   {u.department_id}")
            print(f"    created_at:      {u.created_at}")

        # 3. Simulate list_users for SuperAdmin (no school filter)
        print(f"\n{'='*70}")
        print("SIMULATING list_users (SuperAdmin - no school filter):")
        print(f"{'='*70}")

        query = select(User)
        result = await db.execute(query)
        all_users = result.scalars().all()
        print(f"  Would return {len(all_users)} users")
        for u in all_users:
            print(f"    - {u.email} ({u.roles}) status={u.status}")

        # 4. Check if lakshayrajput239@gmail.com exists
        print(f"\n{'='*70}")
        print("CHECKING lakshayrajput239@gmail.com:")
        print(f"{'='*70}")

        result = await db.execute(
            select(User).where(User.email == "lakshayrajput239@gmail.com")
        )
        target = result.scalar_one_or_none()
        if target:
            print(f"  FOUND: id={target.id} clerk_user_id={target.clerk_user_id} roles={target.roles} status={target.status}")
        else:
            print(f"  NOT FOUND in DB!")

        # 5. Check if lakshay.kumar@pw.live exists
        print(f"\n{'='*70}")
        print("CHECKING lakshay.kumar@pw.live:")
        print(f"{'='*70}")

        result = await db.execute(
            select(User).where(User.email == "lakshay.kumar@pw.live")
        )
        sa = result.scalar_one_or_none()
        if sa:
            print(f"  FOUND: id={sa.id} clerk_user_id={sa.clerk_user_id} roles={sa.roles} status={sa.status}")
        else:
            print(f"  NOT FOUND in DB!")

        # 6. Check for any users with placeholder clerk_user_ids
        print(f"\n{'='*70}")
        print("USERS WITH PLACEHOLDER CLERK IDs:")
        print(f"{'='*70}")

        result = await db.execute(
            select(User).where(User.clerk_user_id.like("manual-setup-%"))
        )
        placeholders = result.scalars().all()
        if placeholders:
            for u in placeholders:
                print(f"  - {u.email} clerk_user_id={u.clerk_user_id} roles={u.roles}")
        else:
            print("  None found")


if __name__ == "__main__":
    asyncio.run(check())
