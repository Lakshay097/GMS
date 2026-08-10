"""
Initialize the permission matrix in the database.
Run this after database migrations to load the PRS §12 permission matrix.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from shared.database import AsyncSessionLocal
from shared.permissions import PermissionMatrix
from dotenv import load_dotenv

load_dotenv()


async def init_permissions():
    """
    Initialize the permission matrix.
    """
    async with AsyncSessionLocal() as db:
        print("Initializing permission matrix from PRS §12...")
        await PermissionMatrix.initialize_permissions(db)
        print("Permission matrix initialized successfully.")
        
        # Verify permissions loaded
        from sqlalchemy import text
        result = await db.execute(text("SELECT COUNT(*) FROM permissions"))
        count = result.scalar()
        print(f"Total permissions loaded: {count}")
        
        # Check for null IDs
        result = await db.execute(text("SELECT COUNT(*) FROM permissions WHERE id IS NULL"))
        null_count = result.scalar()
        if null_count > 0:
            print(f"WARNING: {null_count} permissions have null IDs, fixing...")
            await db.execute(text("UPDATE permissions SET id = gen_random_uuid() WHERE id IS NULL"))
            await db.commit()
            print("Fixed null IDs.")


if __name__ == "__main__":
    asyncio.run(init_permissions())
