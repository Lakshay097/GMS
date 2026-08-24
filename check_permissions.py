import asyncio
from shared.database import get_db
from sqlalchemy import text

async def check_permissions():
    async for session in get_db():
        result = await session.execute(text("SELECT * FROM permissions WHERE module = 'dashboard' AND action = 'view'"))
        permissions = result.fetchall()
        print('Dashboard VIEW permissions:')
        for perm in permissions:
            print(f'  {perm}')

if __name__ == "__main__":
    asyncio.run(check_permissions())