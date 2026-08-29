"""
Feature Flags API routes per PRS §56.
SuperAdmin can list and toggle feature flags for phased rollout.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.middleware import get_current_user
from shared.platform_models import FeatureFlag

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


class FeatureFlagResponse(BaseModel):
    flag_key: str
    enabled: bool
    description: str | None = None
    updated_at: str


class FeatureFlagToggleRequest(BaseModel):
    enabled: bool


@router.get("/", response_model=List[FeatureFlagResponse])
async def list_feature_flags(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all feature flags. All authenticated users can read."""
    result = await db.execute(select(FeatureFlag).order_by(FeatureFlag.flag_key))
    flags = result.scalars().all()
    return [
        FeatureFlagResponse(
            flag_key=f.flag_key,
            enabled=f.enabled,
            description=f.description,
            updated_at=f.updated_at.isoformat(),
        )
        for f in flags
    ]


@router.patch("/{flag_key}", response_model=FeatureFlagResponse)
async def toggle_feature_flag(
    flag_key: str,
    request: FeatureFlagToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Toggle a feature flag. SuperAdmin only."""
    # Permission check
    normalized_roles = [r.lower() if isinstance(r, str) else r for r in current_user.roles]
    if "superadmin" not in normalized_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SuperAdmin can toggle feature flags",
        )

    result = await db.execute(
        select(FeatureFlag).where(FeatureFlag.flag_key == flag_key)
    )
    flag = result.scalar_one_or_none()

    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{flag_key}' not found",
        )

    flag.enabled = request.enabled
    await db.commit()
    await db.refresh(flag)

    return FeatureFlagResponse(
        flag_key=flag.flag_key,
        enabled=flag.enabled,
        description=flag.description,
        updated_at=flag.updated_at.isoformat(),
    )
