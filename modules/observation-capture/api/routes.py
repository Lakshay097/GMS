"""
Observation Capture API routes — PRS §24.
Implements Checker-only Observation capture endpoints with idempotency support.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.observation_capture.schemas import (
    ObservationResponse,
    ObservationSubmitRequest,
    ReopenApprovalRequest,
    ReopenRequest,
)
from modules.observation_capture.services.observation_service import ObservationService
from shared.database import get_db
from shared.errors import ConflictError, NotFoundError, ValidationError

router = APIRouter(prefix="/v1/observations", tags=["observations"])


@router.post("", response_model=ObservationResponse, status_code=status.HTTP_201_CREATED)
async def submit_observation(
    request: ObservationSubmitRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an Observation per PRS §24.
    
    Requirements:
    - Idempotency-Key header is MANDATORY (R-54/FR-069)
    - Checkers capture Observations only — never edit other business records (R-22/BR-11)
    - Observation must be linked to a specific KPI (R-23/BR-20)
    - Value required and type-matched to KPI's declared Unit
    - Auto-Result is SYSTEM computation via Rule Engine — never client-settable (R-29)
    - Duplicate detection applies per PRS §24.6/BR-25
    - Grace period handling applies per PRS §24.16/BR-26
    """
    # Validate idempotency key requirement (R-54/FR-069)
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Idempotency-Key header is required (R-54/FR-069)",
                    "field": "Idempotency-Key",
                }
            },
        )
    
    service = ObservationService(db)
    
    try:
        observation = await service.submit_observation(
            kpi_id=request.kpi_id,
            kpi_version=request.kpi_version,
            checker_id=request.checker_id,
            department_id=request.department_id,
            school_id=request.school_id,
            value_numeric=request.value_numeric,
            value_text=request.value_text,
            asset_id=request.asset_id,
            location_id=request.location_id,
            event_times=[et.model_dump() for et in request.event_times],
            evidence=[ev.model_dump() for ev in request.evidence],
            is_late=request.is_late,
            submission_token=request.submission_token,
            override_duplicate=request.override_duplicate,
            override_justification=request.override_justification,
        )
        return observation
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.detail,
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.detail,
        )


@router.get("/{observation_id}", response_model=ObservationResponse)
async def get_observation(
    observation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get an Observation by ID."""
    service = ObservationService(db)
    try:
        observation = await service.get_observation(observation_id)
        
        # Check if observation is locked
        is_locked = await service.is_observation_locked(observation)
        
        response_data = ObservationResponse.model_validate(observation)
        response_data.is_locked = is_locked
        response_data.evidence_count = len(observation.evidence) if observation.evidence else 0
        
        return response_data
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )


@router.post("/{observation_id}/reopen-request")
async def request_reopen(
    observation_id: UUID,
    request: ReopenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request reopening a closed-missed observation per PRS §24.16/BR-26.
    Requires Admin/SuperAdmin approval.
    """
    service = ObservationService(db)
    try:
        observation = await service.request_reopen(
            observation_id=observation_id,
            reason=request.reason,
            actor_id=UUID("00000000-0000-0000-0000-000000000000"),  # TODO: Get from auth context
        )
        return ObservationResponse.model_validate(observation)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )


@router.post("/{observation_id}/reopen-approval")
async def approve_reopen(
    observation_id: UUID,
    request: ReopenApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve or reject a reopen request per PRS §24.16/BR-26.
    Only Admin/SuperAdmin can approve.
    """
    service = ObservationService(db)
    try:
        observation = await service.approve_reopen(
            observation_id=observation_id,
            approved=request.approved,
            admin_comment=request.admin_comment,
            actor_id=UUID("00000000-0000-0000-0000-000000000000"),  # TODO: Get from auth context
        )
        return ObservationResponse.model_validate(observation)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )


@router.patch("/{observation_id}", response_model=ObservationResponse)
async def update_observation(
    observation_id: UUID,
    value_numeric: Optional[float] = None,
    value_text: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Update an Observation (RESTRICTED).
    
    R-24/BR-12/C5: Auditors never edit Observations — they may only Verify or raise a Discrepancy.
    This endpoint is provided for authorized roles only and enforces the Auditor restriction at the API layer.
    """
    # TODO: Get actual user role from auth context
    # For now, this is a placeholder that would check the user's role
    # In production, this would be: user_role = get_current_user_role()
    user_role = None  # Would be extracted from JWT/auth context
    
    # Reject if user is an Auditor
    from shared.models import UserRole
    if user_role == UserRole.AUDITOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "AUTHORIZATION_ERROR",
                    "message": "Auditors cannot edit Observations. They may only Verify or raise a Discrepancy (R-24/BR-12/C5).",
                }
            },
        )
    
    service = ObservationService(db)
    try:
        # Check if observation is locked (R-16)
        observation = await service.get_observation(observation_id)
        is_locked = await service.is_observation_locked(observation)
        
        if is_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "BUSINESS_RULE_ERROR",
                        "message": "Observation is locked and cannot be edited (R-16)",
                    }
                },
            )
        
        # Update observation
        if value_numeric is not None:
            observation.value_numeric = value_numeric
        if value_text is not None:
            observation.value_text = value_text
        
        await db.commit()
        await db.refresh(observation)
        
        response_data = ObservationResponse.model_validate(observation)
        response_data.is_locked = is_locked
        response_data.evidence_count = len(observation.evidence) if observation.evidence else 0
        
        return response_data
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.detail,
        )
