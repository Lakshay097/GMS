"""
Settings & Master Data API routes per PRS §18-20.
Provides endpoints for holiday calendar, working days, assets, and discrepancy categories.
"""
from datetime import date
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.errors import ValidationError as ServiceValidationError

router = APIRouter(prefix="/settings/master-data", tags=["settings-master-data"])


# ── Schemas ──────────────────────────────────────────────────────────────

class HolidayCreate(BaseModel):
    holiday_date: date
    label: str
    school_id: Optional[UUID] = None
    recurrence_type: str = "one_time"


class HolidayUpdate(BaseModel):
    holiday_date: Optional[date] = None
    label: Optional[str] = None
    recurrence_type: Optional[str] = None


class HolidayResponse(BaseModel):
    id: UUID
    school_id: Optional[UUID]
    holiday_date: date
    label: str
    recurrence_type: str
    created_by: Optional[UUID]
    created_at: str


class WorkingDaysUpdate(BaseModel):
    working_days: List[str] = Field(..., description="List of day abbreviations (e.g., ['mon', 'tue', 'wed', 'thu', 'fri'])")


class WorkingDaysResponse(BaseModel):
    school_id: UUID
    working_days: List[str]


class AssetCreate(BaseModel):
    school_id: UUID
    name: str
    category_code: Optional[str] = None
    location_id: Optional[UUID] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    category_code: Optional[str] = None
    location_id: Optional[UUID] = None


class AssetResponse(BaseModel):
    id: UUID
    school_id: UUID
    name: str
    category_code: Optional[str]
    location_id: Optional[UUID]
    status: str
    created_at: str
    updated_at: str


class DiscrepancyCategoryCreate(BaseModel):
    name: str
    allow_delegate: bool = False


class DiscrepancyCategoryUpdate(BaseModel):
    name: Optional[str] = None
    allow_delegate: Optional[bool] = None
    status: Optional[str] = None


class DiscrepancyCategoryResponse(BaseModel):
    id: UUID
    name: str
    status: str
    allow_delegate: bool
    created_at: str


# ── Holiday Calendar Endpoints ────────────────────────────────────────────

@router.post("/holidays", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
async def create_holiday(
    holiday: HolidayCreate,
    db: AsyncSession = Depends(get_db),
    created_by: Optional[UUID] = None,
):
    """Create a new holiday entry."""
    from platform_services.master_data_service import MasterDataService
    service = MasterDataService(db)
    try:
        result = await service.add_holiday(
            holiday_date=holiday.holiday_date,
            label=holiday.label,
            school_id=holiday.school_id,
            recurrence_type=holiday.recurrence_type,
            created_by=created_by,
        )
        return HolidayResponse(
            id=result.id,
            school_id=result.school_id,
            holiday_date=result.holiday_date,
            label=result.label,
            recurrence_type=result.recurrence_type,
            created_by=result.created_by,
            created_at=result.created_at.isoformat(),
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/holidays", response_model=List[HolidayResponse])
async def get_holidays(
    school_id: Optional[UUID] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get holidays with optional filters."""
    from platform_services.master_data_service import MasterDataService
    service = MasterDataService(db)
    holidays = await service.get_holidays(school_id=school_id, from_date=from_date, to_date=to_date)
    return [
        HolidayResponse(
            id=h.id,
            school_id=h.school_id,
            holiday_date=h.holiday_date,
            label=h.label,
            recurrence_type=h.recurrence_type,
            created_by=h.created_by,
            created_at=h.created_at.isoformat(),
        )
        for h in holidays
    ]


@router.get("/holidays/{holiday_id}", response_model=HolidayResponse)
async def get_holiday(holiday_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific holiday by ID."""
    from shared.platform_models import OrganizationHoliday
    holiday = await db.get(OrganizationHoliday, holiday_id)
    if not holiday:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
    return HolidayResponse(
        id=holiday.id,
        school_id=holiday.school_id,
        holiday_date=holiday.holiday_date,
        label=holiday.label,
        recurrence_type=holiday.recurrence_type,
        created_by=holiday.created_by,
        created_at=holiday.created_at.isoformat(),
    )


@router.patch("/holidays/{holiday_id}", response_model=HolidayResponse)
async def update_holiday(holiday_id: UUID, holiday: HolidayUpdate, db: AsyncSession = Depends(get_db)):
    """Update a holiday entry."""
    from platform_services.master_data_service import MasterDataService
    service = MasterDataService(db)
    try:
        result = await service.update_holiday(
            holiday_id,
            holiday_date=holiday.holiday_date,
            label=holiday.label,
            recurrence_type=holiday.recurrence_type,
        )
        return HolidayResponse(
            id=result.id,
            school_id=result.school_id,
            holiday_date=result.holiday_date,
            label=result.label,
            recurrence_type=result.recurrence_type,
            created_by=result.created_by,
            created_at=result.created_at.isoformat(),
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(holiday_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a holiday entry."""
    from platform_services.master_data_service import MasterDataService
    service = MasterDataService(db)
    try:
        await service.delete_holiday(holiday_id)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── Working Days Endpoints ─────────────────────────────────────────────────

@router.get("/schools/{school_id}/working-days", response_model=WorkingDaysResponse)
async def get_working_days(school_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get working days configuration for a school."""
    from platform_services.master_data_service import MasterDataService
    service = MasterDataService(db)
    try:
        working_days = await service.get_school_working_days(school_id)
        return WorkingDaysResponse(school_id=school_id, working_days=working_days)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/schools/{school_id}/working-days", response_model=WorkingDaysResponse)
async def update_working_days(school_id: UUID, data: WorkingDaysUpdate, db: AsyncSession = Depends(get_db)):
    """Update working days configuration for a school."""
    from platform_services.master_data_service import MasterDataService
    service = MasterDataService(db)
    try:
        school = await service.update_school_working_days(school_id, data.working_days)
        return WorkingDaysResponse(school_id=school_id, working_days=school.working_days or [])
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── Assets Endpoints ─────────────────────────────────────────────────────

@router.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(asset: AssetCreate, db: AsyncSession = Depends(get_db)):
    """Create a new asset."""
    service = MasterDataService(db)
    try:
        result = await service.create_asset(
            school_id=asset.school_id,
            name=asset.name,
            category_code=asset.category_code,
            location_id=asset.location_id,
        )
        return AssetResponse(
            id=result.id,
            school_id=result.school_id,
            name=result.name,
            category_code=result.category_code,
            location_id=result.location_id,
            status=result.status.value,
            created_at=result.created_at.isoformat(),
            updated_at=result.updated_at.isoformat(),
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/schools/{school_id}/assets", response_model=List[AssetResponse])
async def get_school_assets(school_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get active assets for a school."""
    service = MasterDataService(db)
    assets = await service.get_active_assets(school_id)
    return [
        AssetResponse(
            id=a.id,
            school_id=a.school_id,
            name=a.name,
            category_code=a.category_code,
            location_id=a.location_id,
            status=a.status.value,
            created_at=a.created_at.isoformat(),
            updated_at=a.updated_at.isoformat(),
        )
        for a in assets
    ]


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific asset by ID."""
    service = MasterDataService(db)
    asset = await service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return AssetResponse(
        id=asset.id,
        school_id=asset.school_id,
        name=asset.name,
        category_code=asset.category_code,
        location_id=asset.location_id,
        status=asset.status.value,
        created_at=asset.created_at.isoformat(),
        updated_at=asset.updated_at.isoformat(),
    )


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: UUID, asset: AssetUpdate, db: AsyncSession = Depends(get_db)):
    """Update an asset."""
    service = MasterDataService(db)
    try:
        result = await service.update_asset(
            asset_id,
            name=asset.name,
            category_code=asset.category_code,
            location_id=asset.location_id,
        )
        return AssetResponse(
            id=result.id,
            school_id=result.school_id,
            name=result.name,
            category_code=result.category_code,
            location_id=result.location_id,
            status=result.status.value,
            created_at=result.created_at.isoformat(),
            updated_at=result.updated_at.isoformat(),
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/assets/{asset_id}/retire", response_model=AssetResponse)
async def retire_asset(asset_id: UUID, db: AsyncSession = Depends(get_db)):
    """Retire an asset (BR-23: forward-only, never hard delete)."""
    service = MasterDataService(db)
    try:
        result = await service.retire_asset(asset_id)
        return AssetResponse(
            id=result.id,
            school_id=result.school_id,
            name=result.name,
            category_code=result.category_code,
            location_id=result.location_id,
            status=result.status.value,
            created_at=result.created_at.isoformat(),
            updated_at=result.updated_at.isoformat(),
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── Discrepancy Categories Endpoints ───────────────────────────────────────

@router.post("/discrepancy-categories", response_model=DiscrepancyCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_discrepancy_category(category: DiscrepancyCategoryCreate, db: AsyncSession = Depends(get_db)):
    """Create a new discrepancy category."""
    service = MasterDataService(db)
    try:
        result = await service.create_discrepancy_category(
            name=category.name,
            allow_delegate=category.allow_delegate,
        )
        return DiscrepancyCategoryResponse(
            id=result.id,
            name=result.name,
            status=result.status,
            allow_delegate=result.allow_delegate,
            created_at=result.created_at.isoformat(),
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/discrepancy-categories", response_model=List[DiscrepancyCategoryResponse])
async def get_discrepancy_categories(active_only: bool = True, db: AsyncSession = Depends(get_db)):
    """Get discrepancy categories."""
    service = MasterDataService(db)
    categories = await service.get_discrepancy_categories(active_only=active_only)
    return [
        DiscrepancyCategoryResponse(
            id=c.id,
            name=c.name,
            status=c.status,
            allow_delegate=c.allow_delegate,
            created_at=c.created_at.isoformat(),
        )
        for c in categories
    ]


@router.get("/discrepancy-categories/{category_id}", response_model=DiscrepancyCategoryResponse)
async def get_discrepancy_category(category_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific discrepancy category by ID."""
    from shared.platform_models import DiscrepancyCategory
    category = await db.get(DiscrepancyCategory, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discrepancy category not found")
    return DiscrepancyCategoryResponse(
        id=category.id,
        name=category.name,
        status=category.status,
        allow_delegate=category.allow_delegate,
        created_at=category.created_at.isoformat(),
    )


@router.patch("/discrepancy-categories/{category_id}", response_model=DiscrepancyCategoryResponse)
async def update_discrepancy_category(category_id: UUID, category: DiscrepancyCategoryUpdate, db: AsyncSession = Depends(get_db)):
    """Update a discrepancy category."""
    service = MasterDataService(db)
    try:
        result = await service.update_discrepancy_category(
            category_id,
            name=category.name,
            allow_delegate=category.allow_delegate,
            status=category.status,
        )
        return DiscrepancyCategoryResponse(
            id=result.id,
            name=result.name,
            status=result.status,
            allow_delegate=result.allow_delegate,
            created_at=result.created_at.isoformat(),
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/discrepancy-categories/{category_id}/deprecate", response_model=DiscrepancyCategoryResponse)
async def deprecate_discrepancy_category(category_id: UUID, db: AsyncSession = Depends(get_db)):
    """Deprecate a discrepancy category (forward-only, never delete)."""
    service = MasterDataService(db)
    try:
        result = await service.deprecate_discrepancy_category(category_id)
        return DiscrepancyCategoryResponse(
            id=result.id,
            name=result.name,
            status=result.status,
            allow_delegate=result.allow_delegate,
            created_at=result.created_at.isoformat(),
        )
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
