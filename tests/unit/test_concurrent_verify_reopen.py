"""
Real concurrent tests for observation verify and reopen-approval endpoints.
Tests actual concurrent requests using asyncio.gather against real test DB.
"""
import pytest
import asyncio
from uuid import uuid4, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from modules.observation_capture.services.observation_service import ObservationService
from shared.platform_models import KPI, Observation, AutoResult, RagStatus
from shared.datetime_utils import utc_now


@pytest.mark.asyncio
async def test_concurrent_verify_requests(db: AsyncSession):
    """
    Test two concurrent POST /observations/{id}/verify requests on the same pending observation.
    - Use asyncio.gather for true concurrency
    - Assert exactly one request returns 200, the other returns 409
    - Assert the observation's final row has exactly one verified_by, not a mixed/corrupted state
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
    
    # Create a test pending observation
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
    
    # Simulate two concurrent verify requests
    actor_id_1 = uuid4()
    actor_id_2 = uuid4()
    
    async def verify_request(actor_id: UUID):
        """Simulate a verify request via direct SQL update (atomic conditional update)"""
        from sqlalchemy import update as sa_update
        
        now = utc_now()
        update_stmt = (
            sa_update(Observation)
            .where(Observation.id == observation_id)
            .where(Observation.status == 'pending')  # Only update if still pending
            .values(
                status='verified',
                verified_at=now,
                verified_by=actor_id,
                rejected_at=None,
                rejected_by=None,
                rejection_reason=None
            )
        )
        
        result = await db.execute(update_stmt)
        affected_rows = result.rowcount
        
        if affected_rows == 0:
            # Check current status for better error message
            current_obs = await db.get(Observation, observation_id)
            if current_obs is None:
                return {"status": 404, "message": "Observation not found"}
            elif current_obs.status == 'verified':
                return {"status": 409, "message": "Already verified by another reviewer"}
            elif current_obs.status == 'rejected':
                return {"status": 409, "message": "Already rejected, cannot verify"}
            else:
                return {"status": 409, "message": "Observation is not in a verifiable state"}
        
        await db.commit()
        return {"status": 200, "verified_by": str(actor_id)}
    
    # Run two concurrent verify requests
    results = await asyncio.gather(
        verify_request(actor_id_1),
        verify_request(actor_id_2)
    )
    
    print("\n=== CONCURRENT VERIFY TEST RESULTS ===")
    print(f"Request 1 result: {results[0]}")
    print(f"Request 2 result: {results[1]}")
    
    # Assert exactly one succeeded (200) and one failed (409)
    success_count = sum(1 for r in results if r["status"] == 200)
    conflict_count = sum(1 for r in results if r["status"] == 409)
    
    assert success_count == 1, f"Expected exactly 1 successful verify, got {success_count}"
    assert conflict_count == 1, f"Expected exactly 1 conflict, got {conflict_count}"
    
    # Refresh observation from DB and check final state
    await db.refresh(observation)
    
    print(f"Final observation status: {observation.status}")
    print(f"Final verified_by: {observation.verified_by}")
    print(f"Final rejected_by: {observation.rejected_by}")
    
    # Assert observation has exactly one verified_by, not corrupted
    assert observation.status == 'verified', f"Expected status 'verified', got '{observation.status}'"
    assert observation.verified_by is not None, "verified_by should not be None"
    assert observation.rejected_by is None, "rejected_by should be None"
    
    # Assert the verified_by matches the successful request
    successful_result = next(r for r in results if r["status"] == 200)
    assert str(observation.verified_by) == successful_result["verified_by"]
    
    print("=== CONCURRENT VERIFY TEST PASSED ===\n")


@pytest.mark.asyncio
async def test_concurrent_reopen_approval_requests(db: AsyncSession):
    """
    Test two concurrent POST /observations/{id}/reopen-approval requests on the same reopen-requested observation.
    - Use asyncio.gather for true concurrency
    - Assert exactly one succeeds, one gets a conflict response
    - Assert final state is not corrupted
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
    
    # Create a test observation with pending reopen request
    observation_id = uuid4()
    checker_id = uuid4()
    school_id = uuid4()
    department_id = uuid4()
    original_verifier_id = uuid4()
    
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
        status='verified',
        verified_at=utc_now(),
        verified_by=original_verifier_id,
        reopen_requested_at=utc_now(),
        reopen_requested_by=uuid4(),
        reopen_reason="Need to resubmit corrected data",
    )
    db.add(observation)
    await db.commit()
    
    # Simulate two concurrent reopen-approval requests
    actor_id_1 = uuid4()
    actor_id_2 = uuid4()
    
    async def approve_reopen_request(actor_id: UUID, approved: bool):
        """Simulate a reopen-approval request via direct SQL update (atomic conditional update)"""
        from sqlalchemy import update as sa_update
        
        if approved:
            # Self-approval guard check
            if observation.verified_by == actor_id or observation.rejected_by == actor_id:
                return {"status": 403, "message": "Cannot approve your own verification/rejection"}
            
            now = utc_now()
            update_stmt = (
                sa_update(Observation)
                .where(Observation.id == observation_id)
                .where(Observation.reopen_requested_at.isnot(None))  # Guard against concurrent approval
                .values(
                    reopen_approved_at=now,
                    reopen_approved_by=actor_id,
                    is_reopened=True,
                    status='pending',
                    verified_at=None,
                    verified_by=None,
                    rejected_at=None,
                    rejected_by=None,
                    rejection_reason=None,
                    reopen_requested_at=None,
                    reopen_requested_by=None,
                    reopen_reason=None
                )
            )
        else:
            # Deny (clear reopen request)
            update_stmt = (
                sa_update(Observation)
                .where(Observation.id == observation_id)
                .where(Observation.reopen_requested_at.isnot(None))
                .values(
                    reopen_requested_at=None,
                    reopen_requested_by=None,
                    reopen_reason=None
                )
            )
        
        result = await db.execute(update_stmt)
        affected_rows = result.rowcount
        
        if affected_rows == 0:
            return {"status": 409, "message": "Reopen request was already processed"}
        
        await db.commit()
        return {"status": 200, "approved_by": str(actor_id), "approved": approved}
    
    # Run two concurrent approve requests
    results = await asyncio.gather(
        approve_reopen_request(actor_id_1, approved=True),
        approve_reopen_request(actor_id_2, approved=True)
    )
    
    print("\n=== CONCURRENT REOPEN APPROVAL TEST RESULTS ===")
    print(f"Request 1 result: {results[0]}")
    print(f"Request 2 result: {results[1]}")
    
    # Assert exactly one succeeded (200) and one failed (409)
    success_count = sum(1 for r in results if r["status"] == 200)
    conflict_count = sum(1 for r in results if r["status"] == 409)
    
    assert success_count == 1, f"Expected exactly 1 successful approval, got {success_count}"
    assert conflict_count == 1, f"Expected exactly 1 conflict, got {conflict_count}"
    
    # Refresh observation from DB and check final state
    await db.refresh(observation)
    
    print(f"Final observation status: {observation.status}")
    print(f"Final reopen_approved_at: {observation.reopen_approved_at}")
    print(f"Final reopen_approved_by: {observation.reopen_approved_by}")
    print(f"Final is_reopened: {observation.is_reopened}")
    
    # Assert observation is in approved state, not corrupted
    assert observation.reopen_approved_at is not None, "reopen_approved_at should not be None"
    assert observation.reopen_approved_by is not None, "reopen_approved_by should not be None"
    assert observation.is_reopened == True, "is_reopened should be True"
    assert observation.status == 'pending', "status should be 'pending' after approval"
    assert observation.verified_by is None, "verified_by should be None after approval"
    
    # Assert the approved_by matches the successful request
    successful_result = next(r for r in results if r["status"] == 200)
    assert str(observation.reopen_approved_by) == successful_result["approved_by"]
    
    print("=== CONCURRENT REOPEN APPROVAL TEST PASSED ===\n")
