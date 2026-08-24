"""Observation Capture domain schemas — PRS §24."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class EventTimeCapture(BaseModel):
    """Event time capture per PRS §24.14."""
    event_time_point_id: UUID
    captured_at: datetime
    capture_mode: str = Field(..., description="auto or manual")
    asset_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    reason: Optional[str] = Field(None, description="Required for manual capture mode")


class EvidenceUpload(BaseModel):
    """Evidence upload request per PRS §24 and Architecture §18/ADR-07."""
    file_name: str = Field(..., min_length=1, max_length=255)
    file_size_bytes: int = Field(..., gt=0)
    content_type: str = Field(..., min_length=1, max_length=100)
    cloudinary_public_id: Optional[str] = None
    cloudinary_url: Optional[HttpUrl] = None


class ObservationSubmitRequest(BaseModel):
    """Observation submission request per PRS §24."""
    kpi_id: UUID
    kpi_version: int
    checker_id: UUID
    department_id: UUID
    school_id: UUID
    value_numeric: Optional[Decimal] = None
    value_text: Optional[str] = Field(None, max_length=1000)
    asset_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    event_times: list[EventTimeCapture] = Field(default_factory=list)
    evidence: list[EvidenceUpload] = Field(default_factory=list)
    is_late: bool = False
    submission_token: UUID = Field(default_factory=uuid.uuid4)
    override_duplicate: bool = False
    override_justification: Optional[str] = Field(None, max_length=500)


class ObservationResponse(BaseModel):
    """Observation response per PRS §24."""
    id: UUID
    kpi_id: UUID
    kpi_version: int
    checker_id: UUID
    department_id: UUID
    school_id: UUID
    value_numeric: Optional[Decimal]
    value_text: Optional[str]
    auto_result: str
    rag_status: str
    submitted_at: datetime
    is_late: bool
    submission_token: UUID
    asset_id: Optional[UUID]
    location_id: Optional[UUID]
    event_times: Optional[list[dict]]
    time_capture_mode: Optional[str]
    manual_time_reason: Optional[str]
    evidence_count: int = 0
    is_locked: bool = False
    status: str = "pending"
    verified_at: Optional[datetime] = None
    verified_by: Optional[UUID] = None
    rejected_at: Optional[datetime] = None
    rejected_by: Optional[UUID] = None
    rejection_reason: Optional[str] = None
    # Reopen request fields per PRS §24.16/BR-26
    is_reopened: bool = False
    reopen_requested_at: Optional[datetime] = None
    reopen_requested_by: Optional[UUID] = None
    reopen_reason: Optional[str] = None
    reopen_approved_at: Optional[datetime] = None
    reopen_approved_by: Optional[UUID] = None
    # Enriched display fields for list views (populated by list endpoint JOINs)
    title: Optional[str] = None
    description: Optional[str] = None
    observer_name: Optional[str] = None
    school_name: Optional[str] = None
    department_name: Optional[str] = None
    category_name: Optional[str] = None
    observation_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DuplicateDetectionResponse(BaseModel):
    """Duplicate detection response per PRS §24.6/BR-25."""
    is_duplicate: bool
    existing_observation_id: Optional[UUID] = None
    existing_observation_summary: Optional[dict] = None


class VerifyRequest(BaseModel):
    """Observation verification request."""
    pass


class RejectRequest(BaseModel):
    """Observation rejection request."""
    reason: str = Field(..., min_length=1, max_length=500, description="Rejection reason")


class ReopenRequest(BaseModel):
    """Reopen request per PRS §24.16/BR-26."""
    reason: str = Field(..., min_length=1, max_length=500)


class ReopenApprovalRequest(BaseModel):
    """Reopen approval request per PRS §24.16/BR-26."""
    approved: bool
    admin_comment: Optional[str] = Field(None, max_length=500)
