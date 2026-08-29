"""
Locations API routes per PRS §37.10, FR-189.
CRUD for per-floor/zone/wing scoping used by Event-Time observations.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.errors import ConflictError, ValidationError as ServiceValidationError
from shared.middleware.tenancy import require_tenant_context, TenantContext
from shared.platform_models import Location

router = APIRouter(prefix="/locations", tags=["locations"])


# ── Schemas ──────────────────────────────────────────────────────────────

class LocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location_type: str = Field("floor", description="floor | zone | wing | building")


class LocationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    location_type: Optional[str] = None
    status: Optional[str] = None


class LocationResponse(BaseModel):
    id: UUID
    school_id: UUID
    name: str
    location_type: str
    status: str
    created_at: str
    updated_at: str


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    location: LocationCreate,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Create a new location within the caller's school."""
    if not tenant_context.school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="School context required")

    school_id = UUID(tenant_context.school_id)

    # Check uniqueness
    existing = await db.execute(
        select(Location).where(
            Location.school_id == school_id,
            Location.name == location.name,
            Location.location_type == location.location_type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Location '{location.name}' ({location.location_type}) already exists for this school",
        )

    loc = Location(
        school_id=school_id,
        name=location.name,
        location_type=location.location_type,
        status="active",
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)

    return LocationResponse(
        id=loc.id,
        school_id=loc.school_id,
        name=loc.name,
        location_type=loc.location_type,
        status=loc.status,
        created_at=loc.created_at.isoformat(),
        updated_at=loc.updated_at.isoformat(),
    )


@router.get("/", response_model=List[LocationResponse])
async def list_locations(
    school_id: Optional[UUID] = None,
    location_type: Optional[str] = None,
    active_only: bool = True,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """List locations, scoped to the caller's school."""
    target_school = school_id or (UUID(tenant_context.school_id) if tenant_context.school_id else None)

    query = select(Location)
    if target_school:
        query = query.where(Location.school_id == target_school)
    if location_type:
        query = query.where(Location.location_type == location_type)
    if active_only:
        query = query.where(Location.status == "active")
    query = query.order_by(Location.location_type, Location.name)

    result = await db.execute(query)
    locations = result.scalars().all()

    return [
        LocationResponse(
            id=loc.id,
            school_id=loc.school_id,
            name=loc.name,
            location_type=loc.location_type,
            status=loc.status,
            created_at=loc.created_at.isoformat(),
            updated_at=loc.updated_at.isoformat(),
        )
        for loc in locations
    ]


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific location by ID."""
    loc = await db.get(Location, location_id)
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Scope check
    if tenant_context.school_id and str(loc.school_id) != tenant_context.school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    return LocationResponse(
        id=loc.id,
        school_id=loc.school_id,
        name=loc.name,
        location_type=loc.location_type,
        status=loc.status,
        created_at=loc.created_at.isoformat(),
        updated_at=loc.updated_at.isoformat(),
    )


@router.patch("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: UUID,
    update: LocationUpdate,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Update a location's name, type, or status."""
    loc = await db.get(Location, location_id)
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Scope check
    if tenant_context.school_id and str(loc.school_id) != tenant_context.school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    if update.name is not None:
        loc.name = update.name
    if update.location_type is not None:
        loc.location_type = update.location_type
    if update.status is not None:
        loc.status = update.status

    await db.commit()
    await db.refresh(loc)

    return LocationResponse(
        id=loc.id,
        school_id=loc.school_id,
        name=loc.name,
        location_type=loc.location_type,
        status=loc.status,
        created_at=loc.created_at.isoformat(),
        updated_at=loc.updated_at.isoformat(),
    )


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_location(
    location_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Archive a location (soft-delete, never hard delete)."""
    loc = await db.get(Location, location_id)
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Scope check
    if tenant_context.school_id and str(loc.school_id) != tenant_context.school_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    loc.status = "archived"
    await db.commit()
