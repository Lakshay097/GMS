import asyncio
from shared.database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        await conn.execute(text('ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(100)'))
        print('Column length updated successfully')

asyncio.run(main())