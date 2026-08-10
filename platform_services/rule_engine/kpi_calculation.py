"""
KPI calculation strategies — PRS §23.14-15, R-35/R-36.
Threshold comparison is the only Phase 1 formula type.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from shared.platform_models import AutoResult, KpiComparator, RagStatus, VALID_COMPARATORS


class KpiCalculationError(ValueError):
    """Invalid KPI calculation inputs."""


def normalize_comparator(comparator: str) -> str:
    """Map unicode comparators from seed data to canonical ASCII forms."""
    mapping = {
        "≥": ">=",
        "≤": "<=",
        "=>": ">=",
        "=<": "<=",
    }
    normalized = mapping.get(comparator.strip(), comparator.strip())
    if normalized not in VALID_COMPARATORS:
        raise KpiCalculationError(f"Unsupported comparator: {comparator}")
    return normalized


def evaluate_comparator(value: Decimal, target: Decimal, comparator: str) -> bool:
    """Evaluate comparator at full precision per FR-176 (R-17/PRS §52)."""
    comparator = normalize_comparator(comparator)
    if comparator == ">=":
        return value >= target
    if comparator == "<=":
        return value <= target
    if comparator == "=":
        return value == target
    if comparator == "<":
        return value < target
    if comparator == ">":
        return value > target
    raise KpiCalculationError(f"Unsupported comparator: {comparator}")


def round_for_display(value: Decimal, decimal_places: int, rounding_mode: str) -> Decimal:
    """Display rounding per PRS §23.14 — round-half-up by default (R-36)."""
    if rounding_mode != "round_half_up":
        raise KpiCalculationError(f"Unsupported rounding mode: {rounding_mode}")
    quantizer = Decimal("1").scaleb(-decimal_places)
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)


def compute_auto_result(value: Decimal, target: Decimal, comparator: str) -> AutoResult:
    """Threshold comparison formula type — PRS §23.14."""
    if evaluate_comparator(value, target, comparator):
        return AutoResult.MET
    return AutoResult.NOT_MET


def _within_amber_band(value: Decimal, target: Decimal, amber_band_pct: Decimal) -> bool:
    """True when value is within tolerance of target but does not strictly meet comparator."""
    if target == 0:
        return False
    delta_pct = abs((value - target) / target) * Decimal("100")
    return delta_pct <= amber_band_pct


def compute_rag_status(
    *,
    value: Optional[Decimal],
    target: Decimal,
    comparator: str,
    amber_band_pct: Decimal,
    is_late: bool = False,
    missing_data_behavior: str = "not_submitted",
) -> RagStatus:
    """
    Compute RAG status per PRS §23.14 / FR-177 (R-37).
    Missing data behavior resolved from Configuration Engine (R-36).
    """
    if value is None:
        if missing_data_behavior == "not_submitted":
            return RagStatus.NOT_SUBMITTED
        raise KpiCalculationError(f"Unsupported missing-data behavior: {missing_data_behavior}")

    meets_comparator = evaluate_comparator(value, target, comparator)

    if meets_comparator and not is_late:
        return RagStatus.GREEN

    if meets_comparator and is_late:
        return RagStatus.AMBER

    if not meets_comparator and _within_amber_band(value, target, amber_band_pct):
        return RagStatus.AMBER

    return RagStatus.RED


class ThresholdComparisonStrategy:
    """Phase 1 KPI formula strategy — PRS §23.14 threshold comparison."""

    name = "threshold_comparison"

    def compute(
        self,
        *,
        value: Optional[Decimal],
        target: Decimal,
        comparator: str,
        amber_band_pct: Decimal,
        is_late: bool = False,
        decimal_places: int = 2,
        rounding_mode: str = "round_half_up",
        missing_data_behavior: str = "not_submitted",
    ) -> dict:
        auto_result = None
        display_value = None
        if value is not None:
            auto_result = compute_auto_result(value, target, comparator)
            display_value = round_for_display(value, decimal_places, rounding_mode)

        rag_status = compute_rag_status(
            value=value,
            target=target,
            comparator=comparator,
            amber_band_pct=amber_band_pct,
            is_late=is_late,
            missing_data_behavior=missing_data_behavior,
        )

        return {
            "auto_result": auto_result.value if auto_result else None,
            "rag_status": rag_status.value,
            "display_value": str(display_value) if display_value is not None else None,
        }
