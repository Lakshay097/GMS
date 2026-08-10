"""
Rule Engine pluggable strategies — Architecture §5.2.
R-36: missing-data handling resolved through strategies, not hardcoded per module.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from enum import IntEnum
from typing import Iterable, Optional

from platform_services.rule_engine.kpi_calculation import ThresholdComparisonStrategy


class ComplianceStatusLevel(IntEnum):
    """Ordered compliance levels for worst-status-wins roll-up."""

    MET = 1
    AMBER = 2
    NOT_MET = 3
    N_A = 0  # Neutral — does not worsen aggregate


class RuleStrategy(ABC):
    """Pluggable aggregation strategy interface (Phase 2 adds weighted-scoring)."""

    name: str

    @abstractmethod
    def aggregate(self, statuses: Iterable[str]) -> str:
        """Aggregate a collection of status strings into a single roll-up status."""
        raise NotImplementedError


class RuleEngine:
    """
    Resolves aggregation and KPI calculation via registered strategies.
    Callers depend on RuleEngine, not concrete strategy implementations (R-35).
    """

    def __init__(self):
        self._strategies: dict[str, RuleStrategy] = {}
        self._kpi_strategies: dict[str, ThresholdComparisonStrategy] = {
            ThresholdComparisonStrategy.name: ThresholdComparisonStrategy(),
        }

    def register_strategy(self, strategy: RuleStrategy) -> None:
        self._strategies[strategy.name] = strategy

    def get_strategy(self, name: str) -> RuleStrategy:
        strategy = self._strategies.get(name)
        if strategy is None:
            raise KeyError(f"No rule strategy registered: {name}")
        return strategy

    def aggregate(self, strategy_name: str, statuses: Iterable[str]) -> str:
        return self.get_strategy(strategy_name).aggregate(statuses)

    def compute_kpi_result(
        self,
        *,
        formula_type: str,
        value: Optional[Decimal],
        target: Decimal,
        comparator: str,
        amber_band_pct: Decimal,
        is_late: bool = False,
        decimal_places: int = 2,
        rounding_mode: str = "round_half_up",
        missing_data_behavior: str = "not_submitted",
    ) -> dict:
        """Compute auto-result and RAG via the configured formula strategy (R-35)."""
        strategy = self._kpi_strategies.get(formula_type)
        if strategy is None:
            raise KeyError(f"No KPI formula strategy registered: {formula_type}")
        return strategy.compute(
            value=value,
            target=target,
            comparator=comparator,
            amber_band_pct=amber_band_pct,
            is_late=is_late,
            decimal_places=decimal_places,
            rounding_mode=rounding_mode,
            missing_data_behavior=missing_data_behavior,
        )
