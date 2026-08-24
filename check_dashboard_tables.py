"""
Check if dashboard tables exist and have data
"""
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from shared.database import AsyncSessionLocal
from sqlalchemy import text

async def check_tables():
    """Check if required tables exist and have data"""
    async with AsyncSessionLocal() as db:
        tables_to_check = [
            'observations',
            'compliance_observations', 
            'tasks',
            'discrepancies',
            'task_escalations',
            'audit_log_entries'
        ]
        
        for table in tables_to_check:
            try:
                # Check if table exists and count rows
                result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"Table {table}: {count} rows")
            except Exception as e:
                print(f"Table {table}: ERROR - {e}")

if __name__ == "__main__":
    asyncio.run(check_tables())