"""
Script to fix remaining departments with incorrect names.
Fixes: SOTC Head -> SOTC, School IT Manager -> IT, School Store In-Charge -> Store
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

# Department codes that need name fixes
DEPT_NAME_FIXES = {
    "SOTC": "SOTC",
    "IT": "IT", 
    "STORE": "Store"
}

async def fix_remaining_departments():
    """Fix department names that still have role names instead of department names."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        print("Please set DATABASE_URL in your .env file")
        return
    
    # Ensure we're using async driver
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://")
    
    # Clean up URL parameters that asyncpg doesn't support
    import urllib.parse
    parsed = urllib.parse.urlparse(database_url)
    query_dict = urllib.parse.parse_qs(parsed.query)
    
    # Remove unsupported SSL parameters
    unsupported_params = ['sslmode', 'sslcert', 'sslkey', 'sslrootcert', 'sslcrl', 'channel_binding']
    for param in unsupported_params:
        query_dict.pop(param, None)
    
    # Rebuild URL without unsupported params
    new_query = urllib.parse.urlencode(query_dict, doseq=True)
    database_url = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    
    # Create async engine
    engine = create_async_engine(database_url, echo=True)
    
    try:
        async with engine.begin() as conn:
            # Fix SOTC department names
            result = await conn.execute(
                text("UPDATE departments SET name = :new_name WHERE code = 'SOTC' AND name != :new_name"),
                {"new_name": "SOTC"}
            )
            print(f"Updated {result.rowcount} SOTC department names")
            
            # Fix IT department names
            result = await conn.execute(
                text("UPDATE departments SET name = :new_name WHERE code = 'IT' AND name != :new_name"),
                {"new_name": "IT"}
            )
            print(f"Updated {result.rowcount} IT department names")
            
            # Fix Store department names
            result = await conn.execute(
                text("UPDATE departments SET name = :new_name WHERE code = 'STORE' AND name != :new_name"),
                {"new_name": "Store"}
            )
            print(f"Updated {result.rowcount} Store department names")
            
            print("\n[SUCCESS] Fixed all remaining department names")
            
    except Exception as e:
        print(f"Error fixing department names: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    print("Fixing remaining department names...")
    print("This will update:")
    print("  - 'SOTC Head (Safety, Operations, Transport & Compliance)' -> 'SOTC'")
    print("  - 'School IT Manager' -> 'IT'")
    print("  - 'School Store In-Charge' -> 'Store'")
    print()
    
    # Security check - this should only be run by SuperAdmin
    print("WARNING: This operation should only be performed by SuperAdmin")
    
    # Check for command line argument or prompt
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'yes':
        print("Proceeding with department name fixes...")
        asyncio.run(fix_remaining_departments())
    else:
        response = input("Do you want to continue? (yes/no): ")
        
        if response.lower() != 'yes':
            print("Operation cancelled")
            sys.exit(0)
        
        asyncio.run(fix_remaining_departments())