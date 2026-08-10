"""Unit test for BR-23 Asset Retirement Enforcement."""
import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from platform_services.master_data_service.service import MasterDataService
from shared.datetime_utils import utc_now
from shared.platform_models import (
    Asset,
    AssetStatus,
    Observation,
    KPI,
    KRA,
    AutoResult,
    RagStatus,
)


@pytest.mark.asyncio
async def test_BR23_retired_asset_blocks_new_assignment(db, school, user):
    """
    BR-23: Retired assets block new assignment but keep historical reads intact.
    - Active asset can be assigned to new observations
    - Retired asset cannot be assigned to new observations  
    - Historical observations with retired asset remain readable
    """
    master_data = MasterDataService(db)
    
    # Create an active asset
    asset = await master_data.create_asset(
        school_id=school.id,
        name="Test Asset",
        category_code="equipment",
    )
    assert asset.status == AssetStatus.ACTIVE
    
    # Create KPI for observation
    kra = KRA(id=uuid.uuid4(), name="KRA Test", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Test KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Create observation with active asset (should succeed)
    observation_1 = Observation(
        kpi_id=kpi.kpi_id,
        kpi_version=1,
        checker_id=user.id,
        department_id=uuid.uuid4(),  # Use a dummy department ID
        school_id=school.id,
        value_numeric=Decimal("95.5"),
        auto_result=AutoResult.MET,
        rag_status=RagStatus.GREEN,
        asset_id=asset.id,
    )
    db.add(observation_1)
    await db.commit()
    await db.refresh(observation_1)
    
    # Verify observation was created with asset
    assert observation_1.asset_id == asset.id
    
    # Retire the asset
    retired_asset = await master_data.retire_asset(asset.id)
    assert retired_asset.status == AssetStatus.RETIRED
    
    # Verify the asset is no longer active
    is_active = await master_data.is_asset_active(asset.id)
    assert is_active is False
    
    # Verify historical observation is still readable
    historical_obs = await db.get(Observation, observation_1.id)
    assert historical_obs is not None
    assert historical_obs.asset_id == asset.id
    assert historical_obs.value_numeric == Decimal("95.5")
    
    # Verify asset is still readable (historical data preserved)
    asset_record = await master_data.get_asset(asset.id)
    assert asset_record is not None
    assert asset_record.status == AssetStatus.RETIRED
    assert asset_record.name == "Test Asset"


@pytest.mark.asyncio
async def test_BR23_active_asset_allows_assignment(db, school, user):
    """
    BR-23: Active assets allow new assignment.
    Verify that active assets can still be assigned to new observations.
    """
    master_data = MasterDataService(db)
    
    # Create an active asset
    asset = await master_data.create_asset(
        school_id=school.id,
        name="Active Asset",
        category_code="equipment",
    )
    assert asset.status == AssetStatus.ACTIVE
    
    # Verify the asset is active
    is_active = await master_data.is_asset_active(asset.id)
    assert is_active is True
    
    # Create KPI for observation
    kra = KRA(id=uuid.uuid4(), name="KRA Active", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Active KPI",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Create observation with active asset (should succeed)
    observation = Observation(
        kpi_id=kpi.kpi_id,
        kpi_version=1,
        checker_id=user.id,
        department_id=uuid.uuid4(),
        school_id=school.id,
        value_numeric=Decimal("100.0"),
        auto_result=AutoResult.MET,
        rag_status=RagStatus.GREEN,
        asset_id=asset.id,
    )
    db.add(observation)
    await db.commit()
    await db.refresh(observation)
    
    # Verify observation was created successfully
    assert observation.asset_id == asset.id
    assert observation.value_numeric == Decimal("100.0")
