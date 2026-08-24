"""
Generic data-defined Workflow Engine — Architecture §5.3, ADR-03.
Supports parameterized N-level approval sub-stages (BR-21 / ADR-09).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.platform_models import WorkflowDefinition


class WorkflowError(Exception):
    """Workflow transition validation failure."""


@dataclass
class ApprovalLevel:
    """Single level in an N-level approval chain."""

    level: int
    role_id: str  # Role name string (e.g., 'admin', 'checker')
    auto_escalation_sla_hours: Optional[int] = None


@dataclass
class ApprovalChainConfig:
    """Parameterized approval sub-stage configuration."""

    chain_version_id: UUID
    levels: list[ApprovalLevel] = field(default_factory=list)


@dataclass
class TransitionDefinition:
    from_state: str
    to_state: str
    guard: Optional[str] = None


@dataclass
class WorkflowDefinitionData:
    entity_type: str
    initial_state: str
    transitions: list[TransitionDefinition]
    approval_chain: Optional[ApprovalChainConfig] = None


@dataclass
class TransitionResult:
    entity_type: str
    from_state: str
    to_state: str
    approval_level: Optional[int] = None


GuardFunc = Callable[[dict[str, Any]], bool]


class WorkflowEngine:
    """
    Data-defined state machine engine.
    State machines are registered as configuration, not hardcoded per module.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._guards: dict[str, GuardFunc] = {}
        self._definitions: dict[str, WorkflowDefinitionData] = {}

    def register_guard(self, name: str, guard: GuardFunc) -> None:
        self._guards[name] = guard

    async def register_definition(self, definition: WorkflowDefinitionData) -> None:
        """Persist and cache a state machine definition."""
        self._definitions[definition.entity_type] = definition

        transitions_json = [
            {"from_state": t.from_state, "to_state": t.to_state, "guard": t.guard}
            for t in definition.transitions
        ]
        approval_json = None
        if definition.approval_chain:
            approval_json = {
                "chain_version_id": str(definition.approval_chain.chain_version_id),
                "levels": [
                    {
                        "level": lvl.level,
                        "role_id": str(lvl.role_id),
                        "auto_escalation_sla_hours": lvl.auto_escalation_sla_hours,
                    }
                    for lvl in definition.approval_chain.levels
                ],
            }

        result = await self.db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.entity_type == definition.entity_type
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.initial_state = definition.initial_state
            existing.transitions = transitions_json
            existing.approval_chain_config = approval_json
        else:
            self.db.add(
                WorkflowDefinition(
                    entity_type=definition.entity_type,
                    initial_state=definition.initial_state,
                    transitions=transitions_json,
                    approval_chain_config=approval_json,
                )
            )
        await self.db.commit()

    async def load_definition(self, entity_type: str) -> WorkflowDefinitionData:
        if entity_type in self._definitions:
            return self._definitions[entity_type]

        result = await self.db.execute(
            select(WorkflowDefinition).where(WorkflowDefinition.entity_type == entity_type)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise WorkflowError(f"No workflow definition for entity type: {entity_type}")

        transitions = [
            TransitionDefinition(
                from_state=t["from_state"],
                to_state=t["to_state"],
                guard=t.get("guard"),
            )
            for t in (row.transitions or [])
        ]
        approval_chain = None
        if row.approval_chain_config:
            cfg = row.approval_chain_config
            approval_chain = ApprovalChainConfig(
                chain_version_id=UUID(cfg["chain_version_id"]),
                levels=[
                    ApprovalLevel(
                        level=lvl["level"],
                        role_id=UUID(lvl["role_id"]),
                        auto_escalation_sla_hours=lvl.get("auto_escalation_sla_hours"),
                    )
                    for lvl in cfg.get("levels", [])
                ],
            )

        definition = WorkflowDefinitionData(
            entity_type=row.entity_type,
            initial_state=row.initial_state,
            transitions=transitions,
            approval_chain=approval_chain,
        )
        self._definitions[entity_type] = definition
        return definition

    async def transition(
        self,
        entity_type: str,
        current_state: str,
        target_state: str,
        context: Optional[dict[str, Any]] = None,
    ) -> TransitionResult:
        """Validate and execute a state transition."""
        definition = await self.load_definition(entity_type)
        context = context or {}

        valid = any(
            t.from_state == current_state and t.to_state == target_state
            for t in definition.transitions
        )
        if not valid:
            raise WorkflowError(
                f"Invalid transition {current_state} → {target_state} for {entity_type}"
            )

        transition = next(
            t
            for t in definition.transitions
            if t.from_state == current_state and t.to_state == target_state
        )
        if transition.guard:
            guard_fn = self._guards.get(transition.guard)
            if guard_fn is None:
                raise WorkflowError(f"Unknown guard: {transition.guard}")
            if not guard_fn(context):
                raise WorkflowError(f"Guard '{transition.guard}' rejected transition")

        approval_level = None
        if target_state.startswith("pending_approval_level_"):
            approval_level = int(target_state.rsplit("_", 1)[-1])

        return TransitionResult(
            entity_type=entity_type,
            from_state=current_state,
            to_state=target_state,
            approval_level=approval_level,
        )

    async def get_approval_levels(self, entity_type: str) -> list[ApprovalLevel]:
        """Return N-level approval chain from configuration (not hardcoded)."""
        definition = await self.load_definition(entity_type)
        if definition.approval_chain is None:
            return []
        return definition.approval_chain.levels

    async def get_initial_state(self, entity_type: str) -> str:
        definition = await self.load_definition(entity_type)
        return definition.initial_state

    def build_approval_transitions(
        self,
        base_state: str,
        num_levels: int,
        approved_state: str,
        rejected_state: str,
    ) -> list[TransitionDefinition]:
        """
        Build parameterized N-level approval sub-stage transitions.
        Used by Discrepancy module (BR-21) without a separate approval mechanism.
        """
        transitions: list[TransitionDefinition] = []
        for level in range(1, num_levels + 1):
            pending = f"pending_approval_level_{level}"
            if level == 1:
                transitions.append(
                    TransitionDefinition(from_state=base_state, to_state=pending)
                )
            else:
                prev = f"pending_approval_level_{level - 1}"
                transitions.append(
                    TransitionDefinition(from_state=prev, to_state=pending, guard="no_skip")
                )
            transitions.append(
                TransitionDefinition(
                    from_state=pending,
                    to_state=approved_state if level == num_levels else f"pending_approval_level_{level + 1}",
                    guard="approved",
                )
            )
            transitions.append(
                TransitionDefinition(from_state=pending, to_state=rejected_state, guard="rejected")
            )
        return transitions
