import asyncio
from shared.database import AsyncSessionLocal
from sqlalchemy import text

async def fix():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("UPDATE users SET clerk_user_id = :new_cuid WHERE id = :id"),
            {"new_cuid": "user_3I4mex7L85J3G0K2IIItLWhQIH5", "id": "dc0911a1-cea4-4011-baa8-997388939173"}
        )
        await db.commit()
        print(f"Rows updated: {result.rowcount}")

asyncio.run(fix())
