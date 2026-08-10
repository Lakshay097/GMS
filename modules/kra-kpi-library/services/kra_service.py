"""
KRA service — PRS §22.
Global KPI Library is SuperAdmin-owned (R-43/BR-04).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.datetime_utils import utc_now
from shared.errors import ConflictError, NotFoundError, ValidationError
from shared.platform_models import KRA, KraStatus


class KraService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_kra(
        self,
        *,
        name: str,
        description: Optional[str] = None,
    ) -> KRA:
        existing = await self.db.execute(select(KRA).where(KRA.name == name))
        if existing.scalar_one_or_none():
            raise ConflictError(f"KRA already exists: {name}")

        kra = KRA(name=name, description=description, status=KraStatus.ACTIVE)
        self.db.add(kra)
        await self.db.commit()
        await self.db.refresh(kra)
        return kra

    async def list_kras(self, *, include_deprecated: bool = False) -> list[KRA]:
        query = select(KRA)
        if not include_deprecated:
            query = query.where(KRA.status == KraStatus.ACTIVE)
        result = await self.db.execute(query.order_by(KRA.name))
        return list(result.scalars().all())

    async def get_kra(self, kra_id: UUID) -> KRA:
        kra = await self.db.get(KRA, kra_id)
        if kra is None:
            raise NotFoundError("KRA")
        return kra

    async def update_kra(
        self,
        kra_id: UUID,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> KRA:
        kra = await self.get_kra(kra_id)
        if name is not None:
            kra.name = name
        if description is not None:
            kra.description = description
        if status is not None:
            if status not in {KraStatus.ACTIVE.value, KraStatus.DEPRECATED.value}:
                raise ValidationError("Invalid KRA status", field="status")
            kra.status = KraStatus(status)
        kra.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(kra)
        return kra
