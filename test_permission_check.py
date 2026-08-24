import asyncio
from shared.database import get_db
from shared.permissions import PermissionMatrix, Module, Action
from sqlalchemy import select
from shared.models import User

async def test_permission_check():
    async for session in get_db():
        # Get the user
        result = await session.execute(select(User).where(User.email == 'lakshay.kumar@pw.live'))
        user = result.scalar_one_or_none()
        
        if user:
            print(f'Testing permission check for user: {user.email}')
            print(f'User roles: {user.roles}')
            
            # Test the permission check
            try:
                has_permission = await PermissionMatrix.check_permission(
                    db=session,
                    user_roles=user.roles,
                    module=Module.DASHBOARD.value,
                    action=Action.VIEW.value
                )
                print(f'Permission check result: {has_permission}')
            except Exception as e:
                print(f'Permission check failed with error: {e}')
                import traceback
                traceback.print_exc()
        else:
            print('User not found')

if __name__ == "__main__":
    asyncio.run(test_permission_check())