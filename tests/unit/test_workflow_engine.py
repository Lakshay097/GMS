"""Unit tests for Workflow Engine — Architecture §5.3, ADR-03."""
import uuid

import pytest

from platform_services.workflow_engine.service import (
    ApprovalChainConfig,
    ApprovalLevel,
    TransitionDefinition,
    WorkflowDefinitionData,
    WorkflowEngine,
    WorkflowError,
)


@pytest.mark.asyncio
async def test_workflow_engine_data_defined_transitions(db):
    engine = WorkflowEngine(db)
    definition = WorkflowDefinitionData(
        entity_type="test_entity",
        initial_state="draft",
        transitions=[
            TransitionDefinition(from_state="draft", to_state="submitted"),
            TransitionDefinition(from_state="submitted", to_state="approved", guard="approved"),
        ],
    )
    await engine.register_definition(definition)

    engine.register_guard("approved", lambda ctx: ctx.get("approved") is True)

    result = await engine.transition("test_entity", "draft", "submitted")
    assert result.to_state == "submitted"

    with pytest.raises(WorkflowError):
        await engine.transition("test_entity", "submitted", "approved", {"approved": False})

    result = await engine.transition("test_entity", "submitted", "approved", {"approved": True})
    assert result.to_state == "approved"


@pytest.mark.asyncio
async def test_workflow_engine_n_level_approval_substage(db):
    """Parameterized N-level approval — BR-21 / ADR-09."""
    engine = WorkflowEngine(db)
    role_1 = uuid.uuid4()
    role_2 = uuid.uuid4()

    approval_chain = ApprovalChainConfig(
        chain_version_id=uuid.uuid4(),
        levels=[
            ApprovalLevel(level=1, role_id=role_1),
            ApprovalLevel(level=2, role_id=role_2),
        ],
    )
    transitions = engine.build_approval_transitions(
        base_state="investigation_complete",
        num_levels=2,
        approved_state="approved",
        rejected_state="rejected",
    )
    definition = WorkflowDefinitionData(
        entity_type="discrepancy",
        initial_state="open",
        transitions=transitions,
        approval_chain=approval_chain,
    )
    await engine.register_definition(definition)

    levels = await engine.get_approval_levels("discrepancy")
    assert len(levels) == 2
    assert levels[0].role_id == role_1
    assert levels[1].role_id == role_2

    engine.register_guard("approved", lambda ctx: True)
    engine.register_guard("rejected", lambda ctx: False)
    engine.register_guard("no_skip", lambda ctx: True)

    result = await engine.transition(
        "discrepancy", "investigation_complete", "pending_approval_level_1"
    )
    assert result.approval_level == 1
