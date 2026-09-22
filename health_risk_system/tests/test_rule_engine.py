"""
tests/test_rule_engine.py — Tests for individual rules and the rule engine.
"""

import pytest
from app.models.risk_models import ActivityState, RiskLevel
from app.rules import rule_definitions as R
from app.rules.rule_engine import RuleEngine
from tests.conftest import make_reading


# ---------------------------------------------------------------------------
# Heart Rate Rules
# ---------------------------------------------------------------------------

class TestHRRules:

    def test_normal_resting_hr_no_trigger(self):
        r = make_reading(heart_rate=72.0)
        rule = R.rule_hr_rest_elevated(r, ActivityState.REST)
        assert rule.triggered is False

    def test_elevated_resting_hr_triggers(self):
        r = make_reading(heart_rate=115.0)
        rule = R.rule_hr_rest_elevated(r, ActivityState.REST)
        assert rule.triggered is True
        assert rule.score_contribution > 0

    def test_elevated_hr_during_running_no_rest_trigger(self):
        r = make_reading(heart_rate=140.0)
        rule = R.rule_hr_rest_elevated(r, ActivityState.RUNNING)
        assert rule.triggered is False   # Not at rest

    def test_low_hr_triggers(self):
        r = make_reading(heart_rate=45.0)
        rule = R.rule_hr_low(r)
        assert rule.triggered is True

    def test_normal_hr_low_rule_no_trigger(self):
        r = make_reading(heart_rate=65.0)
        rule = R.rule_hr_low(r)
        assert rule.triggered is False

    def test_exercise_extreme_hr_triggers(self):
        r = make_reading(heart_rate=190.0)
        rule = R.rule_hr_exercise_extreme(r, ActivityState.RUNNING)
        assert rule.triggered is True

    def test_exercise_moderate_hr_no_extreme_trigger(self):
        r = make_reading(heart_rate=150.0)
        rule = R.rule_hr_exercise_extreme(r, ActivityState.RUNNING)
        assert rule.triggered is False


# ---------------------------------------------------------------------------
# SpO2 Rules
# ---------------------------------------------------------------------------

class TestSpO2Rules:

    def test_normal_spo2_no_trigger(self):
        r = make_reading(spo2=98.0)
        assert R.rule_spo2_critical(r).triggered is False
        assert R.rule_spo2_high_risk(r).triggered is False
        assert R.rule_spo2_monitor(r).triggered is False

    def test_critical_spo2_triggers(self):
        r = make_reading(spo2=88.0)
        assert R.rule_spo2_critical(r).triggered is True

    def test_high_risk_spo2_triggers(self):
        r = make_reading(spo2=91.5)
        assert R.rule_spo2_high_risk(r).triggered is True

    def test_monitor_band_spo2_triggers(self):
        # Monitor band is [high_risk=92.0, monitor=93.0) — use 92.5
        r = make_reading(spo2=92.5)
        assert R.rule_spo2_monitor(r).triggered is True

    def test_boundary_spo2_90(self):
        # 90 is the critical threshold — below it triggers critical
        r = make_reading(spo2=89.9)
        assert R.rule_spo2_critical(r).triggered is True

    def test_boundary_spo2_92(self):
        # 90 <= x < 92 → high risk
        r = make_reading(spo2=90.5)
        assert R.rule_spo2_high_risk(r).triggered is True


# ---------------------------------------------------------------------------
# Temperature Rules
# ---------------------------------------------------------------------------

class TestTemperatureRules:

    def test_normal_temp_no_trigger(self):
        r = make_reading(body_temperature=36.7)
        assert R.rule_temp_severe(r).triggered is False
        assert R.rule_temp_high(r).triggered is False
        assert R.rule_temp_fever_candidate(r).triggered is False
        assert R.rule_temp_elevated(r).triggered is False

    def test_elevated_temp_triggers(self):
        r = make_reading(body_temperature=37.5)
        assert R.rule_temp_elevated(r).triggered is True

    def test_fever_candidate_triggers(self):
        r = make_reading(body_temperature=38.2)
        assert R.rule_temp_fever_candidate(r).triggered is True

    def test_high_temp_triggers(self):
        r = make_reading(body_temperature=39.2)
        assert R.rule_temp_high(r).triggered is True

    def test_severe_temp_triggers(self):
        r = make_reading(body_temperature=40.5)
        assert R.rule_temp_severe(r).triggered is True

    def test_temp_boundary_fever_38(self):
        r = make_reading(body_temperature=38.0)
        assert R.rule_temp_fever_candidate(r).triggered is True


# ---------------------------------------------------------------------------
# Heat Stress Rule
# ---------------------------------------------------------------------------

class TestHeatStressRule:

    def test_full_heat_stress_triggers(self):
        r = make_reading(
            environment_temperature=38.0,
            humidity=82.0,
            heart_rate=108.0,
            body_temperature=38.0,
        )
        rule = R.rule_heat_stress(r, ActivityState.WALKING)
        assert rule.triggered is True

    def test_partial_heat_stress_no_trigger(self):
        """High temp but low humidity — should not trigger."""
        r = make_reading(
            environment_temperature=38.0,
            humidity=40.0,   # Below threshold
            heart_rate=108.0,
        )
        rule = R.rule_heat_stress(r, ActivityState.WALKING)
        assert rule.triggered is False

    def test_normal_environment_no_trigger(self):
        r = make_reading(
            environment_temperature=22.0,
            humidity=50.0,
            heart_rate=75.0,
        )
        rule = R.rule_heat_stress(r, ActivityState.REST)
        assert rule.triggered is False


# ---------------------------------------------------------------------------
# Fall Rule
# ---------------------------------------------------------------------------

class TestFallRule:

    def test_possible_fall_triggers(self):
        rule = R.rule_possible_fall(ActivityState.POSSIBLE_FALL)
        assert rule.triggered is True
        assert rule.score_contribution >= 40

    def test_no_fall_at_rest(self):
        rule = R.rule_possible_fall(ActivityState.REST)
        assert rule.triggered is False

    def test_no_fall_during_running(self):
        rule = R.rule_possible_fall(ActivityState.RUNNING)
        assert rule.triggered is False


# ---------------------------------------------------------------------------
# Exercise Normal Rule
# ---------------------------------------------------------------------------

class TestExerciseNormalRule:

    def test_running_with_normal_spo2_is_normal(self):
        r = make_reading(heart_rate=145.0, spo2=97.0, body_temperature=37.0)
        rule = R.rule_exercise_normal(r, ActivityState.RUNNING)
        assert rule.triggered is True

    def test_rest_with_high_hr_is_not_normal_exercise(self):
        r = make_reading(heart_rate=120.0, spo2=97.0)
        rule = R.rule_exercise_normal(r, ActivityState.REST)
        assert rule.triggered is False


# ---------------------------------------------------------------------------
# Rule Engine Integration Tests
# ---------------------------------------------------------------------------

class TestRuleEngineIntegration:

    def test_normal_reading_produces_normal_risk(self, rule_engine):
        r = make_reading()
        result = rule_engine.evaluate(r, ActivityState.REST, scenario_id=99)
        assert result.risk_score.risk_level in (RiskLevel.NORMAL, RiskLevel.LOW)
        assert result.risk_event is None

    def test_exercise_with_elevated_hr_is_not_risk(self, rule_engine):
        r = make_reading(heart_rate=145.0, spo2=97.0, body_temperature=37.0,
                         acceleration_x=1.2, acceleration_y=2.9, acceleration_z=1.3)
        result = rule_engine.evaluate(r, ActivityState.RUNNING, scenario_id=99)
        assert result.is_exercise_normal is True

    def test_persistence_increases_with_consecutive_abnormal(self, rule_engine):
        rule_engine.reset()
        for _ in range(3):
            r = make_reading(heart_rate=120.0)
            result = rule_engine.evaluate(r, ActivityState.REST, scenario_id=88)
        # After 3 abnormal readings, persistence should be 3
        assert result.persistence_count >= 3

    def test_multi_sensor_anomaly_scores_higher(self, rule_engine):
        rule_engine.reset()
        # Both SpO2 and HR bad
        r = make_reading(heart_rate=125.0, spo2=89.0)
        for _ in range(3):
            result = rule_engine.evaluate(r, ActivityState.REST, scenario_id=77)
        assert result.risk_score.score > 40   # Should be at least MODERATE

    def test_low_spo2_generates_risk_event_after_persistence(self, rule_engine):
        rule_engine.reset()
        r = make_reading(spo2=88.0, heart_rate=80.0)
        for _ in range(3):
            result = rule_engine.evaluate(r, ActivityState.REST, scenario_id=66)
        # After 3 consecutive critical SpO2 readings, AI should be triggered
        assert result.requires_ai is True or result.risk_event is not None
