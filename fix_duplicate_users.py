"""
One-time data fix: merge duplicate user records for the same email.

When create_superadmin.py and Clerk webhook both create users for the same
email, you end up with two records — one with SuperAdmin role (placeholder
clerk_user_id) and one with Viewer role (real clerk_user_id).

This script merges them: keeps the record with the most roles, sets the real
clerk_user_id on it, and archives the duplicate.

Usage:
    python fix_duplicate_users.py                         # Fix all duplicates
    python fix_duplicate_users.py --email user@x.com      # Fix specific email
    python fix_duplicate_users.py --dry-run               # Preview without changes
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
from shared.datetime_utils import utc_now

async def fix_duplicates(email_filter=None, dry_run=False):
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
        # Find all emails with multiple active user records
        if email_filter:
            result = await conn.execute(
                text("SELECT email FROM users WHERE email = :email GROUP BY email HAVING COUNT(*) > 1"),
                {"email": email_filter}
            )
        else:
            result = await conn.execute(
                text("SELECT email FROM users WHERE status = 'active' GROUP BY email HAVING COUNT(*) > 1")
            )

        duplicates = [row[0] for row in result.fetchall()]

        if not duplicates:
            print("No duplicate user records found.")
            await engine.dispose()
            return

        print(f"Found {len(duplicates)} email(s) with duplicate records:\n")

        for email in duplicates:
            # Get all records for this email
            result = await conn.execute(
                text("SELECT id, clerk_user_id, roles, status, school_id FROM users WHERE email = :email ORDER BY created_at"),
                {"email": email}
            )
            rows = result.fetchall()

            print(f"Email: {email}")
            print(f"  Records: {len(rows)}")
            for row in rows:
                print(f"    id={row[0]} clerk_user_id={row[1]} roles={row[2]} status={row[3]} school_id={row[4]}")

            # Find the best record (most roles, real clerk_user_id preferred)
            best = None
            best_role_count = -1
            for row in rows:
                if row[3] == 'active':
                    roles = row[2] if isinstance(row[2], list) else []
                    role_count = len(roles)
                    is_real_id = not str(row[1]).startswith('manual-setup-')
                    if (role_count > best_role_count or
                        (role_count == best_role_count and is_real_id and
                         best and str(best[1]).startswith('manual-setup-'))):
                        best_role_count = role_count
                        best = row

            if best is None:
                best = rows[0]

            # Find the real Clerk user ID (non-placeholder)
            real_clerk_id = None
            for row in rows:
                if not str(row[1]).startswith('manual-setup-'):
                    real_clerk_id = row[1]
                    break

            print(f"\n  KEEP:    id={best[0]} roles={best[2]}")
            if real_clerk_id and best[1] != real_clerk_id:
                print(f"  UPDATE:  clerk_user_id {best[1]} → {real_clerk_id}")

            for row in rows:
                if row[0] != best[0] and row[3] == 'active':
                    print(f"  ARCHIVE: id={row[0]} clerk_user_id={row[1]} roles={row[2]}")

            if not dry_run:
                now = utc_now().isoformat()

                # Update the best record's clerk_user_id if needed
                if real_clerk_id and best[1] != real_clerk_id:
                    await conn.execute(
                        text("UPDATE users SET clerk_user_id = :cuid, updated_at = :now WHERE id = :id"),
                        {"cuid": real_clerk_id, "id": best[0], "now": now}
                    )
                    print(f"  → Updated clerk_user_id")

                # Archive the duplicates
                for row in rows:
                    if row[0] != best[0] and row[3] == 'active':
                        await conn.execute(
                            text("UPDATE users SET status = 'archived', archived_at = :now, updated_at = :now WHERE id = :id"),
                            {"id": row[0], "now": now}
                        )
                        print(f"  → Archived id={row[0]}")

                print(f"  ✅ Done")
            else:
                print(f"  [DRY RUN — no changes made]")

            print()

    await engine.dispose()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", help="Fix specific email only")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    args = parser.parse_args()
    asyncio.run(fix_duplicates(email_filter=args.email, dry_run=args.dry_run))
