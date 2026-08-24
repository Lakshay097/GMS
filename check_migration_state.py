import asyncio
from shared.database import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT version_num FROM alembic_version'))
        versions = [row[0] for row in result]
        print('Applied versions:', versions)
        
        # Check if the department request fields exist
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('requested_department_id', 'department_request_status', 'requested_at')
        """))
        columns = [row[0] for row in result]
        print('Department request columns in users table:', columns)

asyncio.run(check())