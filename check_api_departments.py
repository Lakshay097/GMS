"""
Script to check what the API is returning for departments.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv()

async def check_api_departments():
    """Check what departments are being returned by the API."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        return
    
    # Ensure we're using async driver
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://")
    
    # Clean up URL parameters
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    query_dict = urllib.parse.parse_qs(parsed.query)
    unsupported_params = ['sslmode', 'sslcert', 'sslkey', 'sslrootcert', 'sslcrl', 'channel_binding']
    for param in unsupported_params:
        query_dict.pop(param, None)
    new_query = urllib.parse.urlencode(query_dict, doseq=True)
    database_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    
    # Create async engine
    engine = create_async_engine(database_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Check one specific school's departments
            result = await conn.execute(
                text("SELECT d.name, d.code, d.status, s.name as school_name FROM departments d JOIN schools s ON d.school_id = s.id WHERE s.code = 'GUR-JAI' ORDER BY d.name")
            )
            departments = result.fetchall()
            
            print(f"Departments for Gurukulam Jaipur:")
            for dept in departments:
                print(f"  - {dept[0]} ({dept[1]}) - {dept[2]}")
            
            print(f"\nTotal: {len(departments)} departments")
            
            # Check if there are any departments without school names
            result = await conn.execute(
                text("SELECT COUNT(*) FROM departments WHERE school_id IS NULL")
            )
            null_school_count = result.scalar()
            print(f"\nDepartments without school_id: {null_school_count}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_api_departments())