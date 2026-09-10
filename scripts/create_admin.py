"""
Create the first SuperAdmin user for SchoolOps.

Usage:
    python -m scripts.create_admin --email admin@example.com --name "Platform Admin"
    python -m scripts.create_admin --email admin@example.com --name "Admin" --password 'S3cure!Pass9'
    python -m scripts.create_admin --email admin@example.com --name "Admin" --school SCH-TEST

- Never hardcodes credentials; the password is supplied interactively (hidden
  prompt) or via --password (for automation). The password is hashed with
  Argon2id before storage — plaintext is never persisted.
- SuperAdmins have school_id = NULL (they manage all schools).
- Use --school <code> to also create the school first, or --create-school
  "School Name" to create a brand-new school with the given code.
"""

import argparse
import asyncio
import getpass
import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from shared.database import AsyncSessionLocal, engine
from shared.models import User, UserStatus, UserRole, School, SchoolStatus
from shared.auth import hash_password, validate_password_policy
from shared.datetime_utils import utc_now


async def create_superadmin(
    email: str,
    full_name: str,
    password: str,
    school_code: str | None = None,
    create_school_name: str | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        # ── Validate password policy ────────────────────────────────────
        policy_error = validate_password_policy(password)
        if policy_error:
            print(f"ERROR: {policy_error}")
            sys.exit(1)

        # ── Guard: at least one SuperAdmin already exists? ──────────────
        existing_superadmins = await db.execute(
            select(User).where(User.roles.contains(["superadmin"]), User.status == UserStatus.ACTIVE)
        )
        if existing_superadmins.scalars().first() is not None:
            print("WARNING: An active SuperAdmin already exists.")
            if "--force" not in sys.argv:
                print("Re-run with --force to create another SuperAdmin.")
                sys.exit(1)

        # ── Guard: email uniqueness (including archived users) ──────────
        existing_email = await db.execute(select(User).where(User.email == email))
        if existing_email.scalar_one_or_none() is not None:
            print(f"ERROR: A user with email {email} already exists (may be archived).")
            sys.exit(1)

        # ── Resolve / create school ─────────────────────────────────────
        school = None
        if school_code:
            result = await db.execute(select(School).where(School.code == school_code))
            school = result.scalar_one_or_none()
            if school is None and create_school_name:
                school = School(
                    name=create_school_name,
                    code=school_code,
                    status=SchoolStatus.ACTIVE,
                )
                db.add(school)
                await db.flush()
                print(f"[OK] Created school: {school.name} ({school.code})")
            if school is None:
                print(f"ERROR: School code '{school_code}' not found. Use --create-school to create it.")
                sys.exit(1)

        # ── Create the SuperAdmin ───────────────────────────────────────
        user = User(
            id=uuid4(),
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            school_id=school.id if school else None,
            department_id=None,
            status=UserStatus.ACTIVE,
            roles=[UserRole.SUPERADMIN.value],
            mfa_enabled=False,
            language_preference="en",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(user)
        await db.commit()

        print("[OK] SuperAdmin created:")
        print(f"     Email: {user.email}")
        print(f"     Name:  {user.full_name}")
        print(f"     Role:  superadmin")
        print(f"     School: {school.code if school else '(none — manages all schools)'}")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first SuperAdmin for SchoolOps.")
    parser.add_argument("--email", required=True, help="SuperAdmin email address")
    parser.add_argument("--name", required=True, help="Full name of the SuperAdmin")
    parser.add_argument("--password", help="Password (omit to be prompted securely)")
    parser.add_argument("--school", help="Attach the admin to this existing school code")
    parser.add_argument("--create-school", metavar="NAME",
                        help="Create a new school with --school <code> and this name first")
    parser.add_argument("--force", action="store_true",
                        help="Allow creating additional SuperAdmins when one already exists")
    args = parser.parse_args()

    password = args.password
    if not password:
        password = getpass.getpass("Password for the new SuperAdmin: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("ERROR: Passwords do not match.")
            sys.exit(1)

    if not password:
        print("ERROR: Password is required.")
        sys.exit(1)

    asyncio.run(create_superadmin(
        email=args.email,
        full_name=args.name,
        password=password,
        school_code=args.school,
        create_school_name=args.create_school,
    ))


if __name__ == "__main__":
    main()
