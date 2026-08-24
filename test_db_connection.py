import asyncio
from shared.database import engine
from sqlalchemy import text

async def test_db():
    """Test database connection."""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("Database connection successful:", result.fetchone())
    except Exception as e:
        print(f"Database connection failed: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_db())