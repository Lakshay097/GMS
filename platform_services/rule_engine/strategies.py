"""
Worst-status-wins strategy — Phase 1 default per Architecture §5.2.
"""
from __future__ import annotations

from typing import Iterable

from platform_services.rule_engine.service import ComplianceStatusLevel, RuleStrategy

_STATUS_MAP = {
    "met": ComplianceStatusLevel.MET,
    "green": ComplianceStatusLevel.MET,
    "amber": ComplianceStatusLevel.AMBER,
    "not_met": ComplianceStatusLevel.NOT_MET,
    "red": ComplianceStatusLevel.NOT_MET,
    "n_a": ComplianceStatusLevel.N_A,
    "na": ComplianceStatusLevel.N_A,
}

_LEVEL_TO_STATUS = {
    ComplianceStatusLevel.MET: "met",
    ComplianceStatusLevel.AMBER: "amber",
    ComplianceStatusLevel.NOT_MET: "not_met",
    ComplianceStatusLevel.N_A: "n_a",
}


class WorstStatusWinsStrategy(RuleStrategy):
    """Phase 1 roll-up: worst (highest severity) status wins."""

    name = "worst_status_wins"

    def aggregate(self, statuses: Iterable[str]) -> str:
        worst = ComplianceStatusLevel.N_A
        for status in statuses:
            level = _STATUS_MAP.get(status.lower().replace("-", "_"), ComplianceStatusLevel.N_A)
            if level > worst:
                worst = level
        return _LEVEL_TO_STATUS[worst]
