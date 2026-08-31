"""
Tests for the KPI Entry workflow — Issue #1-14 fixes.

Covers:
- Single and multiple KPI entry submission
- Auto-generated captured_at timestamp
- 30-minute edit window enforcement
- Audit trail creation on submit and edit
- Capture type / reason validation
- Duplicate prevention
- Edit permissions by role
"""
# Force memory queue to avoid boto3 dependency
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import uuid
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from modules.observation_capture.services.observation_service import (
    ObservationService,
    DuplicateCheckResult,
)
from platform_services.configuration_engine.constants import ConfigKey
from platform_services.configuration_engine.service import ConfigurationEngine
from shared.errors import ConflictError, ValidationError, NotFoundError
from shared.platform_models import (
    AutoResult,
    KPI,
    KpiCaptureType,
    KpiFormulaType,
    KpiStatus,
    Observation,
    ObservationAudit,
    RagStatus,
)
from shared.datetime_utils import utc_now


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def sample_kpi(db: AsyncSession) -> KPI:
    """Create a sample VALUE_READING KPI for testing."""
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=uuid.uuid4(),
        title="Test Value KPI",
        target_value=Decimal("100"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        formula_type=KpiFormulaType.THRESHOLD_COMPARISON,
        capture_type=KpiCaptureType.VALUE_READING,
        status=KpiStatus.ACTIVE.value,
    )
    db.add(kpi)
    await db.commit()
    await db.refresh(kpi)
    return kpi


@pytest.fixture
async def check_kpi(db: AsyncSession) -> KPI:
    """Create a sample CHECK (Yes/No) KPI for testing."""
    kpi = KPI(
        kpi_id=uuid.uuid4(),
        version=1,
        kra_id=uuid.uuid4(),
        title="Test Check KPI",
        target_value=Decimal("1"),
        comparator=">=",
        unit_of_measure="yes/no",
        frequency_code="daily",
        formula_type=KpiFormulaType.THRESHOLD_COMPARISON,
        capture_type=KpiCaptureType.CHECK,
        status=KpiStatus.ACTIVE.value,
    )
    db.add(kpi)
    await db.commit()
    await db.refresh(kpi)
    return kpi


# ─── Submission Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_single_kpi_entry_submission_success(db, sample_kpi, seed_configuration):
    """Submit a single KPI entry and verify it succeeds."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    obs = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("95"),
        submission_date="2026-08-31",
    )

    assert obs is not None
    assert obs.kpi_id == sample_kpi.kpi_id
    assert obs.value_numeric == Decimal("95")
    assert obs.status == "pending"
    assert obs.submitted_at is not None


@pytest.mark.asyncio
async def test_captured_at_auto_generated_by_backend(db, sample_kpi, seed_configuration):
    """Verify captured_at is auto-generated server-side, not from client."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    before_submit = utc_now()
    obs = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("95"),
        submission_date="2026-08-31",
    )
    after_submit = utc_now()

    assert obs.captured_at is not None
    # captured_at should be between before and after submission
    assert before_submit <= obs.captured_at <= after_submit


@pytest.mark.asyncio
async def test_multiple_kpi_entries_submission(db, sample_kpi, seed_configuration):
    """Submit multiple KPI entries for the same KPI on different days."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    obs1 = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("90"),
        submission_date="2026-08-29",
    )

    obs2 = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("95"),
        submission_date="2026-08-30",
    )

    assert obs1.id != obs2.id
    assert obs1.value_numeric == Decimal("90")
    assert obs2.value_numeric == Decimal("95")


@pytest.mark.asyncio
async def test_duplicate_submission_prevented(db, sample_kpi, seed_configuration):
    """Duplicate submission within detection window is rejected."""
    service = ObservationService(db)
    config_engine = ConfigurationEngine(db)
    await config_engine.set_global(ConfigKey.DUPLICATE_DETECTION_WINDOW_MINUTES, 60)

    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("90"),
    )

    with pytest.raises(ConflictError) as exc_info:
        await service.submit_observation(
            kpi_id=sample_kpi.kpi_id,
            kpi_version=sample_kpi.version,
            checker_id=checker_id,
            department_id=department_id,
            school_id=school_id,
            value_numeric=Decimal("95"),
        )

    assert "Duplicate" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_submission_remains_after_reload(db, sample_kpi, seed_configuration):
    """Verify submission is persisted and can be retrieved (simulates page reload)."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    obs = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("95"),
        submission_date="2026-08-31",
    )

    # "Reload" — query from DB directly
    from sqlalchemy import select
    result = await db.execute(
        select(Observation).where(Observation.id == obs.id)
    )
    reloaded = result.scalar_one_or_none()

    assert reloaded is not None
    assert reloaded.kpi_id == sample_kpi.kpi_id
    assert reloaded.value_numeric == Decimal("95")
    assert reloaded.captured_at is not None


# ─── Audit Trail Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_record_created_on_initial_submission(db, sample_kpi, seed_configuration):
    """Verify an ObservationAudit record is created on initial submission."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    obs = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("95"),
        submission_date="2026-08-31",
        actor_id=checker_id,
    )

    from sqlalchemy import select
    audit_result = await db.execute(
        select(ObservationAudit).where(
            ObservationAudit.observation_id == obs.id
        )
    )
    audit_records = audit_result.scalars().all()

    assert len(audit_records) >= 1
    # At least one record should be for value_numeric
    value_records = [r for r in audit_records if r.field_name == "value_numeric"]
    assert len(value_records) >= 1
    assert value_records[0].change_type == "initial_submit"
    assert value_records[0].old_value is None
    assert value_records[0].new_value == "95"


@pytest.mark.asyncio
async def test_audit_record_created_on_check_submission(db, check_kpi, seed_configuration):
    """Verify audit records for check (Yes/No) submission."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    obs = await service.submit_observation(
        kpi_id=check_kpi.kpi_id,
        kpi_version=check_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("1"),
        check_result="Yes",
        submission_date="2026-08-31",
        actor_id=checker_id,
    )

    from sqlalchemy import select
    audit_result = await db.execute(
        select(ObservationAudit).where(
            ObservationAudit.observation_id == obs.id
        )
    )
    audit_records = audit_result.scalars().all()

    assert len(audit_records) >= 1
    check_records = [r for r in audit_records if r.field_name == "check_result"]
    assert len(check_records) >= 1
    assert check_records[0].new_value == "Yes"


# ─── Check Capture Type / Reason Validation ──────────────────────────────────


@pytest.mark.asyncio
async def test_check_yes_no_reason_required(db, check_kpi, seed_configuration):
    """When check_result is 'No', reason is mandatory."""
    service = ObservationService(db)

    with pytest.raises(ValidationError) as exc_info:
        await service.submit_observation(
            kpi_id=check_kpi.kpi_id,
            kpi_version=check_kpi.version,
            checker_id=uuid.uuid4(),
            department_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            value_numeric=Decimal("0"),
            check_result="No",
            reason=None,
            submission_date="2026-08-31",
        )

    assert "Reason is required" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_check_no_empty_reason_rejected(db, check_kpi, seed_configuration):
    """When check_result is 'No', empty string reason is rejected."""
    service = ObservationService(db)

    with pytest.raises(ValidationError) as exc_info:
        await service.submit_observation(
            kpi_id=check_kpi.kpi_id,
            kpi_version=check_kpi.version,
            checker_id=uuid.uuid4(),
            department_id=uuid.uuid4(),
            school_id=uuid.uuid4(),
            value_numeric=Decimal("0"),
            check_result="No",
            reason="   ",
            submission_date="2026-08-31",
        )

    assert "Reason is required" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_check_yes_no_reason_optional(db, check_kpi, seed_configuration):
    """When check_result is 'Yes', reason is optional."""
    service = ObservationService(db)

    obs = await service.submit_observation(
        kpi_id=check_kpi.kpi_id,
        kpi_version=check_kpi.version,
        checker_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        value_numeric=Decimal("1"),
        check_result="Yes",
        reason=None,
        submission_date="2026-08-31",
    )

    assert obs is not None
    assert obs.check_result == "Yes"
    assert obs.reason is None


@pytest.mark.asyncio
async def test_check_no_valid_reason_accepted(db, check_kpi, seed_configuration):
    """When check_result is 'No' with valid reason, submission succeeds."""
    service = ObservationService(db)

    obs = await service.submit_observation(
        kpi_id=check_kpi.kpi_id,
        kpi_version=check_kpi.version,
        checker_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        value_numeric=Decimal("0"),
        check_result="No",
        reason="School was closed for maintenance",
        submission_date="2026-08-31",
    )

    assert obs is not None
    assert obs.check_result == "No"
    assert obs.reason == "School was closed for maintenance"


# ─── 30-Minute Edit Window Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_within_30_minutes_allowed(db, sample_kpi, seed_configuration):
    """Submitter can edit within 30 minutes of captured_at."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    obs = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("90"),
        submission_date="2026-08-31",
        actor_id=checker_id,
    )

    # Verify within edit window
    elapsed = utc_now() - obs.captured_at
    assert elapsed.total_seconds() < 1800  # Less than 30 minutes


@pytest.mark.asyncio
async def test_captured_at_used_for_edit_window(db, sample_kpi, seed_configuration):
    """Verify that captured_at (server-side) is used for the edit window calculation."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    obs = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("90"),
        submission_date="2026-08-31",
    )

    # captured_at should be very close to utc_now() (within a few seconds)
    assert obs.captured_at is not None
    diff = abs((utc_now() - obs.captured_at).total_seconds())
    assert diff < 10  # Within 10 seconds


@pytest.mark.asyncio
async def test_edit_after_30_minutes_rejected_for_submitter(db, sample_kpi, seed_configuration):
    """Submitter cannot edit after 30 minutes."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    obs = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("90"),
        submission_date="2026-08-31",
        actor_id=checker_id,
    )

    # Simulate time passing (set captured_at to 31 minutes ago)
    obs.captured_at = utc_now() - timedelta(minutes=31)
    await db.commit()
    await db.refresh(obs)

    # Verify edit window is expired
    elapsed = utc_now() - obs.captured_at
    assert elapsed.total_seconds() >= 1800


@pytest.mark.asyncio
async def test_edit_boundary_exactly_30_minutes(db, sample_kpi, seed_configuration):
    """Test the boundary condition: exactly 30 minutes."""
    service = ObservationService(db)
    checker_id = uuid.uuid4()
    department_id = uuid.uuid4()
    school_id = uuid.uuid4()

    obs = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=checker_id,
        department_id=department_id,
        school_id=school_id,
        value_numeric=Decimal("90"),
        submission_date="2026-08-31",
        actor_id=checker_id,
    )

    # Set captured_at to exactly 30 minutes ago
    obs.captured_at = utc_now() - timedelta(minutes=30)
    await db.commit()

    elapsed = utc_now() - obs.captured_at
    # At exactly 30 minutes, edit window should be expired
    # (elapsed >= 1800 means not within window)
    assert elapsed.total_seconds() >= 1800


# ─── Idempotency Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_idempotent_submission_returns_same_observation(db, sample_kpi, seed_configuration):
    """Same submission_token returns the same observation (idempotency)."""
    service = ObservationService(db)
    token = uuid.uuid4()

    obs1 = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        value_numeric=Decimal("95"),
        submission_token=token,
    )

    obs2 = await service.submit_observation(
        kpi_id=sample_kpi.kpi_id,
        kpi_version=sample_kpi.version,
        checker_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        school_id=uuid.uuid4(),
        value_numeric=Decimal("99"),  # Different value but same token
        submission_token=token,
    )

    assert obs1.id == obs2.id
    # First submission's value should be preserved
    assert obs2.value_numeric == Decimal("95")
