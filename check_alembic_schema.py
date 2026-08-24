import asyncio
from shared.database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name = 'alembic_version'"
        ))
        rows = result.fetchall()
        for row in rows:
            print(row)

asyncio.run(main())