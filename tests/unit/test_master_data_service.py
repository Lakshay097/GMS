"""Unit tests for Master Data Service — Architecture §5.6, R-14."""
from datetime import date

import pytest

from platform_services.master_data_service.service import MasterDataService
from shared.errors import ConflictError
from shared.platform_models import AssetStatus, MasterDataStatus


@pytest.mark.asyncio
async def test_master_data_forward_only_deprecate(db):
    """R-14: deprecate but never delete or repoint."""
    service = MasterDataService(db)
    entry = await service.create_entry("frequency", "daily", "Daily")
    assert entry.status == MasterDataStatus.ACTIVE

    deprecated = await service.deprecate_entry("frequency", "daily")
    assert deprecated.status == MasterDataStatus.DEPRECATED


@pytest.mark.asyncio
async def test_master_data_no_duplicate_entries(db):
    service = MasterDataService(db)
    await service.create_entry("priority", "high", "High")
    with pytest.raises(ConflictError):
        await service.create_entry("priority", "high", "High Again")


@pytest.mark.asyncio
async def test_v15_discrepancy_category(db):
    service = MasterDataService(db)
    category = await service.create_discrepancy_category("Safety", allow_delegate=True)
    categories = await service.get_discrepancy_categories()
    assert len(categories) == 1
    assert categories[0].name == "Safety"


@pytest.mark.asyncio
async def test_v15_holiday_calendar(db, school, user):
    service = MasterDataService(db)
    holiday = await service.add_holiday(
        date(2026, 1, 26),
        "Republic Day",
        school_id=school.id,
        created_by=user.id,
    )
    assert await service.is_holiday(date(2026, 1, 26), school_id=school.id)


@pytest.mark.asyncio
async def test_v15_working_days(db):
    service = MasterDataService(db)
    assert service.is_working_day(date(2026, 8, 3), ["mon", "tue", "wed", "thu", "fri"])  # Monday
    assert not service.is_working_day(date(2026, 8, 2), ["mon", "tue", "wed", "thu", "fri"])  # Sunday


@pytest.mark.asyncio
async def test_v15_asset_lifecycle(db, school):
    """BR-23: assets retired, never deleted."""
    service = MasterDataService(db)
    asset = await service.create_asset(school.id, "Fire Extinguisher A")
    assert asset.status == AssetStatus.ACTIVE

    retired = await service.retire_asset(asset.id)
    assert retired.status == AssetStatus.RETIRED

    active = await service.get_active_assets(school.id)
    assert len(active) == 0
