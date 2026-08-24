import asyncio
import uuid
from shared.database import AsyncSessionLocal
from sqlalchemy import text
from shared.datetime_utils import utc_now

async def create_superadmin():
    async with AsyncSessionLocal() as db:
        # check if already exists
        existing = await db.execute(
            text("SELECT id FROM users WHERE clerk_user_id = :cuid OR email = :email"),
            {"cuid": "user_3I4mex7L85J3G0K2IIItLWhQIH5", "email": "lakshay.kumar@pw.live"}
        )
        row = existing.fetchone()
        if row:
            print(f"User already exists with id: {row[0]}")
            return

        user_id = uuid.uuid4()
        now = utc_now()

        await db.execute(
            text("""INSERT INTO users
                (id, clerk_user_id, email, full_name, school_id, department_id,
                 status, roles, mfa_enabled, phone, employee_id, created_at, updated_at, language_preference)
                VALUES
                (:id, :clerk_user_id, :email, :full_name, :school_id, :department_id,
                 :status, :roles, :mfa_enabled, :phone, :employee_id, :created_at, :updated_at, :language_preference)"""),
            {
                "id": user_id,
                "clerk_user_id": "user_3I4mex7L85J3G0K2IIItLWhQIH5",
                "email": "lakshay.kumar@pw.live",
                "full_name": "Lakshay Kumar",
                "school_id": None,
                "department_id": None,
                "status": "active",
                "roles": '["superadmin"]',
                "mfa_enabled": False,
                "phone": None,
                "employee_id": None,
                "created_at": now,
                "updated_at": now,
                "language_preference": "en",
            }
        )
        await db.commit()
        print(f"SuperAdmin created: {user_id}")

asyncio.run(create_superadmin())
