"""
One-time migration script: Sync existing user roles from Neon DB to Clerk publicMetadata.

The frontend reads roles from Clerk's publicMetadata to control navigation.
If your SuperAdmin can only see Dashboard and Reports, their Clerk publicMetadata
is missing the 'roles' array. This script fixes that by reading roles from the
database and writing them to Clerk.

Usage:
    python sync_clerk_roles.py                    # Sync all active users
    python sync_clerk_roles.py --email user@x.com # Sync a specific user only
"""
import asyncio
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")


async def sync_user_roles(engine, email_filter: str = None):
    if not CLERK_SECRET_KEY:
        print("ERROR: CLERK_SECRET_KEY not set in environment. Cannot sync to Clerk.")
        return

    async with engine.begin() as conn:
        if email_filter:
            result = await conn.execute(
                text("SELECT clerk_user_id, email, roles FROM users WHERE email = :email AND status = 'active'"),
                {"email": email_filter}
            )
        else:
            result = await conn.execute(
                text("SELECT clerk_user_id, email, roles FROM users WHERE status = 'active'")
            )

        users = result.fetchall()

    if not users:
        print("No active users found.")
        return

    print(f"Found {len(users)} active user(s). Syncing roles to Clerk...\n")

    success = 0
    failed = 0

    async with httpx.AsyncClient() as client:
        for row in users:
            clerk_user_id = row[0]
            email = row[1]
            roles = row[2] if isinstance(row[2], list) else []

            # Skip users with temporary clerk_user_id (not yet linked to Clerk)
            if clerk_user_id.startswith("manual-setup-"):
                print(f"  SKIP  {email} — has temporary clerk_user_id ({clerk_user_id}). Link via sign-in first.")
                continue

            try:
                response = await client.patch(
                    f"https://api.clerk.com/v1/users/{clerk_user_id}/metadata",
                    headers={
                        "Authorization": f"Bearer {CLERK_SECRET_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={"publicMetadata": {"roles": roles}},
                    timeout=10.0
                )
                if response.status_code == 200:
                    print(f"  OK    {email} — roles synced: {roles}")
                    success += 1
                else:
                    print(f"  FAIL  {email} — Clerk API returned {response.status_code}: {response.text[:100]}")
                    failed += 1
            except Exception as e:
                print(f"  ERROR {email} — {e}")
                failed += 1

    print(f"\nDone. {success} synced, {failed} failed.")


if __name__ == "__main__":
    import urllib.parse

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        sys.exit(1)

    # Normalize driver
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://")

    # Remove unsupported SSL params for asyncpg
    parsed = urllib.parse.urlparse(database_url)
    query_dict = urllib.parse.parse_qs(parsed.query)
    for param in ['sslmode', 'sslcert', 'sslkey', 'sslrootcert', 'sslcrl', 'channel_binding']:
        query_dict.pop(param, None)
    new_query = urllib.parse.urlencode(query_dict, doseq=True)
    database_url = urllib.parse.urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, new_query, parsed.fragment
    ))

    email_filter = None
    if "--email" in sys.argv:
        idx = sys.argv.index("--email")
        if idx + 1 < len(sys.argv):
            email_filter = sys.argv[idx + 1]

    engine = create_async_engine(database_url)

    async def main():
        try:
            await sync_user_roles(engine, email_filter)
        finally:
            await engine.dispose()

    asyncio.run(main())
