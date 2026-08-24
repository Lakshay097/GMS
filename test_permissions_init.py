import asyncio
from shared.permissions import PermissionMatrix
from shared.database import AsyncSessionLocal

async def test_permissions():
    """Test permissions initialization."""
    try:
        async with AsyncSessionLocal() as db:
            print("Starting permissions initialization...")
            await PermissionMatrix.initialize_permissions(db)
            print("Permissions matrix initialized successfully")
    except Exception as e:
        print(f"Permissions initialization failed: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_permissions())