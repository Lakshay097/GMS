"""
Approval Chain Service for Audit Discrepancy module.
v2.0: Named chains with scope filtering, priority-based matching, and person assignment.

Multiple chains can be active simultaneously. When a discrepancy enters
approval, the system selects the best matching chain by:
  1. Filter: only active chains
  2. Filter: category match (if chain specifies a category)
  3. Filter: school match (if chain specifies a school)
  4. Filter: department match (if chain specifies a department)
  5. Sort by priority (highest first)
  6. First match wins

Each level can assign either a role (e.g., 'admin') or a specific user (by user_id).
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.platform_models import DiscrepancyApprovalChainConfig, Discrepancy
from shared.errors import ValidationError, NotFoundError
from platform_services.workflow_engine.service import (
    WorkflowEngine,
    ApprovalLevel,
    ApprovalChainConfig,
    TransitionDefinition,
    WorkflowDefinitionData,
)


class ApprovalChainService:
    """
    v2.0 approval chain configuration service.
    Supports named chains, scope filtering, priority-based matching,
    and per-level person assignment.
    """

    def __init__(self, db: AsyncSession, workflow_engine: WorkflowEngine):
        self.db = db
        self.workflow_engine = workflow_engine

    # ── Create ──────────────────────────────────────────────────────────

    async def create_approval_chain(
        self,
        levels: List[dict],
        name: str = "Default Chain",
        description: Optional[str] = None,
        priority: int = 0,
        school_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
    ) -> DiscrepancyApprovalChainConfig:
        """
        Create a new approval chain.

        Args:
            levels: List of level dicts. Each level must have:
                - level (int): 1-based level number
                - role_id (str): Role name (e.g., 'admin') OR
                - user_id (str): Specific user UUID
                - auto_escalation_sla_hours (int, optional): SLA in hours
            name: Human-readable chain name
            description: Optional description of when to use this chain
            priority: Higher = checked first when multiple active chains match
            school_id: Scope to specific school (null = all schools)
            department_id: Scope to specific department (null = all departments)
            category_id: Scope to specific discrepancy category (null = all categories)
            created_by: User ID creating the chain

        Returns:
            Created DiscrepancyApprovalChainConfig entity
        """
        # Validate levels structure
        if not levels:
            raise ValidationError("Approval chain must have at least one level")

        self._validate_levels(levels)

        # Normalize levels for storage
        levels_serializable = self._normalize_levels(levels)

        # Create the chain (no longer deactivates others — multiple active allowed)
        chain = DiscrepancyApprovalChainConfig(
            name=name.strip(),
            description=description.strip() if description else None,
            levels=levels_serializable,
            is_active=True,
            priority=priority,
            school_id=school_id,
            department_id=department_id,
            category_id=category_id,
            created_by=created_by,
        )
        self.db.add(chain)
        await self.db.commit()
        await self.db.refresh(chain)

        return chain

    # ── Read ────────────────────────────────────────────────────────────

    async def get_approval_chain(self, chain_version_id: UUID) -> Optional[DiscrepancyApprovalChainConfig]:
        """Get a specific approval chain by ID."""
        return await self.db.get(DiscrepancyApprovalChainConfig, chain_version_id)

    async def list_approval_chains(self, active_only: bool = False) -> List[DiscrepancyApprovalChainConfig]:
        """List all approval chains, ordered by priority descending then created_at."""
        query = select(DiscrepancyApprovalChainConfig)
        if active_only:
            query = query.where(DiscrepancyApprovalChainConfig.is_active == True)
        query = query.order_by(
            DiscrepancyApprovalChainConfig.priority.desc(),
            DiscrepancyApprovalChainConfig.created_at.desc(),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_approval_chain(self) -> Optional[DiscrepancyApprovalChainConfig]:
        """
        Get the highest-priority active approval chain.
        For backward compatibility — prefer resolve_chain_for_discrepancy() for new code.
        """
        result = await self.db.execute(
            select(DiscrepancyApprovalChainConfig)
            .where(DiscrepancyApprovalChainConfig.is_active == True)
            .order_by(DiscrepancyApprovalChainConfig.priority.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── Chain Matching (priority-based) ─────────────────────────────────

    async def resolve_chain_for_discrepancy(
        self,
        school_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
    ) -> Optional[DiscrepancyApprovalChainConfig]:
        """
        Find the best matching active chain for a discrepancy.

        Matching logic (priority order):
        1. Must be active
        2. If chain has category_id → discrepancy must match
        3. If chain has school_id → discrepancy must match
        4. If chain has department_id → discrepancy must match
        5. Sort by priority (highest first)
        6. First match wins

        A chain with no scope filters (all null) is a "catch-all" and matches everything.
        More specific chains (with filters) should have higher priority.
        """
        result = await self.db.execute(
            select(DiscrepancyApprovalChainConfig)
            .where(DiscrepancyApprovalChainConfig.is_active == True)
            .order_by(DiscrepancyApprovalChainConfig.priority.desc())
        )
        active_chains = result.scalars().all()

        for chain in active_chains:
            if self._chain_matches(chain, school_id, department_id, category_id):
                return chain

        return None

    def _chain_matches(
        self,
        chain: DiscrepancyApprovalChainConfig,
        school_id: Optional[UUID],
        department_id: Optional[UUID],
        category_id: Optional[UUID],
    ) -> bool:
        """Check if a chain's scope filters match the given discrepancy context."""
        # If chain specifies a category, discrepancy must match
        if chain.category_id and category_id != chain.category_id:
            return False

        # If chain specifies a school, discrepancy must match
        if chain.school_id and school_id != chain.school_id:
            return False

        # If chain specifies a department, discrepancy must match
        if chain.department_id and department_id != chain.department_id:
            return False

        return True

    # ── Activate / Deactivate ──────────────────────────────────────────

    async def activate_chain(self, chain_version_id: UUID) -> DiscrepancyApprovalChainConfig:
        """
        Activate a chain. Multiple chains can be active simultaneously.
        """
        chain = await self.db.get(DiscrepancyApprovalChainConfig, chain_version_id)
        if not chain:
            raise NotFoundError(f"Approval chain not found: {chain_version_id}")

        chain.is_active = True
        await self.db.commit()
        await self.db.refresh(chain)
        return chain

    async def deactivate_chain(self, chain_version_id: UUID) -> DiscrepancyApprovalChainConfig:
        """
        Deactivate a chain.
        """
        chain = await self.db.get(DiscrepancyApprovalChainConfig, chain_version_id)
        if not chain:
            raise NotFoundError(f"Approval chain not found: {chain_version_id}")

        chain.is_active = False
        await self.db.commit()
        await self.db.refresh(chain)
        return chain

    # ── Update ──────────────────────────────────────────────────────────

    async def update_approval_chain(
        self,
        chain_version_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        levels: Optional[List[dict]] = None,
        priority: Optional[int] = None,
        school_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
    ) -> DiscrepancyApprovalChainConfig:
        """
        Update an existing approval chain.
        Only modifies fields that are explicitly provided.
        """
        chain = await self.db.get(DiscrepancyApprovalChainConfig, chain_version_id)
        if not chain:
            raise NotFoundError(f"Approval chain not found: {chain_version_id}")

        if name is not None:
            chain.name = name.strip()
        if description is not None:
            chain.description = description.strip() if description else None
        if levels is not None:
            self._validate_levels(levels)
            chain.levels = self._normalize_levels(levels)
        if priority is not None:
            chain.priority = priority
        if school_id is not None:
            chain.school_id = school_id
        if department_id is not None:
            chain.department_id = department_id
        if category_id is not None:
            chain.category_id = category_id

        await self.db.commit()
        await self.db.refresh(chain)
        return chain

    # ── Delete ──────────────────────────────────────────────────────────

    async def delete_chain(self, chain_version_id: UUID) -> None:
        """
        Delete an approval chain.
        Cannot delete if it's bound to in-flight discrepancies.
        """
        chain = await self.db.get(DiscrepancyApprovalChainConfig, chain_version_id)
        if not chain:
            raise NotFoundError(f"Approval chain not found: {chain_version_id}")

        # Check for in-flight discrepancies bound to this chain
        result = await self.db.execute(
            select(Discrepancy).where(
                Discrepancy.bound_chain_version_id == chain_version_id,
                Discrepancy.state.notin_(["raised", "closed"]),
            )
        )
        in_flight = result.scalars().first()
        if in_flight:
            raise ValidationError(
                f"Cannot delete chain '{chain.name}' — it is bound to "
                f"discrepancy {in_flight.id} which is still in progress."
            )

        await self.db.delete(chain)
        await self.db.commit()

    # ── Helpers ─────────────────────────────────────────────────────────

    def _validate_levels(self, levels: List[dict]) -> None:
        """Validate level structure. Each level needs role_id OR user_id."""
        from shared.models import UserRole
        valid_roles = {r.value for r in UserRole}

        for i, level in enumerate(levels, 1):
            if level.get("level") != i:
                raise ValidationError(f"Level {i} has incorrect level number: {level.get('level')}")

            has_role = "role_id" in level and level["role_id"]
            has_user = "user_id" in level and level["user_id"]

            if not has_role and not has_user:
                raise ValidationError(
                    f"Level {i} must have either 'role_id' (role name) or 'user_id' (specific person)"
                )

            if has_role:
                role_name = str(level["role_id"]).lower().strip()
                if role_name not in valid_roles:
                    raise ValidationError(
                        f"Level {i} has invalid role: '{level['role_id']}'. Valid roles: {sorted(valid_roles)}"
                    )

            if has_user:
                try:
                    UUID(str(level["user_id"]))
                except ValueError:
                    raise ValidationError(f"Level {i} has invalid user_id: {level['user_id']}")

    def _normalize_levels(self, levels: List[dict]) -> List[dict]:
        """Normalize level data for consistent JSONB storage."""
        normalized = []
        for level in levels:
            level_copy = level.copy()
            if "role_id" in level_copy and level_copy["role_id"]:
                level_copy["role_id"] = str(level_copy["role_id"]).lower().strip()
            if "user_id" in level_copy and level_copy["user_id"]:
                level_copy["user_id"] = str(level_copy["user_id"])
            # Ensure assignee_type is set
            if "role_id" in level_copy and level_copy.get("role_id"):
                level_copy["assignee_type"] = "role"
            elif "user_id" in level_copy and level_copy.get("user_id"):
                level_copy["assignee_type"] = "user"
            normalized.append(level_copy)
        return normalized

    async def _update_workflow_definition(self, chain: DiscrepancyApprovalChainConfig) -> None:
        """
        Update the workflow engine with the approval chain configuration.
        """
        approval_levels = [
            ApprovalLevel(
                level=level["level"],
                role_id=str(level.get("role_id", "")),
                auto_escalation_sla_hours=level.get("auto_escalation_sla_hours"),
            )
            for level in chain.levels
        ]

        approval_chain_config = ApprovalChainConfig(
            chain_version_id=chain.chain_version_id,
            levels=approval_levels,
        )

        num_levels = len(approval_levels)
        transitions = self.workflow_engine.build_approval_transitions(
            base_state="open",
            num_levels=num_levels,
            approved_state="approved",
            rejected_state="rejected",
        )

        workflow_def = WorkflowDefinitionData(
            entity_type="discrepancy",
            initial_state="open",
            transitions=transitions,
            approval_chain=approval_chain_config,
        )

        await self.workflow_engine.register_definition(workflow_def)
