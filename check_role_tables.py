import asyncio
from shared.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%role%'"))
        for row in result:
            print(row)

asyncio.run(check())
