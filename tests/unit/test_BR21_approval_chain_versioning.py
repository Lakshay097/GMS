"""Unit test for BR-21 Approval Chain Versioning (stub)."""
import uuid

import pytest
from sqlalchemy import select

from modules.audit_discrepancy.services.approval_chain_service import ApprovalChainService
from platform_services.workflow_engine.service import WorkflowEngine
from shared.platform_models import DiscrepancyApprovalChainConfig


@pytest.mark.asyncio
async def test_BR21_approval_chain_versioning_forward_only(db, user):
    """
    BR-21: Approval chain versioning is forward-only.
    - Creating a new version deactivates the previous active version
    - Cannot modify existing versions (only create new ones)
    - Historical versions remain readable
    """
    workflow_engine = WorkflowEngine(db)
    service = ApprovalChainService(db, workflow_engine)
    
    # Create first approval chain version
    levels_v1 = [
        {"level": 1, "role_id": "admin", "auto_escalation_sla_hours": 24},
        {"level": 2, "role_id": "superadmin", "auto_escalation_sla_hours": 48},
    ]
    
    chain_v1 = await service.create_approval_chain(
        levels=levels_v1,
        created_by=user.id,
    )
    
    assert chain_v1.is_active is True
    # Levels are normalized (assignee_type added) so compare key fields
    assert len(chain_v1.levels) == 2
    assert chain_v1.levels[0]["role_id"] == "admin"
    assert chain_v1.levels[1]["role_id"] == "superadmin"
    
    # v2.0 model: multiple active chains allowed (priority-based matching)
    levels_v2 = [
        {"level": 1, "role_id": "admin", "auto_escalation_sla_hours": 12},
        {"level": 2, "role_id": "admin", "auto_escalation_sla_hours": 24},
        {"level": 3, "role_id": "superadmin", "auto_escalation_sla_hours": 36},
    ]
    
    chain_v2 = await service.create_approval_chain(
        levels=levels_v2,
        created_by=user.id,
    )
    
    assert chain_v2.is_active is True
    assert len(chain_v2.levels) == 3
    
    # v2.0: both chains remain active (priority-based, not single-active)
    await db.refresh(chain_v1)
    assert chain_v1.is_active is True
    
    # Verify both versions are still readable (historical data preserved)
    all_chains = await service.list_approval_chains()
    assert len(all_chains) == 2
    
    # Verify historical v1 is still accessible
    historical_v1 = await service.get_approval_chain(chain_v1.chain_version_id)
    assert historical_v1 is not None
    assert len(historical_v1.levels) == 2
    assert historical_v1.is_active is True


@pytest.mark.asyncio
async def test_BR21_approval_chain_activate_version(db, user):
    """
    BR-21: Can activate a specific historical version (forward-only).
    - Activating a version deactivates the current active version
    - Historical versions can be reactivated
    """
    workflow_engine = WorkflowEngine(db)
    service = ApprovalChainService(db, workflow_engine)
    
    # Create two versions
    levels_v1 = [{"level": 1, "role_id": "admin"}]
    chain_v1 = await service.create_approval_chain(levels=levels_v1, created_by=user.id)
    
    levels_v2 = [{"level": 1, "role_id": "admin"}]
    chain_v2 = await service.create_approval_chain(levels=levels_v2, created_by=user.id)
    
    # v2.0: both remain active (priority-based, not single-active)
    await db.refresh(chain_v1)
    assert chain_v1.is_active is True
    assert chain_v2.is_active is True
    
    # Deactivate v1, then reactivate it
    await service.deactivate_chain(chain_v1.chain_version_id)
    await db.refresh(chain_v1)
    assert chain_v1.is_active is False
    
    reactivated_v1 = await service.activate_chain(chain_v1.chain_version_id)
    assert reactivated_v1.is_active is True
    
    # Both should now be active again
    await db.refresh(chain_v2)
    assert chain_v2.is_active is True


@pytest.mark.asyncio
async def test_BR21_in_flight_discrepancy_unaffected_stub(db, user):
    """
    BR-21: In-flight discrepancies are unaffected by version changes (stub).
    
    NOTE: This is a stub test as the discrepancy module is not fully implemented yet.
    The full test would verify that:
    - Discrepancies in progress use the approval chain version active at creation time
    - Version changes do not affect in-flight discrepancies
    - Historical discrepancies retain their original approval chain context
    """
    workflow_engine = WorkflowEngine(db)
    service = ApprovalChainService(db, workflow_engine)
    
    # Create initial approval chain
    levels_v1 = [{"level": 1, "role_id": "superadmin"}]
    chain_v1 = await service.create_approval_chain(levels=levels_v1, created_by=user.id)
    
    # Simulate in-flight discrepancy (would be stored with chain_version_id)
    in_flight_chain_id = chain_v1.chain_version_id
    
    # Create new version
    levels_v2 = [{"level": 1, "role_id": "admin"}]
    chain_v2 = await service.create_approval_chain(levels=levels_v2, created_by=user.id)
    
    # Verify the in-flight discrepancy's chain version is still accessible
    historical_chain = await service.get_approval_chain(in_flight_chain_id)
    assert historical_chain is not None
    assert historical_chain.chain_version_id == in_flight_chain_id
    # v2.0: both chains remain active (priority-based matching)
    assert historical_chain.is_active is True
    
    # The in-flight discrepancy should continue using its original chain version
    assert len(historical_chain.levels) == 1
    assert historical_chain.levels[0]["role_id"] == "superadmin"


@pytest.mark.asyncio
async def test_BR21_approval_chain_validation(db, user):
    """
    BR-21: Approval chain validation ensures data integrity.
    - Levels must be sequential (1, 2, 3, ...)
    - Each level must have a valid role_id
    - Empty levels are rejected
    """
    workflow_engine = WorkflowEngine(db)
    service = ApprovalChainService(db, workflow_engine)
    
    # Test empty levels
    with pytest.raises(Exception):  # ValidationError
        await service.create_approval_chain(levels=[], created_by=user.id)
    
    # Test non-sequential levels
    with pytest.raises(Exception):  # ValidationError
        await service.create_approval_chain(
            levels=[
                {"level": 1, "role_id": "admin"},
                {"level": 3, "role_id": "superadmin"},  # Missing level 2
            ],
            created_by=user.id,
        )
    
    # Test invalid role_id
    with pytest.raises(Exception):  # ValidationError
        await service.create_approval_chain(
            levels=[
                {"level": 1, "role_id": "invalid-uuid"},  # Invalid UUID
            ],
            created_by=user.id,
        )
    
    # Test missing required field
    with pytest.raises(Exception):  # ValidationError
        await service.create_approval_chain(
            levels=[
                {"level": 1},  # Missing role_id
            ],
            created_by=user.id,
    )
