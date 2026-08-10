"""Unit tests for KPI calculation strategies — PRS §23.14."""
from decimal import Decimal

import pytest

from platform_services.rule_engine.kpi_calculation import (
    compute_auto_result,
    compute_rag_status,
    evaluate_comparator,
    round_for_display,
)
from shared.platform_models import AutoResult, RagStatus


def test_evaluate_comparator_full_precision():
    """FR-176: Comparator uses full precision, not rounded display value."""
    assert evaluate_comparator(Decimal("99.995"), Decimal("100"), ">=") is False
    assert evaluate_comparator(Decimal("100.004"), Decimal("100"), ">=") is True


def test_round_for_display_round_half_up():
    value = round_for_display(Decimal("1.235"), 2, "round_half_up")
    assert value == Decimal("1.24")


def test_compute_auto_result_threshold_comparison():
    assert compute_auto_result(Decimal("95"), Decimal("90"), ">=") == AutoResult.MET
    assert compute_auto_result(Decimal("85"), Decimal("90"), ">=") == AutoResult.NOT_MET


def test_compute_rag_missing_data_not_submitted():
    result = compute_rag_status(
        value=None,
        target=Decimal("100"),
        comparator=">=",
        amber_band_pct=Decimal("5"),
        missing_data_behavior="not_submitted",
    )
    assert result == RagStatus.NOT_SUBMITTED
