"""
Bulk password migration for self-managed auth.

Users imported from the legacy identity provider have password_hash IS NULL
and cannot log in until they receive initial credentials. This script sets
them in bulk — no email provider required.

Usage:
    # Generate a strong random password per user, print once to stdout:
    python -m scripts.set_user_passwords

    # Set one password for every affected user (must satisfy the password policy):
    python -m scripts.set_user_passwords --password 'S3cure!Pass9'

    # Restrict to specific emails (comma-separated):
    python -m scripts.set_user_passwords --emails a@example.com,b@example.com

    # Force-reset EVERYONE (including users who already have a password).
    # Destructive: revokes all their sessions. Requires --yes:
    python -m scripts.set_user_passwords --all --yes

Behavior:
  - Default scope: ACTIVE users with password_hash IS NULL.
  - --random (default when --password is absent): unique 16-char urlsafe
    password per user, printed as `email<TAB>password` exactly once.
  - Every touched user has all existing sessions revoked.
  - Passwords are hashed with Argon2id before storage; plaintext is never
    persisted and never written to any file.
"""

import argparse
import asyncio
import re
import secrets
import sys

sys.path.insert(0, sys.path[0] if __name__ == "__main__" else ".")
# Allow both `python -m scripts.set_user_passwords` and direct execution.
if __package__ in (None, ""):
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from shared.database import AsyncSessionLocal
from shared.models import User, UserStatus, AuthSession
from shared.auth import hash_password, validate_password_policy
from shared.auth import _session_cache_invalidate
from shared.datetime_utils import utc_now


def generate_password() -> str:
    """16-char urlsafe password, guaranteed to satisfy the policy
    (≥10 chars, at least one letter and one digit — ~7% of raw
    urlsafe tokens contain no digit, so retry until one does)."""
    while True:
        pw = secrets.token_urlsafe(12)
        if re.search(r"\d", pw) and re.search(r"[A-Za-z]", pw):
            return pw


async def migrate(password: str | None, emails: list[str] | None, force_all: bool) -> int:
    query = select(User).where(User.status == UserStatus.ACTIVE)
    if not force_all:
        query = query.where(User.password_hash.is_(None))
    if emails:
        query = query.where(User.email.in_(emails))

    count = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(query.order_by(User.email))
        users = result.scalars().all()
        if not users:
            print("No matching users found — nothing to do.")
            return 0

        print(f"Setting initial passwords for {len(users)} user(s)...\n")
        for user in users:
            pw = password or generate_password()
            policy_error = validate_password_policy(pw)
            if policy_error:
                print(f"ERROR: password policy rejected for {user.email}: {policy_error}")
                return 1
            user.password_hash = hash_password(pw)
            user.failed_login_count = 0
            user.locked_until = None
            user.updated_at = utc_now()

            # Revoke existing sessions (force-reset semantics).
            sessions = (await db.execute(
                select(AuthSession).where(AuthSession.user_id == user.id)
            )).scalars().all()
            for s in sessions:
                await db.delete(s)
                _session_cache_invalidate(s.token_hash)

            if password:
                print(f"  [OK] {user.email}  (shared password applied)")
            else:
                # Printed exactly once — the only record of this password.
                print(f"  {user.email}\t{pw}")
            count += 1

        await db.commit()
    print(f"\nDone. {count} user(s) updated.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--password", help="One password for all affected users (else a unique random one per user).")
    parser.add_argument("--emails", help="Comma-separated list of emails to restrict to.")
    parser.add_argument("--all", action="store_true", help="Include users who already have a password (force reset).")
    parser.add_argument("--yes", action="store_true", help="Confirm the destructive --all reset.")
    args = parser.parse_args()

    if args.all and not args.yes:
        print("ERROR: --all force-resets every user and revokes all their sessions. Re-run with --yes to confirm.")
        sys.exit(1)
    if args.password:
        policy_error = validate_password_policy(args.password)
        if policy_error:
            print(f"ERROR: {policy_error}")
            sys.exit(1)

    emails = [e.strip() for e in args.emails.split(",") if e.strip()] if args.emails else None
    sys.exit(asyncio.run(migrate(args.password, emails, args.all)))


if __name__ == "__main__":
    main()
