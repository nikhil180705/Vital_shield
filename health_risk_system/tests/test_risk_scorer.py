"""
tests/test_risk_scorer.py — Tests for the deterministic risk scorer.
"""

import pytest
from app.models.risk_models import RiskLevel, Severity, TriggeredRule
from app.rules.risk_scorer import RiskScorer, score_to_level


def make_rule(rule_id: str, triggered: bool, score: int) -> TriggeredRule:
    return TriggeredRule(
        rule_id=rule_id,
        rule_name="Test Rule",
        description="Test",
        severity=Severity.MEDIUM,
        triggered=triggered,
        reason="Test reason",
        evidence={},
        score_contribution=score if triggered else 0,
    )


class TestRiskScorer:

    def test_no_triggered_rules_yields_zero(self):
        scorer = RiskScorer()
        rules = [make_rule("R1", False, 10), make_rule("R2", False, 20)]
        result = scorer.compute(rules, persistence_count=1)
        assert result.score == 0
        assert result.risk_level == RiskLevel.NORMAL

    def test_single_rule_scores_correctly(self):
        scorer = RiskScorer()
        rules = [make_rule("HR_R1", True, 25)]
        result = scorer.compute(rules, persistence_count=1)
        assert result.score == 25
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MODERATE)

    def test_multi_sensor_bonus_applied(self):
        scorer = RiskScorer()
        # Two different categories: HR_ and SPO2_
        rules = [
            make_rule("HR_REST_001", True, 15),
            make_rule("SPO2_HIGH_001", True, 20),
        ]
        no_bonus_total = 15 + 20
        result = scorer.compute(rules, persistence_count=1)
        assert result.score > no_bonus_total   # bonus added

    def test_persistence_multiplier_increases_score(self):
        scorer = RiskScorer()
        rules = [make_rule("HR_001", True, 20)]
        r1 = scorer.compute(rules, persistence_count=1)
        r5 = scorer.compute(rules, persistence_count=5)
        assert r5.score >= r1.score

    def test_score_capped_at_100(self):
        scorer = RiskScorer()
        rules = [make_rule(f"CAT{i}_RULE", True, 40) for i in range(5)]
        result = scorer.compute(rules, persistence_count=5)
        assert result.score <= 100

    def test_contributing_rules_listed(self):
        scorer = RiskScorer()
        rules = [
            make_rule("HR_001", True, 20),
            make_rule("TEMP_001", False, 10),
        ]
        result = scorer.compute(rules, persistence_count=1)
        assert "HR_001" in result.contributing_rules
        assert "TEMP_001" not in result.contributing_rules


class TestScoreToLevel:

    def test_zero_is_normal(self):
        assert score_to_level(0) == RiskLevel.NORMAL

    def test_20_is_normal(self):
        assert score_to_level(20) == RiskLevel.NORMAL

    def test_21_is_low(self):
        assert score_to_level(21) == RiskLevel.LOW

    def test_41_is_moderate(self):
        assert score_to_level(41) == RiskLevel.MODERATE

    def test_61_is_high(self):
        assert score_to_level(61) == RiskLevel.HIGH

    def test_81_is_critical(self):
        assert score_to_level(81) == RiskLevel.CRITICAL

    def test_100_is_critical(self):
        assert score_to_level(100) == RiskLevel.CRITICAL
