"""
Script to create a SuperAdmin user for initial setup.
This bypasses the normal auth flow for initial system configuration.
Uses raw SQL to avoid schema mismatch issues.
"""
import asyncio
import uuid
import sys
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv()

async def create_superadmin_user():
    """Create a SuperAdmin user with the specified credentials using raw SQL."""
    
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
            # Check if user already exists
            existing_user = await conn.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": "lakshay.kumar@pw.live"}
            )
            if existing_user.fetchone():
                print("User with email lakshay.kumar@pw.live already exists")
                return
            
            # Generate user ID and temporary clerk_user_id
            user_id = uuid.uuid4()
            clerk_user_id = f"manual-setup-{uuid.uuid4()}"
            
            # Insert SuperAdmin user using raw SQL
            from shared.datetime_utils import utc_now
            now = utc_now()
            
            await conn.execute(
                text("""INSERT INTO users 
                   (id, clerk_user_id, email, full_name, school_id, department_id, 
                    status, roles, mfa_enabled, phone, employee_id, created_at, updated_at)
                   VALUES (:id, :clerk_user_id, :email, :full_name, :school_id, :department_id, 
                    :status, :roles, :mfa_enabled, :phone, :employee_id, :created_at, :updated_at)"""),
                {
                    "id": user_id,
                    "clerk_user_id": clerk_user_id,
                    "email": "lakshay.kumar@pw.live",
                    "full_name": "Lakshay Kumar",
                    "school_id": None,  # null for SuperAdmin
                    "department_id": None,
                    "status": "active",
                    "roles": json.dumps(["superadmin"]),  # JSON array for PostgreSQL
                    "mfa_enabled": False,
                    "phone": None,
                    "employee_id": None,
                    "created_at": now,
                    "updated_at": now
                }
            )
            
            print(f"SuperAdmin user created successfully!")
            print(f"   ID: {user_id}")
            print(f"   Email: lakshay.kumar@pw.live")
            print(f"   Name: Lakshay Kumar")
            print(f"   Roles: ['superadmin']")
            print(f"\nNOTE: This user was created with a temporary clerk_user_id: {clerk_user_id}")
            print(f"   You will need to configure Clerk authentication for this user")
            print(f"   or update the clerk_user_id field with a valid Clerk user ID.")
            print(f"\nFor authentication setup, you'll need to:")
            print(f"   1. Set up Clerk for this email")
            print(f"   2. Update the clerk_user_id in the database")
            print(f"   3. Configure authentication through the Clerk dashboard")
            
    except Exception as e:
        print(f"Error creating SuperAdmin user: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_superadmin_user())
