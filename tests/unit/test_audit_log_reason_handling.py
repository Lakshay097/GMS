"""
Test to verify audit log reason handling for reject and reopen-approval actions.
This test shows actual audit log entries produced.
"""
import pytest
from uuid import uuid4, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from modules.observation_capture.services.observation_service import ObservationService
from platform_services.audit_log_service.service import AuditLogService
from shared.platform_models import KPI, Observation, AutoResult, RagStatus
from shared.datetime_utils import utc_now


@pytest.mark.asyncio
async def test_audit_log_includes_rejection_reason(db: AsyncSession):
    """
    Test that rejection reason is included in audit log new_values JSONB.
    Shows actual audit log entry produced.
    """
    # Create a test KPI
    kpi_id = uuid4()
    kpi = KPI(
        kpi_id=kpi_id,
        version=1,
        kra_id=uuid4(),
        title="Test KPI",
        target_value=Decimal("95.0"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        capture_type="value_reading",
        status="active",
    )
    db.add(kpi)
    await db.commit()
    
    # Create a test observation
    observation_id = uuid4()
    checker_id = uuid4()
    school_id = uuid4()
    department_id = uuid4()
    
    observation = Observation(
        id=observation_id,
        kpi_id=kpi_id,
        kpi_version=1,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("90.0"),
        auto_result=AutoResult.NOT_MET,
        rag_status=RagStatus.RED,
        submitted_at=utc_now(),
        is_late=False,
        submission_token=uuid4(),
        status='pending',
    )
    db.add(observation)
    await db.commit()
    
    # Simulate rejection with reason
    actor_id = uuid4()
    rejection_reason = "Data quality issue - values inconsistent with source"
    
    audit_log = AuditLogService(db)
    await audit_log.log_observation_update(
        observation_id=observation_id,
        actor_id=actor_id,
        old_values={"status": "pending"},
        new_values={
            "status": "rejected",
            "rejected_by": str(actor_id),
            "rejection_reason": rejection_reason
        },
    )
    await db.commit()
    
    # Retrieve and show the actual audit log entry
    audit_entries = await audit_log.get_entity_history("observation", observation_id)
    
    assert len(audit_entries) == 1
    entry = audit_entries[0]
    
    print("\n=== ACTUAL AUDIT LOG ENTRY FOR REJECTION ===")
    print(f"Action: {entry.action}")
    print(f"Entity Type: {entry.entity_type}")
    print(f"Entity ID: {entry.entity_id}")
    print(f"Actor ID: {entry.user_id}")
    print(f"Old Values: {entry.old_values}")
    print(f"New Values: {entry.new_values}")
    print(f"Timestamp: {entry.timestamp}")
    print("=== END AUDIT LOG ENTRY ===\n")
    
    # Verify reason is in new_values
    assert entry.new_values is not None
    assert "rejection_reason" in entry.new_values
    assert entry.new_values["rejection_reason"] == rejection_reason
    assert entry.new_values["status"] == "rejected"


@pytest.mark.asyncio
async def test_audit_log_includes_reopen_approval_reason(db: AsyncSession):
    """
    Test that reopen approval reason (admin_comment) is included in audit log.
    Shows actual audit log entry produced for both approve and deny.
    """
    # Create a test observation with reopen request
    observation_id = uuid4()
    checker_id = uuid4()
    school_id = uuid4()
    department_id = uuid4()
    
    observation = Observation(
        id=observation_id,
        kpi_id=uuid4(),
        kpi_version=1,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("90.0"),
        auto_result=AutoResult.NOT_MET,
        rag_status=RagStatus.RED,
        submitted_at=utc_now(),
        is_late=False,
        submission_token=uuid4(),
        status='pending',
        reopen_requested_at=utc_now(),
        reopen_requested_by=uuid4(),
        reopen_reason="Need to resubmit corrected data",
    )
    db.add(observation)
    await db.commit()
    
    # Test APPROVE with reason
    actor_id = uuid4()
    approve_reason = "Valid request - data source confirmed"
    
    audit_log = AuditLogService(db)
    await audit_log.log_reopen_approval(
        observation_id=observation_id,
        actor_id=actor_id,
        approved=True,
        reason=approve_reason,
    )
    await db.commit()
    
    # Retrieve and show the actual audit log entry for approval
    audit_entries = await audit_log.get_entity_history("observation", observation_id)
    
    assert len(audit_entries) == 1
    entry = audit_entries[0]
    
    print("\n=== ACTUAL AUDIT LOG ENTRY FOR REOPEN APPROVAL ===")
    print(f"Action: {entry.action}")
    print(f"Entity Type: {entry.entity_type}")
    print(f"Entity ID: {entry.entity_id}")
    print(f"Actor ID: {entry.user_id}")
    print(f"Old Values: {entry.old_values}")
    print(f"New Values: {entry.new_values}")
    print(f"Timestamp: {entry.timestamp}")
    print("=== END AUDIT LOG ENTRY ===\n")
    
    # Verify reason is in new_values via reason_comment
    assert entry.new_values is not None
    assert "reason_comment" in entry.new_values
    assert entry.new_values["reason_comment"] == approve_reason
    assert entry.action == "reopen_approved"
    
    # Test DENY with reason
    deny_reason = "Request not justified - observation was correctly rejected"
    
    await audit_log.log_reopen_approval(
        observation_id=observation_id,
        actor_id=actor_id,
        approved=False,
        reason=deny_reason,
    )
    await db.commit()
    
    # Retrieve the denial audit log entry
    audit_entries = await audit_log.get_entity_history("observation", observation_id)
    
    assert len(audit_entries) == 2
    denial_entry = audit_entries[1]  # Second entry is the denial
    
    print("\n=== ACTUAL AUDIT LOG ENTRY FOR REOPEN DENIAL ===")
    print(f"Action: {denial_entry.action}")
    print(f"Entity Type: {denial_entry.entity_type}")
    print(f"Entity ID: {denial_entry.entity_id}")
    print(f"Actor ID: {denial_entry.user_id}")
    print(f"Old Values: {denial_entry.old_values}")
    print(f"New Values: {denial_entry.new_values}")
    print(f"Timestamp: {denial_entry.timestamp}")
    print("=== END AUDIT LOG ENTRY ===\n")
    
    # Verify reason is in new_values via reason_comment
    assert denial_entry.new_values is not None
    assert "reason_comment" in denial_entry.new_values
    assert denial_entry.new_values["reason_comment"] == deny_reason
    assert denial_entry.action == "reopen_rejected"


@pytest.mark.asyncio
async def test_audit_log_includes_reopen_request_reason(db: AsyncSession):
    """
    Test that reopen request reason is included in audit log.
    Shows actual audit log entry produced.
    """
    # Create a test observation
    observation_id = uuid4()
    checker_id = uuid4()
    school_id = uuid4()
    department_id = uuid4()
    
    observation = Observation(
        id=observation_id,
        kpi_id=uuid4(),
        kpi_version=1,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("90.0"),
        auto_result=AutoResult.NOT_MET,
        rag_status=RagStatus.RED,
        submitted_at=utc_now(),
        is_late=False,
        submission_token=uuid4(),
        status='rejected',
        rejected_at=utc_now(),
        rejected_by=uuid4(),
        rejection_reason="Original rejection",
    )
    db.add(observation)
    await db.commit()
    
    # Request reopen with reason
    actor_id = uuid4()
    reopen_reason = "Data entry error - corrected values available"
    
    audit_log = AuditLogService(db)
    await audit_log.log_reopen_request(
        observation_id=observation_id,
        actor_id=actor_id,
        reason=reopen_reason,
    )
    await db.commit()
    
    # Retrieve and show the actual audit log entry
    audit_entries = await audit_log.get_entity_history("observation", observation_id)
    
    assert len(audit_entries) == 1
    entry = audit_entries[0]
    
    print("\n=== ACTUAL AUDIT LOG ENTRY FOR REOPEN REQUEST ===")
    print(f"Action: {entry.action}")
    print(f"Entity Type: {entry.entity_type}")
    print(f"Entity ID: {entry.entity_id}")
    print(f"Actor ID: {entry.user_id}")
    print(f"Old Values: {entry.old_values}")
    print(f"New Values: {entry.new_values}")
    print(f"Timestamp: {entry.timestamp}")
    print("=== END AUDIT LOG ENTRY ===\n")
    
    # Verify reason is in new_values via reason_comment
    assert entry.new_values is not None
    assert "reason_comment" in entry.new_values
    assert entry.new_values["reason_comment"] == reopen_reason
    assert entry.action == "reopen_requested"
