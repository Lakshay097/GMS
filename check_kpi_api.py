"""
Script to test the KPI API endpoint.
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

async def check_permissions():
    """Check if GLOBAL_KPI_LIBRARY permissions exist."""
    
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
            # Check permissions table
            result = await conn.execute(text("""
                SELECT module, action, role 
                FROM permissions 
                WHERE module = 'GLOBAL_KPI_LIBRARY'
            """))
            permissions = result.fetchall()
            print(f"GLOBAL_KPI_LIBRARY permissions: {len(permissions)}")
            for perm in permissions:
                print(f"  - Module: {perm[0]}, Action: {perm[1]}, Role: {perm[2]}")
            
            # Check if there are any permissions at all
            result = await conn.execute(text("SELECT COUNT(*) FROM permissions"))
            total_perms = result.scalar()
            print(f"\nTotal permissions in database: {total_perms}")
            
            # Check permissions table structure
            result = await conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'permissions'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print(f"\nPermissions table structure:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]}")
            
            # Check a sample permission
            result = await conn.execute(text("SELECT * FROM permissions LIMIT 1"))
            sample = result.fetchone()
            print(f"\nSample permission: {sample}")
            
            # Check specific global_kpi_library permissions
            result = await conn.execute(text("""
                SELECT * FROM permissions 
                WHERE module = 'global_kpi_library'
            """))
            gklib_perms = result.fetchall()
            print(f"\nglobal_kpi_library permissions: {len(gklib_perms)}")
            for perm in gklib_perms:
                print(f"  - {perm}")
            
            # Insert missing permissions if needed
            if len(gklib_perms) == 0:
                print("\n⚠️  No GLOBAL_KPI_LIBRARY permissions found!")
                print("Adding default permissions for all roles...")
                
                # Get all roles from existing permissions
                result = await conn.execute(text("SELECT DISTINCT role FROM permissions"))
                roles = [r[0] for r in result.fetchall()]
                print(f"Found roles: {roles}")
                
                # Add read permission for all roles
                for role in roles:
                    await conn.execute(text("""
                        INSERT INTO permissions (module, action, role, scope_constraint, is_allowed)
                        VALUES ('global_kpi_library', 'read', :role, 'global', true)
                    """), {"role": role})
                
                # Add write permission for superadmin
                await conn.execute(text("""
                    INSERT INTO permissions (module, action, role, scope_constraint, is_allowed)
                    VALUES ('global_kpi_library', 'write', 'superadmin', 'global', true)
                """))
                
                print("✅ Permissions added successfully!")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_permissions())