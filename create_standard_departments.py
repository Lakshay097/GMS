"""
Script to create standard departments across all schools based on KPI seed data.
This should only be run by SuperAdmin.
Departments are created for each role defined in the KPI seed data.
"""
import asyncio
import uuid
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text, select
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

# Standard departments based on KPI seed data roles
# Correct mapping: Role -> Department
STANDARD_DEPARTMENTS = [
    {
        "name": "Academics",
        "code": "ACADEMICS",
        "description": "Academic administration and leadership"
    },
    {
        "name": "SOTC",
        "code": "SOTC",
        "description": "Safety, Operations, Transport & Compliance"
    },
    {
        "name": "Accounts",
        "code": "ACCOUNTS",
        "description": "Financial management and accounting"
    },
    {
        "name": "Facility",
        "code": "FACILITY",
        "description": "Infrastructure and facilities management"
    },
    {
        "name": "IT",
        "code": "IT",
        "description": "Information technology and systems management"
    },
    {
        "name": "Store",
        "code": "STORE",
        "description": "Inventory and store management"
    },
    {
        "name": "Security",
        "code": "SECURITY",
        "description": "Campus security and safety"
    },
    {
        "name": "Marketing",
        "code": "MARKETING",
        "description": "Marketing and admissions"
    },
    {
        "name": "Telecalling",
        "code": "TELECALLING",
        "description": "Telecommunications and parent communication"
    }
]

async def create_standard_departments():
    """Create standard departments for all active schools."""
    
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
            # Get all active schools
            schools_result = await conn.execute(
                text("SELECT id, name, code FROM schools WHERE status = 'active'")
            )
            schools = schools_result.fetchall()
            
            if not schools:
                print("No active schools found in database")
                return
            
            print(f"Found {len(schools)} active schools")
            
            for school in schools:
                school_id = school[0]
                school_name = school[1]
                school_code = school[2]
                
                print(f"\nProcessing school: {school_name} ({school_code})")
                
                # Check existing departments for this school
                existing_depts_result = await conn.execute(
                    text("SELECT name, code FROM departments WHERE school_id = :school_id"),
                    {"school_id": str(school_id)}
                )
                existing_depts = {row[1]: row[0] for row in existing_depts_result.fetchall()}
                
                print(f"  Existing departments: {len(existing_depts)}")
                
                # Create missing standard departments
                created_count = 0
                for dept in STANDARD_DEPARTMENTS:
                    if dept["code"] not in existing_depts:
                        dept_id = uuid.uuid4()
                        from shared.datetime_utils import utc_now
                        now = utc_now()
                        
                        await conn.execute(
                            text("""INSERT INTO departments 
                               (id, school_id, name, code, status, description, created_at, updated_at)
                               VALUES (:id, :school_id, :name, :code, :status, :description, :created_at, :updated_at)"""),
                            {
                                "id": dept_id,
                                "school_id": school_id,
                                "name": dept["name"],
                                "code": dept["code"],
                                "status": "active",
                                "description": dept["description"],
                                "created_at": now,
                                "updated_at": now
                            }
                        )
                        print(f"  [+] Created department: {dept['name']} ({dept['code']})")
                        created_count += 1
                    else:
                        print(f"  [-] Department already exists: {dept['name']} ({dept['code']})")
                
                print(f"  Created {created_count} new departments for {school_name}")
            
            print(f"\n[SUCCESS] Standard departments created/verified for all {len(schools)} schools")
            print(f"Total standard departments: {len(STANDARD_DEPARTMENTS)} per school")
            
    except Exception as e:
        print(f"Error creating standard departments: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    print("Creating standard departments across all schools...")
    print("This script creates departments based on KPI seed data roles:")
    for dept in STANDARD_DEPARTMENTS:
        print(f"  - {dept['name']} ({dept['code']})")
    print()
    
    # Check for command line argument or prompt
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'yes':
        print("Proceeding with department creation...")
        asyncio.run(create_standard_departments())
    else:
        # Security check - this should only be run by SuperAdmin
        print("WARNING: This operation should only be performed by SuperAdmin")
        response = input("Do you want to continue? (yes/no): ")
        
        if response.lower() != 'yes':
            print("Operation cancelled")
            sys.exit(0)
        
        asyncio.run(create_standard_departments())