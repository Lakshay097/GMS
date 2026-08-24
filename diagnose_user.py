"""
Diagnostic: Check all user records for lakshay.kumar@pw.live
and simulate the /auth/get-session lookup chain.

Run: python diagnose_user.py
"""
import asyncio
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
from dotenv import load_dotenv
load_dotenv()

import urllib.parse
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

REAL_CLERK_ID = "user_3I4mex7L85J3G0K2IIItLWhQIH5"
EMAIL = "lakshay.kumar@pw.live"

async def diagnose():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://")

    parsed = urllib.parse.urlparse(database_url)
    query_dict = urllib.parse.parse_qs(parsed.query)
    for param in ['sslmode', 'sslcert', 'sslkey', 'sslrootcert', 'sslcrl', 'channel_binding']:
        query_dict.pop(param, None)
    new_query = urllib.parse.urlencode(query_dict, doseq=True)
    database_url = urllib.parse.urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, new_query, parsed.fragment
    ))

    engine = create_async_engine(database_url)

    async with engine.begin() as conn:
        # 1. ALL users with this email
        print("=" * 60)
        print("ALL user records for lakshay.kumar@pw.live:")
        print("=" * 60)
        result = await conn.execute(
            text("SELECT id, clerk_user_id, email, roles, status, school_id FROM users WHERE email = :email"),
            {"email": EMAIL}
        )
        rows = result.fetchall()
        if not rows:
            print("  ❌ NO user records found!")
        for i, row in enumerate(rows):
            print(f"\n  Record #{i+1}:")
            print(f"    id:            {row[0]}")
            print(f"    clerk_user_id: {row[1]}")
            print(f"    email:         {row[2]}")
            print(f"    roles:         {row[3]} (type: {type(row[3]).__name__})")
            print(f"    status:        {row[4]}")
            print(f"    school_id:     {row[5]}")
        if len(rows) > 1:
            print(f"\n  ⚠️  DUPLICATE DETECTED: {len(rows)} records for same email!")

        # 2. Simulate /auth/get-session with real Clerk sub
        print("\n" + "=" * 60)
        print(f"Simulating /auth/get-session with sub={REAL_CLERK_ID}")
        print("=" * 60)

        # Step 1: find by User.id (UUID) — skip if sub is not a valid UUID
        print("\n  Step 1: User.id == sub?")
        import uuid as _uuid
        try:
            _uuid.UUID(REAL_CLERK_ID)
            result = await conn.execute(
                text("SELECT id, email, roles FROM users WHERE id = :id AND status = 'active'"),
                {"id": REAL_CLERK_ID}
            )
            row = result.fetchone()
            print(f"    → {'FOUND' if row else 'MISS'}" + (f" roles={row[2]}" if row else ""))
        except ValueError:
            print(f"    → SKIP (not a UUID: {REAL_CLERK_ID})")

        # Step 2: find by clerk_user_id
        print("\n  Step 2: clerk_user_id == sub?")
        result = await conn.execute(
            text("SELECT id, email, roles, clerk_user_id FROM users WHERE clerk_user_id = :cuid AND status = 'active'"),
            {"cuid": REAL_CLERK_ID}
        )
        row = result.fetchone()
        print(f"    → {'FOUND' if row else 'MISS'}" + (f" email={row[1]} roles={row[2]}" if row else ""))

        # Step 3: find by email
        print("\n  Step 3: email == payload.email?")
        result = await conn.execute(
            text("SELECT id, email, roles, clerk_user_id, status FROM users WHERE email = :email"),
            {"email": EMAIL}
        )
        rows = result.fetchall()
        print(f"    → {len(rows)} record(s) found")
        for row in rows:
            print(f"      id={row[0]} clerk_user_id={row[3]} roles={row[2]} status={row[4]}")

        # 3. Check what the frontend getPermissions would produce
        print("\n" + "=" * 60)
        print("Frontend getPermissions simulation:")
        print("=" * 60)
        if rows:
            for row in rows:
                roles = row[2] if isinstance(row[2], list) else []
                normalized = [r.lower().replace(" ", "_") for r in roles]
                print(f"  User {row[1]}: roles={roles} → normalized={normalized}")
                known = ['superadmin', 'admin', 'dept_head', 'checker', 'viewer']
                matched = [r for r in normalized if r in known]
                print(f"    matched in ROLE_PERMISSIONS: {matched or 'NONE → falls back to viewer!'}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(diagnose())
