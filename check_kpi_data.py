"""
Script to check KPI and KRA data in the database.
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

async def check_kpi_data():
    """Check KPI and KRA data."""
    
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
            # Check KRAs
            result = await conn.execute(text("SELECT id, name, description, status FROM kras"))
            kras = result.fetchall()
            print(f"Total KRAs: {len(kras)}")
            for kra in kras:
                print(f"  - {kra[1]} ({kra[0]}) - {kra[3]}")
            
            # Check KPIs
            result = await conn.execute(text("SELECT kpi_id, title, kra_id, status FROM kpis WHERE status = 'active'"))
            kpis = result.fetchall()
            print(f"\nTotal active KPIs: {len(kpis)}")
            for kpi in kpis:
                print(f"  - {kpi[1]} ({kpi[0]}) - KRA: {kpi[2]} - {kpi[3]}")
            
            # Check KPI assignments
            result = await conn.execute(text("SELECT id, kpi_id, department_id FROM department_kpi_assignments"))
            assignments = result.fetchall()
            print(f"\nTotal KPI assignments: {len(assignments)}")
            for assignment in assignments:
                print(f"  - KPI: {assignment[1]} -> Department: {assignment[2]}")
            
            # Check departments
            result = await conn.execute(text("SELECT id, name, code FROM departments LIMIT 5"))
            departments = result.fetchall()
            print(f"\nSample departments:")
            for dept in departments:
                print(f"  - {dept[1]} ({dept[2]})")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_kpi_data())