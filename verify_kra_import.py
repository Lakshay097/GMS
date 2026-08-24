"""
Quick script to verify KRA/KPI import
"""
import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv
import os
import urllib.parse

load_dotenv()

async def verify_import():
    """Verify KRA/KPI import."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found")
        return
    
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://")
    
    parsed = urllib.parse.urlparse(database_url)
    query_dict = urllib.parse.parse_qs(parsed.query)
    unsupported_params = ['sslmode', 'sslcert', 'sslkey', 'sslrootcert', 'sslcrl', 'channel_binding']
    for param in unsupported_params:
        query_dict.pop(param, None)
    
    new_query = urllib.parse.urlencode(query_dict, doseq=True)
    database_url = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as db:
            # Count KRAs
            result = await db.execute(text("SELECT COUNT(*) FROM kras"))
            kras_count = result.scalar()
            
            # Count KPIs
            result = await db.execute(text("SELECT COUNT(*) FROM kpis"))
            kpis_count = result.scalar()
            
            # Get sample KRAs
            result = await db.execute(text("SELECT name FROM kras ORDER BY name LIMIT 15"))
            kras = result.fetchall()
            
            # Get sample KPIs with their KRAs
            result = await db.execute(text("""
                SELECT kp.title, k.name 
                FROM kpis kp
                JOIN kras k ON kp.kra_id = k.id
                ORDER BY k.name, kp.title
                LIMIT 10
            """))
            kpis = result.fetchall()
            
            print(f"Import Verification Results:")
            print(f"   Total KRAs: {kras_count}")
            print(f"   Total KPIs: {kpis_count}")
            print(f"\nSample KRAs:")
            for kra in kras:
                print(f"   - {kra[0]}")
            
            print(f"\nSample KPIs:")
            for kpi in kpis:
                try:
                    print(f"   - {kpi[0]} (KRA: {kpi[1]})")
                except UnicodeEncodeError:
                    print(f"   - [Special characters] (KRA: {kpi[1]})")
            
    except Exception as e:
        print(f"Error verifying import: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify_import())