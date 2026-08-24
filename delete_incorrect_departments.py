"""
Script to delete incorrect departments created with role names instead of department names.
This should only be run by SuperAdmin.
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

# Incorrect department codes that need to be deleted
INCORRECT_DEPT_CODES = {"PRINCIPAL", "ACCOUNTANT", "FACILITY", "SECURITY", "MARKETING", "TELECALLER"}

async def delete_incorrect_departments():
    """Delete incorrect departments created with role names."""
    
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
            # Check existing departments with incorrect codes
            existing_result = await conn.execute(
                text("SELECT id, name, code, school_id FROM departments WHERE code = ANY(:codes)"),
                {"codes": list(INCORRECT_DEPT_CODES)}
            )
            existing_depts = existing_result.fetchall()
            
            if not existing_depts:
                print("No incorrect departments found to delete")
                return
            
            print(f"Found {len(existing_depts)} incorrect departments to delete:")
            for dept in existing_depts:
                print(f"  - {dept[1]} ({dept[2]})")
            
            # Delete the incorrect departments
            deleted_count = 0
            for dept in existing_depts:
                await conn.execute(
                    text("DELETE FROM departments WHERE id = :id"),
                    {"id": dept[0]}
                )
                print(f"  [+] Deleted: {dept[1]} ({dept[2]})")
                deleted_count += 1
            
            print(f"\n[SUCCESS] Deleted {deleted_count} incorrect departments")
            
    except Exception as e:
        print(f"Error deleting incorrect departments: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    print("Deleting incorrect departments created with role names...")
    print("Incorrect department codes to delete:")
    for code in INCORRECT_DEPT_CODES:
        print(f"  - {code}")
    print()
    
    # Security check - this should only be run by SuperAdmin
    print("WARNING: This operation should only be performed by SuperAdmin")
    
    # Check for command line argument or prompt
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'yes':
        print("Proceeding with department deletion...")
        asyncio.run(delete_incorrect_departments())
    else:
        response = input("Do you want to continue? (yes/no): ")
        
        if response.lower() != 'yes':
            print("Operation cancelled")
            sys.exit(0)
        
        asyncio.run(delete_incorrect_departments())