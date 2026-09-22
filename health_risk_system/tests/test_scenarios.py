"""
tests/test_scenarios.py — Integration tests for the complete pipeline across all 8 mock scenarios.
"""

import pytest
from app.mock.scenarios import ALL_SCENARIOS
from app.pipeline import HealthRiskPipeline
from app.models.risk_models import RiskLevel


@pytest.fixture(scope="module")
def pipeline():
    return HealthRiskPipeline()


@pytest.fixture(scope="module")
def scenario_results(pipeline):
    results = {}
    for scenario in ALL_SCENARIOS:
        results[scenario.scenario_id] = pipeline.process_scenario(scenario)
    return results


class TestScenario1NormalRest:
    def test_risk_level_is_normal_or_low(self, scenario_results):
        r = scenario_results[1]
        assert r.final_risk_level in (RiskLevel.NORMAL, RiskLevel.LOW)

    def test_ai_not_called(self, scenario_results):
        r = scenario_results[1]
        assert r.ai_called is False or r.risk_event is None


class TestScenario2NormalExercise:
    def test_exercise_normal_detected(self, scenario_results):
        r = scenario_results[2]
        # At peak reading, exercise should normalise the HR elevation
        peak = r.peak_engine_result
        if peak:
            assert peak.is_exercise_normal or r.final_risk_level in (RiskLevel.NORMAL, RiskLevel.LOW)

    def test_ai_not_called_for_exercise(self, scenario_results):
        r = scenario_results[2]
        # AI should not be triggered purely due to exercise HR
        # (may be triggered if other anomalies exist — but not expected here)
        assert r.risk_event is None or not r.ai_called


class TestScenario3ElevatedRestingHR:
    def test_risk_detected(self, scenario_results):
        r = scenario_results[3]
        assert r.final_risk_level in (RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_hr_rule_triggered(self, scenario_results):
        r = scenario_results[3]
        peak = r.peak_engine_result
        triggered_ids = [rule.rule_id for rule in peak.rules if rule.triggered]
        assert "HR_REST_HIGH_001" in triggered_ids


class TestScenario4LowSpO2:
    def test_risk_detected(self, scenario_results):
        r = scenario_results[4]
        # Critical SpO2 (88%) → at minimum MODERATE with persistence; HIGH/CRITICAL with multi-sensor
        assert r.final_risk_level in (RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_spo2_rule_triggered(self, scenario_results):
        r = scenario_results[4]
        peak = r.peak_engine_result
        triggered_ids = [rule.rule_id for rule in peak.rules if rule.triggered]
        assert any("SPO2" in rid for rid in triggered_ids)


class TestScenario5HeatStress:
    def test_heat_stress_rule_triggered(self, scenario_results):
        r = scenario_results[5]
        peak = r.peak_engine_result
        triggered_ids = [rule.rule_id for rule in peak.rules if rule.triggered]
        assert "HEAT_STRESS_001" in triggered_ids

    def test_risk_level_elevated(self, scenario_results):
        r = scenario_results[5]
        assert r.final_risk_level in (RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL)


class TestScenario6IllnessPattern:
    def test_illness_pattern_rule_triggered(self, scenario_results):
        r = scenario_results[6]
        peak = r.peak_engine_result
        triggered_ids = [rule.rule_id for rule in peak.rules if rule.triggered]
        assert "ILLNESS_PATTERN_001" in triggered_ids or "TEMP_FEVER_001" in triggered_ids

    def test_risk_level_elevated(self, scenario_results):
        r = scenario_results[6]
        assert r.final_risk_level not in (RiskLevel.NORMAL,)


class TestScenario7Fall:
    def test_fall_rule_triggered(self, scenario_results):
        r = scenario_results[7]
        peak = r.peak_engine_result
        triggered_ids = [rule.rule_id for rule in peak.rules if rule.triggered]
        assert "FALL_POSSIBLE_001" in triggered_ids

    def test_risk_level_high_or_critical(self, scenario_results):
        r = scenario_results[7]
        assert r.final_risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


class TestScenario8Altitude:
    def test_altitude_context_noted(self, scenario_results):
        r = scenario_results[8]
        peak = r.peak_engine_result
        if peak and peak.risk_event:
            assert peak.risk_event.high_altitude is True

    def test_altitude_spo2_rule_triggered(self, scenario_results):
        r = scenario_results[8]
        peak = r.peak_engine_result
        triggered_ids = [rule.rule_id for rule in peak.rules if rule.triggered]
        # At 3200m with declining SpO2 — altitude SpO2 rule should trigger
        assert "ALTITUDE_SPO2_001" in triggered_ids or "SPO2_MONITOR_001" in triggered_ids
