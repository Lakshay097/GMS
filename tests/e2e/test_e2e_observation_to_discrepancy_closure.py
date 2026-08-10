"""
End-to-end test for Observation to Discrepancy Closure workflow.
Tests the complete lifecycle from observation capture through discrepancy creation,
investigation, approval, and final closure with audit trail verification.
"""
import uuid
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from modules.observation_capture.services.observation_service import ObservationService
from modules.audit_discrepancy.services.discrepancy_service import DiscrepancyService
from modules.audit_discrepancy.services.approval_chain_service import ApprovalChainService
from platform_services.workflow_engine.service import WorkflowEngine
from platform_services.audit_log_service.service import AuditLogService
from shared.platform_models import (
    Observation,
    Discrepancy,
    DiscrepancyCategory,
    DiscrepancyApprovalHistory,
    AutoResult,
    RagStatus,
    KPI,
    KRA,
)
from shared.datetime_utils import utc_now
from shared.models import User


# Stub notification service for testing
class StubNotificationService:
    def __init__(self):
        self.dispatched: list[dict] = []
        self._notifications: list[dict] = []

    async def dispatch(self, payload) -> uuid.UUID:
        self.dispatched.append({
            "user_id": payload.user_id,
            "category": payload.category,
            "title": payload.title
        })
        self._notifications.append(payload)
        return uuid.uuid4()
    
    def get_pending_notifications(self):
        return self._notifications


@pytest.mark.asyncio
async def test_e2e_observation_to_discrepancy_closure(db, school, department, seed_configuration):
    """
    End-to-end test: Observation submission triggers discrepancy detection,
    investigation, multi-level approval, and final closure.
    
    Workflow states:
    1. Observation submitted with NOT_MET auto-result
    2. Discrepancy raised from observation
    3. Investigation assigned and findings submitted
    4. Multi-level approval chain executed
    5. Discrepancy closed with audit trail
    6. Notifications dispatched at each transition
    """
    # Setup: Create users for different roles
    checker = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="checker@test.com",
        full_name="Checker User",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["checker"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    
    investigator = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="investigator@test.com",
        full_name="Investigator User",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["supervisor"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    
    approver_l1 = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="approver_l1@test.com",
        full_name="Approver L1",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["admin"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    
    approver_l2 = User(
        id=uuid.uuid4(),
        neon_auth_user_id=f"neon-{uuid.uuid4()}",
        email="approver_l2@test.com",
        full_name="Approver L2",
        school_id=school.id,
        department_id=department.id,
        status="active",
        roles=["super_admin"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    
    db.add_all([checker, investigator, approver_l1, approver_l2])
    await db.commit()
    
    # Setup: Create KPI with threshold that will trigger NOT_MET
    kra = KRA(id=uuid.uuid4(), name="Compliance KRA", created_at=utc_now())
    db.add(kra)
    await db.flush()
    
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=kra.id,
        title="Daily Compliance Score",
        target_value=100,
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        created_at=utc_now(),
    )
    db.add(kpi)
    await db.commit()
    
    # Setup: Create discrepancy category
    category = DiscrepancyCategory(
        id=uuid.uuid4(),
        name="Compliance Gap",
        status="active",
    )
    db.add(category)
    await db.commit()
    
    # Setup: Initialize services
    notification_service = StubNotificationService()
    audit_log_service = AuditLogService(db)
    workflow_engine = WorkflowEngine(db)
    observation_service = ObservationService(db, notification_service=notification_service)
    discrepancy_service = DiscrepancyService(db, workflow_engine, notification_service=notification_service)
    approval_chain_service = ApprovalChainService(db, workflow_engine)
    
    # STEP 1: Submit observation with value below threshold (should trigger NOT_MET)
    observation = await observation_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=kpi.version,
        checker_id=checker.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("75.5"),  # Below target of 100
    )
    
    # Assert observation state
    assert observation.id is not None
    assert observation.auto_result == AutoResult.NOT_MET
    assert observation.rag_status == RagStatus.RED
    assert observation.checker_id == checker.id
    
    # STEP 2: Raise discrepancy from observation
    discrepancy = await discrepancy_service.raise_discrepancy(
        observation_id=observation.id,
        category_id=category.id,
        school_id=school.id,
        department_id=department.id,
        raised_by_user_id=checker.id,
    )
    
    # Assert discrepancy initial state
    assert discrepancy.state == "raised"
    assert discrepancy.observation_id == observation.id
    assert discrepancy.category_id == category.id
    assert discrepancy.raised_by_user_id == checker.id
    
    # Verify audit log entry for discrepancy creation
    audit_entries = await audit_log_service.get_entity_history(
        entity_type="discrepancy",
        entity_id=discrepancy.id
    )
    assert len(audit_entries) == 1
    assert audit_entries[0].event_type == "discrepancy_raised"
    
    # STEP 3: Assign investigation
    discrepancy = await discrepancy_service.assign_investigation(
        discrepancy_id=discrepancy.id,
        investigation_owner_id=investigator.id,
    )
    
    # Assert investigation assignment
    assert discrepancy.state == "under_investigation"
    assert discrepancy.investigation_owner_id == investigator.id
    assert discrepancy.investigation_assigned_at is not None
    
    # Verify notification dispatched to investigator
    notifications = notification_service.get_pending_notifications()
    investigator_notif = [n for n in notifications if n.user_id == investigator.id]
    assert len(investigator_notif) > 0
    
    # STEP 4: Submit investigation findings
    discrepancy = await discrepancy_service.submit_investigation_findings(
        discrepancy_id=discrepancy.id,
        investigation_findings="Root cause identified: Process gap in training. Corrective action: Schedule refresher training for all staff.",
    )
    
    # Assert findings submission
    assert discrepancy.state == "findings_submitted"
    assert discrepancy.investigation_findings is not None
    assert "Root cause identified" in discrepancy.investigation_findings
    
    # STEP 5: Start approval process
    discrepancy = await discrepancy_service.start_approval(discrepancy_id=discrepancy.id)
    
    # Assert approval started
    assert discrepancy.state == "pending_approval_level_1"
    
    # STEP 6: Level 1 approval
    discrepancy = await discrepancy_service.approve_discrepancy(
        discrepancy_id=discrepancy.id,
        level=1,
        approver_id=approver_l1.id,
        comments="Findings validated. Recommended corrective actions approved.",
    )
    
    # Assert level 1 approval
    assert discrepancy.state == "pending_approval_level_2"
    assert discrepancy.current_approval_level == 2
    
    # Verify approval history entry
    approval_history = await db.execute(
        select(DiscrepancyApprovalHistory).where(
            DiscrepancyApprovalHistory.discrepancy_id == discrepancy.id,
            DiscrepancyApprovalHistory.approval_level == 1
        )
    )
    l1_approval = approval_history.scalars().first()
    assert l1_approval is not None
    assert l1_approval.approver_id == approver_l1.id
    assert l1_approval.approval_status == "approved"
    
    # STEP 7: Level 2 approval
    discrepancy = await discrepancy_service.approve_discrepancy(
        discrepancy_id=discrepancy.id,
        level=2,
        approver_id=approver_l2.id,
        comments="Final approval granted. Discrepancy closure authorized.",
    )
    
    # Assert level 2 approval and closure
    assert discrepancy.state == "closed"
    assert discrepancy.closed_at is not None
    assert discrepancy.closed_by_user_id == approver_l2.id
    
    # Verify final approval history
    approval_history = await db.execute(
        select(DiscrepancyApprovalHistory).where(
            DiscrepancyApprovalHistory.discrepancy_id == discrepancy.id,
            DiscrepancyApprovalHistory.approval_level == 2
        )
    )
    l2_approval = approval_history.scalars().first()
    assert l2_approval is not None
    assert l2_approval.approver_id == approver_l2.id
    assert l2_approval.approval_status == "approved"
    
    # STEP 8: Verify complete audit trail
    complete_audit = await audit_log_service.get_entity_history(
        entity_type="discrepancy",
        entity_id=discrepancy.id
    )
    
    expected_events = [
        "discrepancy_raised",
        "investigation_assigned",
        "findings_submitted",
        "approval_started",
        "level_1_approved",
        "level_2_approved",
        "discrepancy_closed"
    ]
    
    actual_events = [entry.event_type for entry in complete_audit]
    for expected_event in expected_events:
        assert expected_event in actual_events, f"Expected audit event {expected_event} not found"
    
    # STEP 9: Verify notification chain
    all_notifications = notification_service.get_pending_notifications()
    
    # Verify checker received notification on discrepancy creation
    checker_notifs = [n for n in all_notifications if n.user_id == checker.id]
    assert len(checker_notifs) > 0
    
    # Verify approvers received notifications
    approver_notifs = [n for n in all_notifications if n.user_id in [approver_l1.id, approver_l2.id]]
    assert len(approver_notifs) > 0
    
    # STEP 10: Verify final state persistence
    final_discrepancy = await db.get(Discrepancy, discrepancy.id)
    assert final_discrepancy.state == "closed"
    assert final_discrepancy.investigation_findings is not None
    assert final_discrepancy.closed_at is not None
    
    # Verify observation is still accessible and linked
    final_observation = await db.get(Observation, observation.id)
    assert final_observation.id == observation.id
    assert final_observation.auto_result == AutoResult.NOT_MET