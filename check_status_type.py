import asyncio
from shared.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT udt_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'status'"))
        for row in result:
            print(row)

asyncio.run(check())
