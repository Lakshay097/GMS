"""
Approval Chain Service for Audit Discrepancy module.
Implements versioned forward-only approval chain configuration per BR-21.
Reuses WorkflowEngine for N-level approval sub-stages.
"""
from __future__ import annotations

from typing import Optional, List
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.platform_models import DiscrepancyApprovalChainConfig
from shared.errors import ValidationError, ConflictError
from platform_services.workflow_engine.service import (
    WorkflowEngine,
    ApprovalLevel,
    ApprovalChainConfig,
    TransitionDefinition,
    WorkflowDefinitionData,
)


class ApprovalChainService:
    """
    Versioned forward-only approval chain configuration service.
    BR-21: Approval chains are versioned and forward-only; in-flight discrepancies
    are not affected by version changes.
    """

    def __init__(self, db: AsyncSession, workflow_engine: WorkflowEngine):
        self.db = db
        self.workflow_engine = workflow_engine

    async def create_approval_chain(
        self,
        levels: List[dict],
        created_by: Optional[UUID] = None,
    ) -> DiscrepancyApprovalChainConfig:
        """
        Create a new approval chain version.
        
        Args:
            levels: List of approval level dicts with structure:
                [{"level": 1, "role_id": UUID, "auto_escalation_sla_hours": 24}, ...]
            created_by: User ID creating the chain version
            
        Returns:
            Created DiscrepancyApprovalChainConfig entity
            
        Raises:
            ValidationError: If levels structure is invalid
        """
        # Validate levels structure
        if not levels:
            raise ValidationError("Approval chain must have at least one level")
        
        for i, level in enumerate(levels, 1):
            if level.get("level") != i:
                raise ValidationError(f"Level {i} has incorrect level number: {level.get('level')}")
            if "role_id" not in level:
                raise ValidationError(f"Level {i} missing required field: role_id")
            try:
                UUID(str(level["role_id"]))
            except ValueError:
                raise ValidationError(f"Level {i} has invalid role_id: {level['role_id']}")
        
        # Convert UUIDs to strings for JSONB storage
        levels_serializable = []
        for level in levels:
            level_copy = level.copy()
            if "role_id" in level_copy:
                level_copy["role_id"] = str(level_copy["role_id"])
            levels_serializable.append(level_copy)
        
        # Deactivate existing active chains (forward-only versioning)
        await self.db.execute(
            select(DiscrepancyApprovalChainConfig).where(
                DiscrepancyApprovalChainConfig.is_active == True
            )
        )
        active_chains = await self.db.execute(
            select(DiscrepancyApprovalChainConfig).where(
                DiscrepancyApprovalChainConfig.is_active == True
            )
        )
        for chain in active_chains.scalars().all():
            chain.is_active = False
        
        # Create new active chain
        chain = DiscrepancyApprovalChainConfig(
            levels=levels_serializable,
            is_active=True,
            created_by=created_by,
        )
        self.db.add(chain)
        await self.db.commit()
        await self.db.refresh(chain)
        
        # Don't auto-update workflow definition to avoid affecting in-flight discrepancies
        # Workflow definition will be updated when needed by DiscrepancyService
        
        return chain

    async def get_active_approval_chain(self) -> Optional[DiscrepancyApprovalChainConfig]:
        """Get the currently active approval chain configuration."""
        result = await self.db.execute(
            select(DiscrepancyApprovalChainConfig).where(
                DiscrepancyApprovalChainConfig.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def get_approval_chain(self, chain_version_id: UUID) -> Optional[DiscrepancyApprovalChainConfig]:
        """Get a specific approval chain version by ID."""
        return await self.db.get(DiscrepancyApprovalChainConfig, chain_version_id)

    async def list_approval_chains(self, active_only: bool = False) -> List[DiscrepancyApprovalChainConfig]:
        """List all approval chain versions."""
        query = select(DiscrepancyApprovalChainConfig)
        if active_only:
            query = query.where(DiscrepancyApprovalChainConfig.is_active == True)
        query = query.order_by(DiscrepancyApprovalChainConfig.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _update_workflow_definition(self, chain: DiscrepancyApprovalChainConfig) -> None:
        """
        Update the workflow engine with the new approval chain configuration.
        This integrates with the WorkflowEngine for N-level approval sub-stages.
        """
        # Convert levels to ApprovalLevel objects
        approval_levels = [
            ApprovalLevel(
                level=level["level"],
                role_id=UUID(str(level["role_id"])),
                auto_escalation_sla_hours=level.get("auto_escalation_sla_hours"),
            )
            for level in chain.levels
        ]
        
        # Create approval chain config for workflow engine
        approval_chain_config = ApprovalChainConfig(
            chain_version_id=chain.chain_version_id,
            levels=approval_levels,
        )
        
        # Build N-level approval transitions using WorkflowEngine helper
        num_levels = len(approval_levels)
        transitions = self.workflow_engine.build_approval_transitions(
            base_state="open",
            num_levels=num_levels,
            approved_state="approved",
            rejected_state="rejected",
        )
        
        # Register the workflow definition for discrepancy entity type
        workflow_def = WorkflowDefinitionData(
            entity_type="discrepancy",
            initial_state="open",
            transitions=transitions,
            approval_chain=approval_chain_config,
        )
        
        await self.workflow_engine.register_definition(workflow_def)

    async def get_current_approval_levels(self) -> List[ApprovalLevel]:
        """
        Get the current approval levels from the active chain.
        Uses WorkflowEngine to retrieve the levels.
        """
        try:
            return await self.workflow_engine.get_approval_levels("discrepancy")
        except Exception:
            # If no workflow definition exists, return empty list
            return []

    async def activate_chain_version(self, chain_version_id: UUID) -> DiscrepancyApprovalChainConfig:
        """
        Activate a specific chain version (forward-only).
        Deactivates the currently active chain.
        
        Args:
            chain_version_id: The chain version to activate
            
        Returns:
            The activated chain
            
        Raises:
            ValidationError: If chain version not found
        """
        chain = await self.db.get(DiscrepancyApprovalChainConfig, chain_version_id)
        if not chain:
            raise ValidationError(f"Approval chain version not found: {chain_version_id}")
        
        # Deactivate currently active chain
        active_chains = await self.db.execute(
            select(DiscrepancyApprovalChainConfig).where(
                DiscrepancyApprovalChainConfig.is_active == True
            )
        )
        for active_chain in active_chains.scalars().all():
            active_chain.is_active = False
        
        # Activate the requested chain
        chain.is_active = True
        await self.db.commit()
        await self.db.refresh(chain)
        
        # Don't auto-update workflow definition to avoid affecting in-flight discrepancies
        # Workflow definition will be updated when needed by DiscrepancyService
        
        return chain
