"""Unit tests for Rule Engine — Architecture §5.2, R-36."""
import pytest

from platform_services.rule_engine.service import RuleEngine
from platform_services.rule_engine.strategies import WorstStatusWinsStrategy


@pytest.fixture
def rule_engine():
    engine = RuleEngine()
    engine.register_strategy(WorstStatusWinsStrategy())
    return engine


def test_worst_status_wins_met_and_amber(rule_engine):
    result = rule_engine.aggregate("worst_status_wins", ["met", "amber", "met"])
    assert result == "amber"


def test_worst_status_wins_not_met_wins(rule_engine):
    result = rule_engine.aggregate("worst_status_wins", ["met", "not_met", "amber"])
    assert result == "not_met"


def test_worst_status_wins_all_met(rule_engine):
    result = rule_engine.aggregate("worst_status_wins", ["met", "met"])
    assert result == "met"


def test_worst_status_wins_na_does_not_worsen(rule_engine):
    result = rule_engine.aggregate("worst_status_wins", ["n_a", "met"])
    assert result == "met"
