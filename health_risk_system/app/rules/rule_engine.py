"""
rule_engine.py — The deterministic rule engine.

This is the AUTHORITY for:
  - threshold detection
  - abnormality detection
  - risk severity
  - rule triggering
  - persistence checks
  - multi-sensor conditions
  - activity/context interpretation

The LLM is NEVER consulted to determine if a sensor reading is dangerous.
The LLM is called ONLY AFTER the rule engine has identified a risk event.

Architecture:
    SensorReading + ActivityState
          ↓
    [run all rules]
          ↓
    TriggeredRule list
          ↓
    Persistence check
          ↓
    RiskScore
          ↓
    Decision: NORMAL or RISK EVENT
"""

from __future__ import annotations

import logging
import uuid
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

from app.config import BASELINE, PERSISTENCE, THRESHOLDS
from app.models.risk_models import (
    ActivityState,
    FallDetectionState,
    RiskEvent,
    RiskLevel,
    RiskScore,
    TriggeredRule,
)
from app.models.sensor_models import SensorReading
from app.rules import rule_definitions as R
from app.rules.risk_scorer import RiskScorer

logger = logging.getLogger(__name__)

# Risk levels that require AI analysis
AI_REQUIRED_LEVELS = {RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.CRITICAL}

# POSSIBLE_FALL always requires AI regardless of score
FALL_ALWAYS_AI = True


class RuleEngineResult:
    """Result from the rule engine for a single reading."""

    def __init__(
        self,
        rules: List[TriggeredRule],
        risk_score: RiskScore,
        activity: ActivityState,
        reading: SensorReading,
        is_exercise_normal: bool,
        requires_ai: bool,
        risk_event: Optional[RiskEvent],
        persistence_count: int,
    ) -> None:
        self.rules = rules
        self.risk_score = risk_score
        self.activity = activity
        self.reading = reading
        self.is_exercise_normal = is_exercise_normal
        self.requires_ai = requires_ai
        self.risk_event = risk_event
        self.persistence_count = persistence_count


class RuleEngine:
    """
    Stateful rule engine maintaining persistence windows per scenario.
    """

    def __init__(self) -> None:
        self._scorer = RiskScorer()
        # Rolling window of recent risk scores (for persistence)
        self._recent_scores: Deque[int] = deque(maxlen=10)
        self._abnormal_count: int = 0
        self._scenario_id: Optional[int] = None

    def reset(self) -> None:
        """Reset state between scenarios."""
        self._recent_scores.clear()
        self._abnormal_count = 0

    def set_scenario(self, scenario_id: int) -> None:
        if self._scenario_id != scenario_id:
            self.reset()
            self._scenario_id = scenario_id

    def evaluate(
        self,
        reading: SensorReading,
        activity: ActivityState,
        scenario_id: Optional[int] = None,
        scenario_name: Optional[str] = None,
    ) -> RuleEngineResult:
        """
        Evaluate all rules for a single sensor reading.
        Returns a RuleEngineResult with scoring and event data.
        """
        if scenario_id is not None:
            self.set_scenario(scenario_id)

        # ----------------------------------------------------------------
        # Run all individual rules
        # ----------------------------------------------------------------
        rules: List[TriggeredRule] = [
            # Heart rate
            R.rule_hr_rest_elevated(reading, activity),
            R.rule_hr_low(reading),
            R.rule_hr_exercise_extreme(reading, activity),
            # SpO2
            R.rule_spo2_critical(reading),
            R.rule_spo2_high_risk(reading),
            R.rule_spo2_monitor(reading),
            # Body temperature
            R.rule_temp_severe(reading),
            R.rule_temp_high(reading),
            R.rule_temp_fever_candidate(reading),
            R.rule_temp_elevated(reading),
            # Environmental / Heat
            R.rule_heat_stress(reading, activity),
            # Altitude
            R.rule_high_altitude_spo2_concern(reading),
            R.rule_rapid_altitude_change(reading),
            # Multi-sensor composite
            R.rule_spo2_hr_rest_combined(reading, activity),
            R.rule_illness_pattern(reading, activity),
            # Fall
            R.rule_possible_fall(activity),
            # Exercise normalisation
            R.rule_exercise_normal(reading, activity),
            # Baseline
            R.rule_baseline_deviation_hr(reading),
        ]

        # ----------------------------------------------------------------
        # Check if exercise pattern normalises the event
        # ----------------------------------------------------------------
        exercise_normal_rule = next(
            (r for r in rules if r.rule_id == "EXERCISE_NORMAL_001" and r.triggered), None
        )
        is_exercise_normal = exercise_normal_rule is not None

        # ----------------------------------------------------------------
        # Persistence tracking
        # ----------------------------------------------------------------
        triggered_rules = [r for r in rules if r.triggered and r.rule_id != "EXERCISE_NORMAL_001"]

        if triggered_rules and not is_exercise_normal:
            self._abnormal_count = min(self._abnormal_count + 1, 10)
        else:
            # Gradual decay rather than instant reset
            self._abnormal_count = max(0, self._abnormal_count - 1)

        persistence_count = self._abnormal_count

        # ----------------------------------------------------------------
        # Score computation
        # ----------------------------------------------------------------
        # If exercise is normal, suppress scoring of HR rules
        scoring_rules = rules
        if is_exercise_normal:
            # Zero out HR rules when exercise explains them
            scoring_rules = [
                TriggeredRule(
                    **{**r.model_dump(), "triggered": False, "score_contribution": 0}
                )
                if r.rule_id in ("HR_REST_HIGH_001", "BASELINE_HR_DEV_001")
                else r
                for r in rules
            ]

        risk_score = self._scorer.compute(scoring_rules, persistence_count)

        # Override: exercise normal with no other issues → NORMAL
        if is_exercise_normal and risk_score.score <= 20:
            risk_score.score = max(0, risk_score.score)
            risk_score.risk_level = RiskLevel.NORMAL

        # ----------------------------------------------------------------
        # Altitude context
        # ----------------------------------------------------------------
        high_altitude = (
            reading.altitude is not None
            and reading.altitude >= THRESHOLDS["altitude"]["high"]
        )
        altitude_note = None
        if high_altitude:
            altitude_note = (
                f"User is at altitude {reading.altitude} m — "
                "SpO2 values should be interpreted in altitude context."
            )

        # ----------------------------------------------------------------
        # Decision: does this reading require AI analysis?
        # ----------------------------------------------------------------
        fall_triggered = any(
            r.rule_id == "FALL_POSSIBLE_001" and r.triggered for r in rules
        )
        requires_ai = (
            (risk_score.risk_level in AI_REQUIRED_LEVELS or (fall_triggered and FALL_ALWAYS_AI))
            and not is_exercise_normal
            and persistence_count >= PERSISTENCE["risk_threshold"]
        )

        # ----------------------------------------------------------------
        # Build RiskEvent if AI is required
        # ----------------------------------------------------------------
        risk_event: Optional[RiskEvent] = None
        if requires_ai:
            risk_event = self._build_event(
                reading=reading,
                activity=activity,
                rules=rules,
                risk_score=risk_score,
                persistence_count=persistence_count,
                scenario_id=scenario_id,
                scenario_name=scenario_name,
                high_altitude=high_altitude,
                altitude_note=altitude_note,
            )
            logger.info(
                "RISK EVENT created: id=%s score=%d level=%s",
                risk_event.event_id,
                risk_event.risk_score,
                risk_event.risk_level,
            )

        return RuleEngineResult(
            rules=rules,
            risk_score=risk_score,
            activity=activity,
            reading=reading,
            is_exercise_normal=is_exercise_normal,
            requires_ai=requires_ai,
            risk_event=risk_event,
            persistence_count=persistence_count,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_event(
        self,
        reading: SensorReading,
        activity: ActivityState,
        rules: List[TriggeredRule],
        risk_score: RiskScore,
        persistence_count: int,
        scenario_id: Optional[int],
        scenario_name: Optional[str],
        high_altitude: bool,
        altitude_note: Optional[str],
    ) -> RiskEvent:
        sensor_snapshot = {
            "heart_rate": reading.heart_rate,
            "spo2": reading.spo2,
            "body_temperature": reading.body_temperature,
            "environment_temperature": reading.environment_temperature,
            "humidity": reading.humidity,
            "altitude": reading.altitude,
            "atmospheric_pressure": reading.atmospheric_pressure,
            "acceleration_magnitude": reading.acceleration_magnitude,
            "activity_state": activity,
        }
        env_context = {
            "altitude": reading.altitude,
            "pressure": reading.atmospheric_pressure,
            "env_temperature": reading.environment_temperature,
            "humidity": reading.humidity,
            "altitude_change": reading.altitude_change,
            "pressure_change": reading.pressure_change,
            "high_altitude": high_altitude,
        }
        return RiskEvent(
            event_id=str(uuid.uuid4())[:8],
            timestamp=reading.timestamp,
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            risk_score=risk_score.score,
            risk_level=risk_score.risk_level,
            activity_state=str(activity),
            triggered_rules=[r for r in rules if r.triggered],
            sensor_snapshot=sensor_snapshot,
            baseline=BASELINE,
            environment_context=env_context,
            persistence_count=persistence_count,
            high_altitude=high_altitude,
            altitude_context_note=altitude_note,
        )
