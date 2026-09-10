"""Seed a few ExpirationRecord rows for live preview verification (dev DB only)."""
import asyncio
from datetime import timedelta

from dotenv import load_dotenv
from sqlalchemy import select

import shared.models  # resolve circular import first
load_dotenv()

from shared.database import AsyncSessionLocal
from shared.models import School
from shared.platform_models import (
    ExpirationEntityType,
    ExpirationRecord,
    ExpirationStatus,
)
from shared.datetime_utils import utc_now


async def main() -> None:
    async with AsyncSessionLocal() as db:
        school = (await db.execute(select(School))).scalars().first()
        if school is None:
            print("no school found; aborting")
            return
        now = utc_now()
        records = [
            ExpirationRecord(
                school_id=school.id,
                entity_type=ExpirationEntityType.CERTIFICATE,
                title="Fire Safety Certificate",
                expires_at=now + timedelta(days=5),
                status=ExpirationStatus.EXPIRING_SOON,
                reminder_lead_days=30,
                created_at=now,
                updated_at=now,
            ),
            ExpirationRecord(
                school_id=school.id,
                entity_type=ExpirationEntityType.INSURANCE,
                title="Building Insurance Policy",
                expires_at=now - timedelta(days=3),
                status=ExpirationStatus.EXPIRED,
                reminder_lead_days=30,
                created_at=now,
                updated_at=now,
            ),
            ExpirationRecord(
                school_id=school.id,
                entity_type=ExpirationEntityType.PERMIT,
                title="Lab Chemical Permit",
                expires_at=now + timedelta(days=200),
                status=ExpirationStatus.ACTIVE,
                reminder_lead_days=30,
                created_at=now,
                updated_at=now,
            ),
        ]
        db.add_all(records)
        await db.commit()
        print("school:", school.name, "| inserted:", len(records))


asyncio.run(main())
