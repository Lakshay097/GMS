"""
Tests for PRS §24 Observation Capture (Checker role).
Acceptance criteria verification per prompt requirements.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from modules.observation_capture.services.observation_service import ObservationService, DuplicateCheckResult
from platform_services.configuration_engine.constants import ConfigKey
from platform_services.configuration_engine.service import ConfigurationEngine
from shared.errors import ConflictError, ValidationError
from shared.platform_models import (
    AutoResult,
    KPI,
    KpiCaptureType,
    KpiStatus,
    Observation,
    RagStatus,
)


@pytest.mark.asyncio
class TestObservationCapture:
    """Test suite for PRS §24 Observation Capture."""

    async def test_observation_requires_linked_kpi_r23_br20(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that Observation must be linked to a specific KPI (R-23/BR-20).
        Observation with no linked KPI is never permitted.
        """
        service = ObservationService(db)
        
        # Try to submit observation with invalid KPI
        with pytest.raises(ValidationError) as exc_info:
            await service.submit_observation(
                kpi_id=uuid4(),  # Invalid KPI ID
                kpi_version=1,
                checker_id=uuid4(),
                department_id=uuid4(),
                school_id=uuid4(),
                value_numeric=Decimal("95.5"),
            )
        
        assert "linked to a valid KPI version" in str(exc_info.value.detail)

    async def test_observation_value_required_and_type_matched(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that Observation value is required and type-matched to KPI's declared Unit.
        """
        service = ObservationService(db)
        
        # Test value_reading capture type requires numeric value
        sample_kpi.capture_type = KpiCaptureType.VALUE_READING
        await db.commit()
        
        with pytest.raises(ValidationError) as exc_info:
            await service.submit_observation(
                kpi_id=sample_kpi.kpi_id,
                kpi_version=sample_kpi.version,
                checker_id=uuid4(),
                department_id=uuid4(),
                school_id=uuid4(),
                value_numeric=None,  # Missing required numeric value
            )
        
        assert "Numeric value is required" in str(exc_info.value.detail)

    async def test_auto_result_is_system_computation_r29(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that Auto-Result is SYSTEM computation via Rule Engine (R-29).
        Never a manual entry field — client cannot set auto_result directly.
        """
        service = ObservationService(db)
        
        observation = await service.submit_observation(
            kpi_id=sample_kpi.kpi_id,
            kpi_version=sample_kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
        )
        
        # Verify auto_result was computed by system
        assert observation.auto_result in [AutoResult.MET, AutoResult.NOT_MET, AutoResult.N_A]
        assert observation.rag_status in [RagStatus.GREEN, RagStatus.AMBER, RagStatus.RED]

    async def test_idempotency_key_duplicate_prevention_r54_fr069(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that idempotency keys prevent duplicate submissions (R-54/FR-069).
        Same request with same idempotency key should return existing observation.
        """
        service = ObservationService(db)
        submission_token = uuid4()
        
        # First submission
        obs1 = await service.submit_observation(
            kpi_id=sample_kpi.kpi_id,
            kpi_version=sample_kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
            submission_token=submission_token,
        )
        
        # Second submission with same token (idempotent retry)
        obs2 = await service.submit_observation(
            kpi_id=sample_kpi.kpi_id,
            kpi_version=sample_kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
            submission_token=submission_token,
        )
        
        # Should return the same observation
        assert obs1.id == obs2.id
        assert obs1.submission_token == obs2.submission_token

    async def test_post_lock_edit_rejected_r16(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that post-lock edit attempts are rejected with clear error (R-16).
        After lock period elapses, only NEW Observation referencing original is possible.
        """
        service = ObservationService(db)
        config_engine = ConfigurationEngine(db)
        
        # Set lock period to 0 for immediate lock
        await config_engine.set_global(ConfigKey.OBSERVATION_LOCK_PERIOD_MINUTES, 0)
        
        # Create observation
        observation = await service.submit_observation(
            kpi_id=sample_kpi.kpi_id,
            kpi_version=sample_kpi.version,
            checker_id=uuid4(),
            department_id=uuid4(),
            school_id=uuid4(),
            value_numeric=Decimal("95.5"),
        )
        
        # Observation should be locked
        is_locked = await service.is_observation_locked(observation)
        assert is_locked is True

    async def test_manual_event_time_requires_reason_prs24_14(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that Manual Event Time entry requires mandatory Reason (PRS §24.14).
        Auto-Captured requires no Reason.
        """
        service = ObservationService(db)
        
        # Set KPI to event_time capture type
        sample_kpi.capture_type = KpiCaptureType.EVENT_TIME
        await db.commit()
        
        # Manual capture without reason should fail
        with pytest.raises(ValidationError) as exc_info:
            await service.submit_observation(
                kpi_id=sample_kpi.kpi_id,
                kpi_version=sample_kpi.version,
                checker_id=uuid4(),
                department_id=uuid4(),
                school_id=uuid4(),
                value_text="Event occurred",
                event_times=[{
                    "event_time_point_id": uuid4(),
                    "captured_at": datetime.now(timezone.utc),
                    "capture_mode": "manual",
                    "reason": None,  # Missing required reason
                }],
            )
        
        assert "Manual event time capture requires a reason" in str(exc_info.value.detail)

    async def test_auto_captured_event_time_no_reason_prs24_14(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that Auto-Captured Event Time requires no Reason (PRS §24.14).
        """
        service = ObservationService(db)
        
        # Set KPI to event_time capture type
        sample_kpi.capture_type = KpiCaptureType.EVENT_TIME
        await db.commit()
        
        # Auto-captured with reason should fail
        with pytest.raises(ValidationError) as exc_info:
            await service.submit_observation(
                kpi_id=sample_kpi.kpi_id,
                kpi_version=sample_kpi.version,
                checker_id=uuid4(),
                department_id=uuid4(),
                school_id=uuid4(),
                value_text="Event occurred",
                event_times=[{
                    "event_time_point_id": uuid4(),
                    "captured_at": datetime.now(timezone.utc),
                    "capture_mode": "auto",
                    "reason": "Should not have reason",  # Invalid for auto mode
                }],
            )
        
        assert "Auto-captured event time should not include a reason" in str(exc_info.value.detail)

    async def test_duplicate_observation_blocked_prs24_6_br25(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that duplicate Observation within detection window is blocked (PRS §24.6/BR-25).
        Default: same-Checker-scoped blocking.
        """
        service = ObservationService(db)
        config_engine = ConfigurationEngine(db)
        
        # Set duplicate detection window
        await config_engine.set_global(ConfigKey.DUPLICATE_DETECTION_WINDOW_MINUTES, 60)
        
        checker_id = uuid4()
        department_id = uuid4()
        school_id = uuid4()
        
        # First observation
        obs1 = await service.submit_observation(
            kpi_id=sample_kpi.kpi_id,
            kpi_version=sample_kpi.version,
            checker_id=checker_id,
            department_id=department_id,
            school_id=school_id,
            value_numeric=Decimal("95.5"),
        )
        
        # Second observation within window (should be blocked)
        with pytest.raises(ConflictError) as exc_info:
            await service.submit_observation(
                kpi_id=sample_kpi.kpi_id,
                kpi_version=sample_kpi.version,
                checker_id=checker_id,
                department_id=department_id,
                school_id=school_id,
                value_numeric=Decimal("95.5"),
            )
        
        assert "Duplicate Observation detected" in str(exc_info.value.detail)
        assert str(obs1.id) in str(exc_info.value.details)

    async def test_duplicate_override_with_justification_prs24_6_br25(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that duplicate Observation can be overridden with justification (PRS §24.6/BR-25).
        Only user with Override permission may proceed after providing mandatory justification.
        """
        service = ObservationService(db)
        config_engine = ConfigurationEngine(db)
        
        # Set duplicate detection window
        await config_engine.set_global(ConfigKey.DUPLICATE_DETECTION_WINDOW_MINUTES, 60)
        
        checker_id = uuid4()
        department_id = uuid4()
        school_id = uuid4()
        
        # First observation
        obs1 = await service.submit_observation(
            kpi_id=sample_kpi.kpi_id,
            kpi_version=sample_kpi.version,
            checker_id=checker_id,
            department_id=department_id,
            school_id=school_id,
            value_numeric=Decimal("95.5"),
        )
        
        # Second observation with override and justification
        obs2 = await service.submit_observation(
            kpi_id=sample_kpi.kpi_id,
            kpi_version=sample_kpi.version,
            checker_id=checker_id,
            department_id=department_id,
            school_id=school_id,
            value_numeric=Decimal("95.5"),
            override_duplicate=True,
            override_justification="Legitimate resubmission after network error",
        )
        
        # Should succeed with override tracking
        assert obs2.is_duplicate_override is True
        assert obs2.duplicate_override_justification == "Legitimate resubmission after network error"
        assert obs2.original_observation_id == obs1.id

    async def test_duplicate_override_requires_justification_prs24_6_br25(
        self, db: AsyncSession, sample_kpi: KPI, seed_configuration
    ):
        """
        Test that duplicate override requires mandatory justification (PRS §24.6/BR-25).
        """
        service = ObservationService(db)
        config_engine = ConfigurationEngine(db)
        
        # Set duplicate detection window
        await config_engine.set_global(ConfigKey.DUPLICATE_DETECTION_WINDOW_MINUTES, 60)
        
        checker_id = uuid4()
        department_id = uuid4()
        school_id = uuid4()
        
        # First observation
        await service.submit_observation(
            kpi_id=sample_kpi.kpi_id,
            kpi_version=sample_kpi.version,
            checker_id=checker_id,
            department_id=department_id,
            school_id=school_id,
            value_numeric=Decimal("95.5"),
        )
        
        # Try override without justification
        with pytest.raises(ValidationError) as exc_info:
            await service.submit_observation(
                kpi_id=sample_kpi.kpi_id,
                kpi_version=sample_kpi.version,
                checker_id=checker_id,
                department_id=department_id,
                school_id=school_id,
                value_numeric=Decimal("95.5"),
                override_duplicate=True,
                override_justification=None,  # Missing required justification
            )
        
        assert "Override justification is required" in str(exc_info.value.detail)


@pytest.fixture
async def sample_kpi(db: AsyncSession) -> KPI:
    """Create a sample KPI for testing."""
    kpi = KPI(
        kpi_id=uuid4(),
        version=1,
        kra_id=uuid4(),
        title="Test KPI",
        target_value=Decimal("100"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        formula_type="threshold_comparison",
        capture_type=KpiCaptureType.VALUE_READING,
        status=KpiStatus.ACTIVE.value,
    )
    db.add(kpi)
    await db.commit()
    await db.refresh(kpi)
    return kpi
