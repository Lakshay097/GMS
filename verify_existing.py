import asyncio
from shared.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT id, clerk_user_id, email, full_name, roles, school_id, status FROM users WHERE id = :id"),
            {"id": "dc0911a1-cea4-4011-baa8-997388939173"}
        )
        row = result.fetchone()
        print(row)

asyncio.run(check())
