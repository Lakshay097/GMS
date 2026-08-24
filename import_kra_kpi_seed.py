"""
Script to import KRA/KPI seed data from specs/kpi-seed-data.md
This requires SuperAdmin privileges.
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
import uuid
import json
import re
from decimal import Decimal

load_dotenv()

async def import_kra_kpi_seed():
    """Import KRA/KPI seed data using direct SQL."""
    
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
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as db:
            # Get SuperAdmin user
            result = await db.execute(
                text("SELECT id, email FROM users WHERE roles::jsonb ? :role"),
                {"role": "superadmin"}
            )
            superadmin = result.fetchone()
            
            if not superadmin:
                print("ERROR: No SuperAdmin user found. Please create one first using create_superadmin.py")
                return
            
            user_id = superadmin[0]
            print(f"Found SuperAdmin user: {superadmin[1]} (ID: {user_id})")
            
            # Parse seed data
            seed_file_path = "specs/kpi-seed-data.md"
            if not Path(seed_file_path).exists():
                print(f"ERROR: Seed file not found: {seed_file_path}")
                return
            
            content = Path(seed_file_path).read_text(encoding="utf-8")
            rows = parse_seed_tables(content)
            
            print(f"\nParsed {len(rows)} rows from seed file")
            
            # Import KRAs and KPIs
            imported_kras = 0
            imported_kpis = 0
            skipped = 0
            kra_cache = {}
            
            from shared.datetime_utils import utc_now
            now = utc_now()
            
            # Frequency aliases
            FREQUENCY_ALIASES = {
                "annually": "annual",
                "half-yearly": "half_yearly",
                "half_yearly": "half_yearly",
                "times-per-day": "times_per_day",
                "ad-hoc": "ad_hoc",
                "event-triggered": "event_triggered",
                "event_triggered": "event_triggered",
                "event-driven": "event_triggered",
                "event_driven": "event_triggered",
                "termly": "termly",
                "quaterly": "quarterly",
                "quarterly": "quarterly",
            }
            
            # Placeholder patterns to skip
            PLACEHOLDER_PATTERNS = (
                "_n/a_",
                "_not specified in manual_",
                "_not specified — school-level default_",
                "_not specified - school-level default_",
                "_target not numerically specified in manual",
                "defined ",
                "x/",
                "x%",
            )
            
            for row in rows:
                # Check if should skip
                should_skip = False
                for field in ("comparator", "target", "frequency", "unit"):
                    value = row.get(field, "").strip().lower()
                    if not value or any(pattern in value for pattern in PLACEHOLDER_PATTERNS):
                        should_skip = True
                        break
                
                if should_skip:
                    skipped += 1
                    continue
                
                kra_name = row["kra"].strip()
                
                # Create KRA if not exists
                if kra_name not in kra_cache:
                    existing = await db.execute(
                        text("SELECT id FROM kras WHERE name = :name"),
                        {"name": kra_name}
                    )
                    existing_kra = existing.fetchone()
                    
                    if existing_kra:
                        kra_cache[kra_name] = existing_kra[0]
                    else:
                        new_kra_id = uuid.uuid4()
                        await db.execute(
                            text("""INSERT INTO kras (id, name, status, created_at, updated_at) 
                                   VALUES (:id, :name, :status, :created_at, :updated_at)"""),
                            {
                                "id": new_kra_id,
                                "name": kra_name,
                                "status": "active",
                                "created_at": now,
                                "updated_at": now
                            }
                        )
                        kra_cache[kra_name] = new_kra_id
                        imported_kras += 1
                
                # Create KPI
                try:
                    target = parse_target(row["target"])
                    comparator = normalize_comparator(row["comparator"])
                    frequency = normalize_frequency(row["frequency"], FREQUENCY_ALIASES)
                    unit = normalize_unit(row["unit"])
                    
                    new_kpi_id = uuid.uuid4()
                    await db.execute(
                        text("""INSERT INTO kpis (kpi_id, version, kra_id, title, target_value, comparator, 
                               unit_of_measure, frequency_code, formula_type, capture_type, category_code, 
                               is_sensitive, amber_tolerance_band, working_days, non_working_day_policy, 
                               status, is_immutable, created_at, created_by) 
                               VALUES (:kpi_id, :version, :kra_id, :title, :target_value, :comparator, 
                               :unit_of_measure, :frequency_code, :formula_type, :capture_type, :category_code, 
                               :is_sensitive, :amber_tolerance_band, :working_days, :non_working_day_policy, 
                               :status, :is_immutable, :created_at, :created_by)"""),
                        {
                            "kpi_id": new_kpi_id,
                            "version": 1,
                            "kra_id": kra_cache[kra_name],
                            "title": row["kpi"].strip(),
                            "target_value": target,
                            "comparator": comparator,
                            "unit_of_measure": unit,
                            "frequency_code": frequency,
                            "formula_type": "threshold_comparison",
                            "capture_type": "value_reading",
                            "category_code": None,
                            "is_sensitive": row.get("sensitive", "no").strip().lower() == "yes",
                            "amber_tolerance_band": None,
                            "working_days": None,
                            "non_working_day_policy": "skip",
                            "status": "active",
                            "is_immutable": False,
                            "created_at": now,
                            "created_by": user_id
                        }
                    )
                    imported_kpis += 1
                except Exception as e:
                    print(f"Skipping KPI due to error: {e}")
                    skipped += 1
            
            await db.commit()
            
            print(f"\nImport completed successfully!")
            print(f"  Total KRAs created: {imported_kras}")
            print(f"  Total KPIs imported: {imported_kpis}")
            print(f"  Rows skipped: {skipped}")
            
            # List the created KRAs
            kras_result = await db.execute(
                text("SELECT name, description FROM kras ORDER BY name")
            )
            kras = kras_result.fetchall()
            
            print(f"\nAvailable KRAs:")
            for kra in kras:
                print(f"  - {kra[0]}")
                if kra[1]:
                    print(f"    Description: {kra[1]}")
            
    except Exception as e:
        print(f"Error importing KRA/KPI seed data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

def parse_seed_tables(content):
    """Parse Role|KRA|KPI seed tables."""
    rows = []
    role_first = False
    for line in content.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells:
            continue
        
        header0 = cells[0].lower()
        if header0 in {"kra", "role"}:
            role_first = header0 == "role"
            continue
        
        if role_first:
            if len(cells) < 7:
                continue
            kra, kpi, unit, comparator, target, frequency = cells[1:7]
            sensitive = cells[7] if len(cells) > 7 else "no"
            capture_type = cells[8] if len(cells) > 8 else "Value"
            non_working_day_policy = cells[10] if len(cells) > 10 else "Skip"
        else:
            if len(cells) < 6:
                continue
            kra, kpi, unit, comparator, target, frequency = cells[0:6]
            sensitive = cells[6] if len(cells) > 6 else "no"
            capture_type = cells[7] if len(cells) > 7 else "Value"
            non_working_day_policy = cells[9] if len(cells) > 9 else "Skip"
        
        rows.append({
            "kra": kra,
            "kpi": kpi,
            "unit": unit,
            "comparator": comparator,
            "target": target,
            "frequency": frequency,
            "sensitive": sensitive,
            "capture_type": capture_type,
            "non_working_day_policy": non_working_day_policy,
        })
    return rows

def parse_target(raw):
    """Parse target value."""
    cleaned = raw.replace("%", "").replace("±", "").strip()
    match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
    if not match:
        raise ValueError(f"Cannot parse target: {raw}")
    return float(match.group())

def normalize_comparator(raw):
    """Normalize comparator symbols."""
    comp = raw.strip()
    if comp in (">=", "≥"):
        return ">="
    if comp in ("<=", "≤"):
        return "<="
    if comp in ("=", "="):
        return "="
    if comp in ("<", "<"):
        return "<"
    if comp in (">", ">"):
        return ">"
    return ">="  # default

def normalize_frequency(raw, aliases):
    """Normalize frequency codes."""
    value = raw.strip().lower()
    if "(" in value:
        value = value.split("(", 1)[0].strip()
    value = value.replace(" ", "_")
    return aliases.get(value, value)

def normalize_unit(raw):
    """Normalize unit of measure."""
    value = raw.strip().lower()
    if value in ("%", "percent", "percentage"):
        return "percent"
    if value in ("hours", "hour"):
        return "hours"
    if not value or value in ("n/a", "_n/a_"):
        return "count"
    return value.replace(" ", "_")

if __name__ == "__main__":
    asyncio.run(import_kra_kpi_seed())