"""
Unit tests for KRA/KPI Library — PRS §22-23.
Covers R-17 (versioning), R-21 (deprecated block), R-37 (config-driven RAG).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from platform_services.configuration_engine.constants import ConfigKey
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.master_data_service.service import MasterDataService
from platform_services.rule_engine.service import RuleEngine
from platform_services.rule_engine.strategies import WorstStatusWinsStrategy
from shared.errors import BusinessRuleError
from shared.platform_models import KRA, KPI, KraStatus, KpiStatus, Observation
from shared.datetime_utils import utc_now
from modules.kra_kpi_library.services.kpi_service import KpiService


@pytest.fixture
async def frequency_master_data(db):
    master_data = MasterDataService(db)
    for code, label in [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annual", "Annual"),
    ]:
        await master_data.create_entry("frequency", code, label)
    return master_data


@pytest.fixture
async def kra(db):
    kra = KRA(id=uuid.uuid4(), name="Safety", status=KraStatus.ACTIVE.value, created_at=utc_now())
    db.add(kra)
    await db.commit()
    return kra


@pytest.fixture
def rule_engine():
    engine = RuleEngine()
    engine.register_strategy(WorstStatusWinsStrategy())
    return engine


@pytest.fixture
async def kpi_service(db, frequency_master_data, rule_engine):
    config = ConfigurationEngine(db)
    await config.seed_defaults()
    return KpiService(db, config_engine=config, rule_engine=rule_engine, master_data=frequency_master_data)


@pytest.mark.asyncio
async def test_R17_kpi_edit_creates_new_version_prior_immutable(kpi_service, kra, db, user, school, department):
    """R-17/FR-049/FR-050: Target edit creates new version; prior becomes immutable once referenced."""
    kpi = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="Safety Compliance",
        target_value=Decimal("100"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
        category_code="safety",
    )
    assert kpi.version == 1

    await kpi_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=1,
        checker_id=user.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("100"),
    )

    prior = await kpi_service.get_kpi_version(kpi.kpi_id, 1)
    assert prior.is_immutable is True
    assert prior.target_value == Decimal("100")

    updated = await kpi_service.update_kpi(kpi.kpi_id, target_value=Decimal("95"))
    assert updated.version == 2
    assert updated.target_value == Decimal("95")
    assert updated.status == KpiStatus.ACTIVE.value

    prior_after = await kpi_service.get_kpi_version(kpi.kpi_id, 1)
    assert prior_after.target_value == Decimal("100")
    assert prior_after.is_immutable is True
    assert prior_after.status == KpiStatus.DEPRECATED.value


@pytest.mark.asyncio
async def test_R21_submission_against_deprecated_kpi_blocked(kpi_service, kra, user, school, department):
    """R-21/PRS §52: Deprecated KPI version submissions are rejected with structured error."""
    kpi = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="Attendance Rate",
        target_value=Decimal("95"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
    )

    deprecated = await kpi_service.deprecate_kpi(kpi.kpi_id)

    with pytest.raises(BusinessRuleError) as exc_info:
        await kpi_service.submit_observation(
            kpi_id=deprecated.kpi_id,
            kpi_version=deprecated.version,
            checker_id=user.id,
            department_id=department.id,
            school_id=school.id,
            value_numeric=Decimal("96"),
        )

    error = exc_info.value
    assert error.code == "BUSINESS_RULE_VIOLATION"
    assert "deprecated" in error.message.lower()
    assert error.details["kpi_version"] == deprecated.version


@pytest.mark.asyncio
async def test_R37_rag_uses_configurable_amber_tolerance_band(kpi_service, kra, school, db):
    """R-37/D6: RAG uses config values; changing config changes output without code deploy."""
    # Use the same config_engine instance as kpi_service to avoid stale cache
    config = kpi_service.config_engine
    await config.seed_defaults()

    kpi = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="Budget Variance",
        target_value=Decimal("100"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="monthly",
    )

    result_default = await kpi_service.compute_kpi_result(
        kpi=kpi,
        value_numeric=Decimal("97"),
        school_id=school.id,
    )
    assert result_default["rag_status"] == "amber"

    await config.set_global(ConfigKey.KPI_AMBER_TOLERANCE_BAND, Decimal("1.0"))
    result_strict = await kpi_service.compute_kpi_result(
        kpi=kpi,
        value_numeric=Decimal("97"),
        school_id=school.id,
    )
    assert result_strict["rag_status"] == "red"

    await config.set_global(ConfigKey.KPI_AMBER_TOLERANCE_BAND, Decimal("10.0"))
    result_relaxed = await kpi_service.compute_kpi_result(
        kpi=kpi,
        value_numeric=Decimal("97"),
        school_id=school.id,
    )
    assert result_relaxed["rag_status"] == "amber"

    await config.set_category_amber_tolerance_band("finance", Decimal("0.5"))
    kpi_with_category = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="Finance KPI",
        target_value=Decimal("100"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="monthly",
        category_code="finance",
    )
    result_category = await kpi_service.compute_kpi_result(
        kpi=kpi_with_category,
        value_numeric=Decimal("99.0"),
        school_id=school.id,
    )
    assert result_category["rag_status"] == "red"


@pytest.mark.asyncio
async def test_R35_kpi_result_uses_rule_engine_formula(kpi_service, kra, school):
    """R-35: Auto-result computed via Rule Engine threshold comparison, not inline math."""
    kpi = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="On-time Delivery",
        target_value=Decimal("90"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="weekly",
    )

    result = await kpi_service.compute_kpi_result(
        kpi=kpi,
        value_numeric=Decimal("92"),
        school_id=school.id,
    )
    assert result["auto_result"] == "met"
    assert result["rag_status"] == "green"


@pytest.mark.asyncio
async def test_validation_kpi_invalid_comparator_rejected(kpi_service, kra):
    from shared.errors import ValidationError
    from platform_services.rule_engine.kpi_calculation import KpiCalculationError

    with pytest.raises((ValidationError, KpiCalculationError)):
        await kpi_service.create_kpi(
            kra_id=kra.id,
            title="Bad Comparator",
            target_value=Decimal("100"),
            comparator="≈",
            unit_of_measure="percent",
            frequency_code="daily",
        )


@pytest.mark.asyncio
async def test_import_requires_sme_confirmation(kpi_service):
    """SME column review gate stays enforced — D1/D3 resolution is not content sign-off."""
    with pytest.raises(BusinessRuleError, match="confirm_sme_review"):
        await kpi_service.import_from_seed_file(confirm_sme_review=False)


def test_held_role_markers_cleared_for_q3():
    """Q3/D1: Marketing Manager and Telecaller are no longer held out of import."""
    from modules.kra_kpi_library.services.kpi_service import HELD_ROLE_MARKERS

    assert HELD_ROLE_MARKERS == ()


def test_parse_seed_includes_marketing_telecaller_and_core():
    """Q3/Q5: parser yields Marketing, Telecaller, and Core KRA Set rows (Role|KRA|KPI)."""
    from modules.kra_kpi_library.services.kpi_service import CAPTURE_TYPE_ALIASES, KpiService

    sample = """
| Role | KRA | KPI | Unit | Comparator | Target | Frequency | Sensitive? | Capture Type | Event Time Point(s) | Non-Working-Day Policy | Asset/Location Scoped? | Evidence Required (Photo/Document)? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Marketing Manager | Admissions Target Achievement | Meet admissions targets | % | ≥ | 95% of session target achieved | monthly | no | Value Reading | n/a | Skip | none | No |
| Telecaller | Outbound Lead Generation | Generate leads | % | ≥ | 100% | daily | no | Value Reading | n/a | Skip | none | No |
| Core (no role manual) | Safety | Fire/emergency drills conducted as per statutory norms | % | ≥ | 95% | annual (twice yearly) | no | Value Reading | n/a | Skip | none | No |
| Core (no role manual) | Facilities | Cleanliness audit compliance | % | ≥ | 90% | monthly | yes | Value Reading | n/a | Skip | Location | Yes |
"""
    rows = KpiService._parse_seed_tables(sample)
    assert len(rows) == 4
    roles = {r["role"] for r in rows}
    assert "Marketing Manager" in roles
    assert "Telecaller" in roles
    assert any(r["source"] == "core" for r in rows)
    core = next(r for r in rows if r["source"] == "core" and r["kra"] == "Safety")
    assert core["kpi"].startswith("Fire/emergency")
    assert core["kra"] == "Safety"
    facilities = next(r for r in rows if r["kra"] == "Facilities")
    assert facilities["evidence_required"].lower() == "yes"
    marketing = next(r for r in rows if "Marketing" in r["role"])
    assert marketing["kra"] == "Admissions Target Achievement"
    assert marketing["source"] == "role_manual"
    assert CAPTURE_TYPE_ALIASES["value reading"] == "value_reading"


def test_normalize_frequency_strips_parenthetical():
    from modules.kra_kpi_library.services.kpi_service import KpiService

    assert KpiService._normalize_frequency("annual (twice yearly)") == "annual"



@pytest.mark.asyncio
async def test_historical_report_resolves_kpi_version(kpi_service, kra, user, school, department, db):
    """FR-051: Historical data resolves against the KPI version active at submission time."""
    kpi = await kpi_service.create_kpi(
        kra_id=kra.id,
        title="Historical KPI",
        target_value=Decimal("100"),
        comparator=">=",
        unit_of_measure="percent",
        frequency_code="daily",
    )

    observation = await kpi_service.submit_observation(
        kpi_id=kpi.kpi_id,
        kpi_version=1,
        checker_id=user.id,
        department_id=department.id,
        school_id=school.id,
        value_numeric=Decimal("100"),
    )

    await kpi_service.update_kpi(kpi.kpi_id, target_value=Decimal("80"))

    stored = await db.get(Observation, observation.id)
    assert stored.kpi_version == 1

    historical_kpi = await kpi_service.get_kpi_version(stored.kpi_id, stored.kpi_version)
    assert historical_kpi.target_value == Decimal("100")
