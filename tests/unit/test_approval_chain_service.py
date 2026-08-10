"""
Unit tests for ApprovalChainService functionality.
Tests the service in isolation without the full E2E workflow.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import uuid
import pytest

from modules.audit_discrepancy.services.approval_chain_service import ApprovalChainService
from platform_services.workflow_engine.service import WorkflowEngine
from shared.platform_models import DiscrepancyApprovalChainConfig
from shared.datetime_utils import utc_now


@pytest.mark.asyncio
async def test_approval_chain_service_invalid_level_structure(db, school, department):
    """
    Test that ApprovalChainService validates level structure correctly.
    """
    # Initialize services
    workflow_engine = WorkflowEngine(db)
    approval_chain_service = ApprovalChainService(db, workflow_engine)
    
    # Test with invalid level sequence
    invalid_levels = [
        {"level": 1, "role_id": uuid.uuid4(), "auto_escalation_sla_hours": 24},
        {"level": 3, "role_id": uuid.uuid4(), "auto_escalation_sla_hours": 48},  # Skipped level 2
    ]
    
    with pytest.raises(Exception) as exc_info:
        await approval_chain_service.create_approval_chain(
            levels=invalid_levels,
            created_by=uuid.uuid4()
        )
    
    # Verify validation error
    assert "level" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_approval_chain_service_missing_role_id(db, school, department):
    """
    Test that ApprovalChainService requires role_id in levels.
    """
    # Initialize services
    workflow_engine = WorkflowEngine(db)
    approval_chain_service = ApprovalChainService(db, workflow_engine)
    
    # Test with missing role_id
    invalid_levels = [
        {"level": 1, "auto_escalation_sla_hours": 24},  # Missing role_id
    ]
    
    with pytest.raises(Exception) as exc_info:
        await approval_chain_service.create_approval_chain(
            levels=invalid_levels,
            created_by=uuid.uuid4()
        )
    
    # Verify validation error
    assert "role" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_approval_chain_service_empty_levels(db, school, department):
    """
    Test that ApprovalChainService requires at least one level.
    """
    # Initialize services
    workflow_engine = WorkflowEngine(db)
    approval_chain_service = ApprovalChainService(db, workflow_engine)
    
    # Test with empty levels
    with pytest.raises(Exception) as exc_info:
        await approval_chain_service.create_approval_chain(
            levels=[],
            created_by=uuid.uuid4()
        )
    
    # Verify validation error
    assert "level" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_approval_chain_service_get_nonexistent(db, school, department):
    """
    Test that ApprovalChainService returns None for nonexistent chain.
    """
    # Initialize services
    workflow_engine = WorkflowEngine(db)
    approval_chain_service = ApprovalChainService(db, workflow_engine)
    
    # Try to get a nonexistent chain
    nonexistent_chain = await approval_chain_service.get_approval_chain(uuid.uuid4())
    assert nonexistent_chain is None


@pytest.mark.asyncio
async def test_approval_chain_service_activate_nonexistent(db, school, department):
    """
    Test that ApprovalChainService cannot activate a nonexistent chain.
    """
    # Initialize services
    workflow_engine = WorkflowEngine(db)
    approval_chain_service = ApprovalChainService(db, workflow_engine)
    
    # Try to activate a nonexistent chain
    with pytest.raises(Exception):
        await approval_chain_service.activate_chain_version(uuid.uuid4())
