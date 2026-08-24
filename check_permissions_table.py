import asyncio
from shared.database import AsyncSessionLocal
from sqlalchemy import text

async def check_permissions():
    """Check if permissions table exists and has data."""
    try:
        async with AsyncSessionLocal() as db:
            # Check if permissions table exists
            result = await db.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'permissions'
                )
            """))
            table_exists = result.scalar()
            print(f"Permissions table exists: {table_exists}")
            
            if table_exists:
                # Count permissions
                result = await db.execute(text("SELECT COUNT(*) FROM permissions"))
                count = result.scalar()
                print(f"Permissions count: {count}")
                
                # Sample some permissions
                result = await db.execute(text("SELECT * FROM permissions LIMIT 5"))
                rows = result.fetchall()
                print(f"Sample permissions: {rows}")
    except Exception as e:
        print(f"Error checking permissions: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(check_permissions())