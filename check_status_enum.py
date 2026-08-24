import asyncio
from shared.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT unnest(enum_range(NULL::userstatus))"))
        for row in result:
            print(row)

asyncio.run(check())
