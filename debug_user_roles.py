import asyncio
from shared.database import get_db
from sqlalchemy import select
from shared.models import User

async def debug_user_roles():
    async for session in get_db():
        result = await session.execute(select(User).where(User.email == 'lakshay.kumar@pw.live'))
        user = result.scalar_one_or_none()
        if user:
            print(f'User ID: {user.id}')
            print(f'Clerk User ID: {user.clerk_user_id}')
            print(f'Roles from DB: {user.roles}')
            print(f'Roles type: {type(user.roles)}')
            
            # Check role normalization
            normalized_roles = [((r.value if hasattr(r, "value") else r) or "").lower() for r in (user.roles or [])]
            print(f'Normalized roles: {normalized_roles}')
            
            # Check individual role
            for role in user.roles:
                print(f'Role: {role}')
                print(f'Role type: {type(role)}')
                print(f'Role lower: {role.lower() if hasattr(role, "lower") else "N/A"}')
                print(f'Has value attr: {hasattr(role, "value")}')
                if hasattr(role, "value"):
                    print(f'Role.value: {role.value}')
        else:
            print('User not found')

if __name__ == "__main__":
    asyncio.run(debug_user_roles())