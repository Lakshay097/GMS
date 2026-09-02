"""KRA/KPI domain schemas."""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EventTimePointInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    capture_mode_allowed: str = "manual_only"
    target_time: Optional[time] = None


class KraCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class KraUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None


class KraResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    status: str

    model_config = {"from_attributes": True}


class KpiCreateRequest(BaseModel):
    kra_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    target_value: Decimal
    comparator: str
    unit_of_measure: str = Field(..., min_length=1, max_length=50)
    frequency_code: str
    capture_type: str = "value_reading"
    category_code: Optional[str] = None
    is_sensitive: bool = False
    amber_tolerance_band: Optional[Decimal] = None
    working_days: Optional[list[str]] = None
    non_working_day_policy: str = "skip"
    event_time_points: list[EventTimePointInput] = Field(default_factory=list)


class KpiUpdateRequest(BaseModel):
    target_value: Optional[Decimal] = None
    comparator: Optional[str] = None
    unit_of_measure: Optional[str] = None
    title: Optional[str] = None
    frequency_code: Optional[str] = None
    capture_type: Optional[str] = None
    category_code: Optional[str] = None
    is_sensitive: Optional[bool] = None
    amber_tolerance_band: Optional[Decimal] = None
    working_days: Optional[list[str]] = None
    non_working_day_policy: Optional[str] = None
    event_time_points: Optional[list[EventTimePointInput]] = None


class EventTimePointResponse(BaseModel):
    """Response model for event time point attached to a KPI."""
    id: UUID
    name: str
    capture_mode_allowed: str
    target_time: Optional[time] = None

    model_config = {"from_attributes": True}


class KpiResponse(BaseModel):
    kpi_id: UUID
    version: int
    kra_id: UUID
    title: str
    target_value: Decimal
    comparator: str
    unit_of_measure: str
    frequency_code: str
    formula_type: str
    capture_type: str
    category_code: Optional[str]
    is_sensitive: bool
    amber_tolerance_band: Optional[Decimal]
    working_days: Optional[list[str]]
    non_working_day_policy: str
    status: str
    is_immutable: bool
    event_time_points: list[EventTimePointResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class KpiImportRequest(BaseModel):
  confirm_sme_review: bool = False
  seed_file_path: Optional[str] = None


class ObservationSubmitRequest(BaseModel):
    kpi_id: UUID
    kpi_version: int
    value_numeric: Optional[Decimal] = None
    value_text: Optional[str] = None
    is_late: bool = False
    submission_token: Optional[UUID] = None
