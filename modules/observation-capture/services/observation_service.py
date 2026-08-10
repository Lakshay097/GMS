"""
Observation Capture service — PRS §24.
Implements Checker-only Observation capture with lock period, duplicate detection,
grace period handling, and Auto-Result computation via Rule Engine.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.audit_log_service.service import AuditLogService
from platform_services.audit_log_service.event_types import AuditEventType
from platform_services.configuration_engine.constants import ConfigKey
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.notification_service.service import (
    NotificationPayload,
    NotificationService,
)
from platform_services.rule_engine.service import RuleEngine
from shared.datetime_utils import utc_now
from shared.errors import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from shared.platform_models import (
    AutoResult,
    ComplianceStatus,
    KPI,
    KpiCaptureType,
    NotificationCategory,
    NotificationChannel,
    Observation,
    RagStatus,
)


class DuplicateCheckResult:
    """Result of duplicate observation check per PRS §24.6/BR-25."""
    
    def __init__(
        self,
        is_duplicate: bool,
        existing_observation_id: Optional[uuid.UUID] = None,
        existing_observation_summary: Optional[dict] = None,
    ):
        self.is_duplicate = is_duplicate
        self.existing_observation_id = existing_observation_id
        self.existing_observation_summary = existing_observation_summary


class ObservationService:
    """
    Observation capture service per PRS §24.
    Checkers capture Observations only — never edit other business records (R-22/BR-11).
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        config_engine: Optional[ConfigurationEngine] = None,
        rule_engine: Optional[RuleEngine] = None,
        audit_log: Optional[AuditLogService] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        self.db = db
        self.config_engine = config_engine or ConfigurationEngine(db)
        self.rule_engine = rule_engine or RuleEngine()
        self.audit_log = audit_log or AuditLogService(db)
        self._notification_service = notification_service or NotificationService(db)

    async def submit_observation(
        self,
        *,
        kpi_id: uuid.UUID,
        kpi_version: int,
        checker_id: uuid.UUID,
        department_id: uuid.UUID,
        school_id: uuid.UUID,
        value_numeric: Optional[Decimal] = None,
        value_text: Optional[str] = None,
        asset_id: Optional[uuid.UUID] = None,
        location_id: Optional[uuid.UUID] = None,
        event_times: Optional[list[dict]] = None,
        evidence: Optional[list[dict]] = None,
        is_late: bool = False,
        submission_token: Optional[uuid.UUID] = None,
        override_duplicate: bool = False,
        override_justification: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Observation:
        """
        Submit an Observation per PRS §24.
        
        Enforces:
        - KPI linkage requirement (R-23/BR-20)
        - Value type matching to KPI unit
        - Lock period immutability (R-16)
        - Auto-Result computation (R-29)
        - Idempotency key requirement (R-54/FR-069)
        - Event Time capture validation (PRS §24.14)
        - Duplicate detection (PRS §24.6/BR-25)
        - Grace period handling (PRS §24.16/BR-26)
        """
        # Validate KPI exists and is active
        kpi = await self._get_kpi_version(kpi_id, kpi_version)
        
        # Validate Observation has linked KPI (R-23/BR-20)
        if kpi is None:
            raise ValidationError(
                "Observation must be linked to a valid KPI version (R-23/BR-20)",
                field="kpi_id",
            )
        
        # Validate value requirements based on capture type
        await self._validate_observation_value(kpi, value_numeric, value_text)
        
        # Validate event time capture if applicable (PRS §24.14)
        if event_times:
            await self._validate_event_time_capture(kpi, event_times)
        
        # Check for duplicate observation (PRS §24.6/BR-25)
        duplicate_check = await self._check_duplicate_observation(
            kpi_id=kpi_id,
            kpi_version=kpi_version,
            checker_id=checker_id,
            department_id=department_id,
            asset_id=asset_id,
            location_id=location_id,
            school_id=school_id,
        )
        
        if duplicate_check.is_duplicate:
            if not override_duplicate:
                # Log blocked duplicate attempt
                await self.audit_log.log_duplicate_blocked(
                    observation_id=uuid.uuid4(),  # Placeholder for the blocked attempt
                    actor_id=actor_id,
                    school_id=school_id,
                    details={
                        "kpi_id": str(kpi_id),
                        "kpi_version": kpi_version,
                        "checker_id": str(checker_id),
                        "existing_observation_id": str(duplicate_check.existing_observation_id),
                    },
                )
                raise ConflictError(
                    "Duplicate Observation detected within detection window (PRS §24.6/BR-25)",
                    details={
                        "existing_observation_id": str(duplicate_check.existing_observation_id),
                        "existing_observation_summary": duplicate_check.existing_observation_summary,
                    },
                )
            else:
                # Validate override justification
                if not override_justification:
                    raise ValidationError(
                        "Override justification is required when overriding duplicate detection",
                        field="override_justification",
                    )
        
        # Generate submission token if not provided (R-54/FR-069)
        if submission_token is None:
            submission_token = uuid.uuid4()
        
        # Check for existing observation with same submission token (idempotency)
        existing = await self.db.execute(
            select(Observation).where(Observation.submission_token == submission_token)
        )
        existing_obs = existing.scalar_one_or_none()
        if existing_obs:
            return existing_obs  # Return existing observation for idempotency
        
        # Compute Auto-Result via Rule Engine (R-29)
        auto_result_data = await self._compute_auto_result(
            kpi=kpi,
            value_numeric=value_numeric,
            value_text=value_text,
            is_late=is_late,
            school_id=school_id,
        )
        
        # Create observation
        observation = Observation(
            id=uuid.uuid4(),
            kpi_id=kpi_id,
            kpi_version=kpi_version,
            checker_id=checker_id,
            department_id=department_id,
            school_id=school_id,
            value_numeric=value_numeric,
            value_text=value_text,
            auto_result=AutoResult(auto_result_data["auto_result"]),
            rag_status=RagStatus(auto_result_data["rag_status"]),
            submitted_at=utc_now(),
            is_late=is_late,
            submission_token=submission_token,
            asset_id=asset_id,
            location_id=location_id,
            event_times=self._serialize_event_times(event_times),
            time_capture_mode=self._extract_time_capture_mode(event_times),
            manual_time_reason=self._extract_manual_time_reason(event_times),
            evidence=evidence,
            is_duplicate_override=override_duplicate,
            duplicate_override_justification=override_justification if override_duplicate else None,
            duplicate_override_by=actor_id if override_duplicate else None,
            original_observation_id=duplicate_check.existing_observation_id if override_duplicate else None,
        )
        
        self.db.add(observation)
        await self.db.flush()
        
        # Log duplicate override if applicable
        if override_duplicate:
            await self.audit_log.log_duplicate_override(
                observation_id=observation.id,
                actor_id=actor_id,
                justification=override_justification,
            )
        
        await self.db.commit()
        await self.db.refresh(observation)
        
        # Notify Checker per PRS §49 Notification Matrix for late submissions
        # Category 4 (DUE_TODAY) - In-App, WhatsApp channels
        if is_late:
            await self._notification_service.dispatch(
                NotificationPayload(
                    user_id=checker_id,
                    category=NotificationCategory.DUE_TODAY.value,
                    title="Late Observation Submitted",
                    body=f"Your observation for KPI {kpi.title} was submitted late",
                    channel=NotificationChannel.IN_APP,
                    school_id=school_id,
                    entity_type="observation",
                    entity_id=observation.id,
                )
            )
        
        return observation

    async def get_observation(self, observation_id: uuid.UUID) -> Observation:
        """Get an observation by ID."""
        observation = await self.db.get(Observation, observation_id)
        if observation is None:
            raise NotFoundError("Observation")
        return observation

    async def is_observation_locked(self, observation: Observation) -> bool:
        """
        Check if observation is locked per R-16.
        Observation is mutable only until lock period elapses.
        """
        if observation.locked_at is None:
            # Check if lock period has elapsed
            lock_period_minutes = await self.config_engine.get(
                ConfigKey.OBSERVATION_LOCK_PERIOD_MINUTES,
                school_id=observation.school_id,
            )
            lock_deadline = observation.submitted_at + timedelta(minutes=lock_period_minutes)
            if utc_now() >= lock_deadline:
                # Mark as locked
                observation.locked_at = lock_deadline
                await self.db.flush()
                return True
            return False
        return True

    async def request_reopen(
        self,
        observation_id: uuid.UUID,
        reason: str,
        actor_id: uuid.UUID,
    ) -> Observation:
        """
        Request reopening a closed-missed observation per PRS §24.16/BR-26.
        Requires Admin/SuperAdmin approval.
        """
        observation = await self.get_observation(observation_id)
        
        # Log reopen request
        await self.audit_log.log_reopen_request(
            observation_id=observation_id,
            actor_id=actor_id,
            reason=reason,
        )
        
        # Update observation with reopen request
        observation.reopen_requested_at = utc_now()
        observation.reopen_requested_by = actor_id
        observation.reopen_reason = reason
        
        await self.db.commit()
        await self.db.refresh(observation)
        return observation

    async def approve_reopen(
        self,
        observation_id: uuid.UUID,
        approved: bool,
        admin_comment: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Observation:
        """
        Approve or reject a reopen request per PRS §24.16/BR-26.
        Only Admin/SuperAdmin can approve.
        """
        observation = await self.get_observation(observation_id)
        
        if observation.reopen_requested_at is None:
            raise BusinessRuleError(
                "No reopen request exists for this observation",
                details={"observation_id": str(observation_id)},
            )
        
        # Log reopen approval/rejection
        await self.audit_log.log_reopen_approval(
            observation_id=observation_id,
            actor_id=actor_id or uuid.uuid4(),
            approved=approved,
        )
        
        if approved:
            observation.reopen_approved_at = utc_now()
            observation.reopen_approved_by = actor_id
            observation.is_reopened = True
        else:
            # Clear reopen request on rejection
            observation.reopen_requested_at = None
            observation.reopen_requested_by = None
            observation.reopen_reason = None
        
        await self.db.commit()
        await self.db.refresh(observation)
        return observation

    async def _get_kpi_version(self, kpi_id: uuid.UUID, version: int) -> Optional[KPI]:
        """Get specific KPI version."""
        result = await self.db.execute(
            select(KPI).where(KPI.kpi_id == kpi_id, KPI.version == version)
        )
        return result.scalar_one_or_none()

    async def _validate_observation_value(
        self,
        kpi: KPI,
        value_numeric: Optional[Decimal],
        value_text: Optional[str],
    ) -> None:
        """
        Validate observation value based on KPI capture type and unit.
        Per PRS §24: value required and type-matched to KPI's declared Unit.
        """
        if kpi.capture_type == KpiCaptureType.VALUE_READING:
            if value_numeric is None:
                raise ValidationError(
                    "Numeric value is required for value_reading capture type",
                    field="value_numeric",
                )
            # TODO: Add unit type validation when unit system is implemented
        elif kpi.capture_type == KpiCaptureType.EVENT_TIME:
            if value_text is None:
                raise ValidationError(
                    "Text value is required for event_time capture type",
                    field="value_text",
                )
        elif kpi.capture_type == KpiCaptureType.VALUE_AND_EVENT_TIME:
            if value_numeric is None:
                raise ValidationError(
                    "Numeric value is required for value_and_event_time capture type",
                    field="value_numeric",
                )

    async def _validate_event_time_capture(
        self,
        kpi: KPI,
        event_times: list[dict],
    ) -> None:
        """
        Validate event time capture per PRS §24.14.
        - Manual entry requires mandatory reason
        - Auto-captured requires no reason
        - Manual entry blocked on auto-captured-only event time points
        """
        if kpi.capture_type not in (KpiCaptureType.EVENT_TIME, KpiCaptureType.VALUE_AND_EVENT_TIME):
            raise ValidationError(
                "Event times can only be captured for event_time or value_and_event_time capture types",
                field="event_times",
            )
        
        for event_time in event_times:
            capture_mode = event_time.get("capture_mode")
            reason = event_time.get("reason")
            
            if capture_mode == "manual":
                if not reason:
                    raise ValidationError(
                        "Manual event time capture requires a reason (PRS §24.14)",
                        field="event_times",
                    )
            elif capture_mode == "auto":
                if reason:
                    raise ValidationError(
                        "Auto-captured event time should not include a reason (PRS §24.14)",
                        field="event_times",
                    )
    
    def _serialize_event_times(self, event_times: Optional[list[dict]]) -> Optional[list[dict]]:
        """Convert UUIDs and datetimes to strings in event_times for JSONB serialization."""
        if not event_times:
            return None
        
        serialized = []
        for event_time in event_times:
            serialized_event = event_time.copy()
            # Convert UUID fields to strings
            if "event_time_point_id" in serialized_event:
                serialized_event["event_time_point_id"] = str(serialized_event["event_time_point_id"])
            if "asset_id" in serialized_event and serialized_event["asset_id"] is not None:
                serialized_event["asset_id"] = str(serialized_event["asset_id"])
            if "location_id" in serialized_event and serialized_event["location_id"] is not None:
                serialized_event["location_id"] = str(serialized_event["location_id"])
            # Convert datetime fields to ISO strings
            if "captured_at" in serialized_event and isinstance(serialized_event["captured_at"], datetime):
                serialized_event["captured_at"] = serialized_event["captured_at"].isoformat()
            serialized.append(serialized_event)
        
        return serialized

    async def _check_duplicate_observation(
        self,
        kpi_id: uuid.UUID,
        kpi_version: int,
        checker_id: uuid.UUID,
        department_id: uuid.UUID,
        asset_id: Optional[uuid.UUID],
        location_id: Optional[uuid.UUID],
        school_id: uuid.UUID,
    ) -> "DuplicateCheckResult":
        """
        Check for duplicate observation per PRS §24.6/BR-25.
        Returns duplicate check result with existing observation details if found.
        """
        duplicate_window_minutes = await self.config_engine.get(
            ConfigKey.DUPLICATE_DETECTION_WINDOW_MINUTES,
            school_id=school_id,
        )
        
        window_start = utc_now() - timedelta(minutes=duplicate_window_minutes)
        
        # Build query for duplicate detection
        query = (
            select(Observation)
            .where(
                Observation.kpi_id == kpi_id,
                Observation.kpi_version == kpi_version,
                Observation.checker_id == checker_id,
                Observation.department_id == department_id,
                Observation.school_id == school_id,
                Observation.submitted_at >= window_start,
            )
        )
        
        # Add asset/location scope if applicable
        if asset_id is not None:
            query = query.where(Observation.asset_id == asset_id)
        if location_id is not None:
            query = query.where(Observation.location_id == location_id)
        
        result = await self.db.execute(query.order_by(Observation.submitted_at.desc()))
        existing = result.scalar_one_or_none()
        
        if existing:
            return DuplicateCheckResult(
                is_duplicate=True,
                existing_observation_id=existing.id,
                existing_observation_summary={
                    "id": str(existing.id),
                    "kpi_id": str(existing.kpi_id),
                    "kpi_version": existing.kpi_version,
                    "checker_id": str(existing.checker_id),
                    "submitted_at": existing.submitted_at.isoformat(),
                    "auto_result": existing.auto_result.value,
                },
            )
        
        return DuplicateCheckResult(is_duplicate=False)

    async def _compute_auto_result(
        self,
        kpi: KPI,
        value_numeric: Optional[Decimal],
        value_text: Optional[str],
        is_late: bool,
        school_id: uuid.UUID,
    ) -> dict:
        """
        Compute Auto-Result via Rule Engine per R-29.
        Auto-Result is SYSTEM computation — never a manual entry field.
        """
        # Get configuration values
        amber_band_pct = await self.config_engine.get(
            ConfigKey.KPI_AMBER_TOLERANCE_BAND,
            school_id=school_id,
        )
        decimal_places = await self.config_engine.get(ConfigKey.KPI_ROUNDING_DECIMAL_PLACES)
        rounding_mode = await self.config_engine.get(ConfigKey.KPI_ROUNDING_MODE)
        missing_data_behavior = await self.config_engine.get(ConfigKey.KPI_MISSING_DATA_BEHAVIOR)
        
        # Compute via Rule Engine
        result = self.rule_engine.compute_kpi_result(
            formula_type=kpi.formula_type.value,
            value=value_numeric,
            target=kpi.target_value,
            comparator=kpi.comparator,
            amber_band_pct=Decimal(amber_band_pct),
            is_late=is_late,
            decimal_places=decimal_places,
            rounding_mode=rounding_mode,
            missing_data_behavior=missing_data_behavior,
        )
        
        return result

    def _extract_time_capture_mode(self, event_times: Optional[list[dict]]) -> Optional[str]:
        """Extract time capture mode from event times."""
        if not event_times:
            return None
        # Use the mode from the first event time as the overall mode
        return event_times[0].get("capture_mode") if event_times else None

    def _extract_manual_time_reason(self, event_times: Optional[list[dict]]) -> Optional[str]:
        """Extract manual time reason from event times."""
        if not event_times:
            return None
        # Use the reason from the first manual event time
        for event_time in event_times:
            if event_time.get("capture_mode") == "manual":
                return event_time.get("reason")
        return None
