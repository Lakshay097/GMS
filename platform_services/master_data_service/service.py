"""
Master Data Service — Architecture §5.6, R-14.
Forward-only reference data; existing FK references never repointed retroactively.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.errors import ConflictError, ValidationError
from shared.platform_models import (
    Asset,
    AssetStatus,
    DiscrepancyCategory,
    MasterDataEntry,
    MasterDataStatus,
    OrganizationHoliday,
)
from shared.models import School


class MasterDataService:
    """Central forward-only reference data service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Master Data Entries ──────────────────────────────────────────────

    async def create_entry(
        self,
        category: str,
        code: str,
        label: str,
    ) -> MasterDataEntry:
        existing = await self.db.get(MasterDataEntry, {"code": code, "category": category})
        if existing:
            raise ConflictError(f"Master data entry already exists: {category}/{code}")
        entry = MasterDataEntry(category=category, code=code, label=label)
        self.db.add(entry)
        await self.db.commit()
        return entry

    async def deprecate_entry(self, category: str, code: str) -> MasterDataEntry:
        """Forward-only: deprecate, never delete or repoint (R-14)."""
        entry = await self.db.get(MasterDataEntry, {"code": code, "category": category})
        if entry is None:
            raise ValidationError(f"Unknown master data entry: {category}/{code}")
        entry.status = MasterDataStatus.DEPRECATED
        await self.db.commit()
        return entry

    async def get_active_entries(self, category: str) -> list[MasterDataEntry]:
        result = await self.db.execute(
            select(MasterDataEntry).where(
                MasterDataEntry.category == category,
                MasterDataEntry.status == MasterDataStatus.ACTIVE,
            )
        )
        return list(result.scalars().all())

    # ── Discrepancy Categories (v1.5) ────────────────────────────────────

    async def create_discrepancy_category(
        self,
        name: str,
        *,
        allow_delegate: bool = False,
    ) -> DiscrepancyCategory:
        category = DiscrepancyCategory(name=name, allow_delegate=allow_delegate)
        self.db.add(category)
        await self.db.commit()
        return category

    async def get_discrepancy_categories(self, active_only: bool = True) -> list[DiscrepancyCategory]:
        query = select(DiscrepancyCategory)
        if active_only:
            query = query.where(DiscrepancyCategory.status == "active")
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_discrepancy_category(
        self,
        category_id: UUID,
        *,
        name: Optional[str] = None,
        allow_delegate: Optional[bool] = None,
        status: Optional[str] = None,
    ) -> DiscrepancyCategory:
        category = await self.db.get(DiscrepancyCategory, category_id)
        if category is None:
            raise ValidationError(f"Unknown discrepancy category: {category_id}")
        
        if name is not None:
            category.name = name
        if allow_delegate is not None:
            category.allow_delegate = allow_delegate
        if status is not None:
            category.status = status
        
        await self.db.commit()
        return category

    async def deprecate_discrepancy_category(self, category_id: UUID) -> DiscrepancyCategory:
        """Forward-only: deprecate, never delete (R-14)."""
        category = await self.db.get(DiscrepancyCategory, category_id)
        if category is None:
            raise ValidationError(f"Unknown discrepancy category: {category_id}")
        category.status = "deprecated"
        await self.db.commit()
        return category

    # ── Organization Holiday Calendar (v1.5) ───────────────────────────────

    async def add_holiday(
        self,
        holiday_date: date,
        label: str,
        *,
        school_id: Optional[UUID] = None,
        recurrence_type: str = "one_time",
        created_by: Optional[UUID] = None,
    ) -> OrganizationHoliday:
        holiday = OrganizationHoliday(
            school_id=school_id,
            holiday_date=holiday_date,
            label=label,
            recurrence_type=recurrence_type,
            created_by=created_by,
        )
        self.db.add(holiday)
        await self.db.commit()
        return holiday

    async def get_holidays(
        self,
        *,
        school_id: Optional[UUID] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> list[OrganizationHoliday]:
        query = select(OrganizationHoliday)
        if school_id is not None:
            query = query.where(
                (OrganizationHoliday.school_id == school_id)
                | (OrganizationHoliday.school_id.is_(None))
            )
        if from_date:
            query = query.where(OrganizationHoliday.holiday_date >= from_date)
        if to_date:
            query = query.where(OrganizationHoliday.holiday_date <= to_date)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def is_holiday(self, check_date: date, school_id: Optional[UUID] = None) -> bool:
        holidays = await self.get_holidays(
            school_id=school_id,
            from_date=check_date,
            to_date=check_date,
        )
        return len(holidays) > 0

    async def update_holiday(
        self,
        holiday_id: UUID,
        *,
        holiday_date: Optional[date] = None,
        label: Optional[str] = None,
        recurrence_type: Optional[str] = None,
    ) -> OrganizationHoliday:
        holiday = await self.db.get(OrganizationHoliday, holiday_id)
        if holiday is None:
            raise ValidationError(f"Unknown holiday: {holiday_id}")
        
        if holiday_date is not None:
            holiday.holiday_date = holiday_date
        if label is not None:
            holiday.label = label
        if recurrence_type is not None:
            holiday.recurrence_type = recurrence_type
        
        await self.db.commit()
        return holiday

    async def delete_holiday(self, holiday_id: UUID) -> None:
        holiday = await self.db.get(OrganizationHoliday, holiday_id)
        if holiday is None:
            raise ValidationError(f"Unknown holiday: {holiday_id}")
        await self.db.delete(holiday)
        await self.db.commit()

    # ── Working Days ─────────────────────────────────────────────────────

    @staticmethod
    def is_working_day(check_date: date, working_days: list[str]) -> bool:
        """Check if a date falls on a configured working day."""
        day_abbr = check_date.strftime("%a").lower()[:3]
        return day_abbr in [d.lower()[:3] for d in working_days]

    async def get_school_working_days(self, school_id: UUID) -> list[str]:
        """Get working days configuration for a school."""
        school = await self.db.get(School, school_id)
        if school is None:
            raise ValidationError(f"Unknown school: {school_id}")
        return school.working_days or []

    async def update_school_working_days(self, school_id: UUID, working_days: list[str]) -> School:
        """Update working days configuration for a school."""
        school = await self.db.get(School, school_id)
        if school is None:
            raise ValidationError(f"Unknown school: {school_id}")
        school.working_days = working_days
        await self.db.commit()
        return school

    # ── Assets (v1.5) ────────────────────────────────────────────────────

    async def create_asset(
        self,
        school_id: UUID,
        name: str,
        *,
        category_code: Optional[str] = None,
        location_id: Optional[UUID] = None,
    ) -> Asset:
        asset = Asset(
            school_id=school_id,
            name=name,
            category_code=category_code,
            location_id=location_id,
            status=AssetStatus.ACTIVE,
        )
        self.db.add(asset)
        await self.db.commit()
        return asset

    async def retire_asset(self, asset_id: UUID) -> Asset:
        """BR-23: assets are retired, never hard-deleted."""
        asset = await self.db.get(Asset, asset_id)
        if asset is None:
            raise ValidationError(f"Unknown asset: {asset_id}")
        asset.status = AssetStatus.RETIRED
        await self.db.commit()
        return asset

    async def get_active_assets(self, school_id: UUID) -> list[Asset]:
        result = await self.db.execute(
            select(Asset).where(Asset.school_id == school_id, Asset.status == AssetStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def get_asset(self, asset_id: UUID) -> Optional[Asset]:
        return await self.db.get(Asset, asset_id)

    async def update_asset(
        self,
        asset_id: UUID,
        *,
        name: Optional[str] = None,
        category_code: Optional[str] = None,
        location_id: Optional[UUID] = None,
    ) -> Asset:
        asset = await self.db.get(Asset, asset_id)
        if asset is None:
            raise ValidationError(f"Unknown asset: {asset_id}")
        
        if name is not None:
            asset.name = name
        if category_code is not None:
            asset.category_code = category_code
        if location_id is not None:
            asset.location_id = location_id
        
        await self.db.commit()
        return asset

    async def is_asset_active(self, asset_id: UUID) -> bool:
        """Check if asset is active (BR-23 enforcement)."""
        asset = await self.db.get(Asset, asset_id)
        if asset is None:
            return False
        return asset.status == AssetStatus.ACTIVE
