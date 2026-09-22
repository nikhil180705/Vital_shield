"""
activity_detector.py — Deterministic activity / context classifier.

Uses accelerometer magnitude to classify the user's current state.

Possible states (ActivityState enum):
    REST
    WALKING
    RUNNING
    HIGH_ACTIVITY
    POSSIBLE_FALL
    UNKNOWN

IMPORTANT: This is a prototype classifier, NOT a clinically validated
activity recognition system. It serves only to distinguish context
(e.g. HR=130 during running vs. HR=130 at rest) for the rule engine.

Fall detection uses a simplified state machine:
    sudden high acceleration → impact candidate
    followed by near-zero movement → POSSIBLE_FALL

We emit POSSIBLE_FALL, never CONFIRMED_FALL.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.models.sensor_models import SensorReading
from app.models.risk_models import ActivityState, FallDetectionState
from app.config import THRESHOLDS

logger = logging.getLogger(__name__)

ACC = THRESHOLDS["acceleration"]

# Consecutive low-motion readings after impact required for POSSIBLE_FALL
FALL_POST_IMPACT_READINGS_REQUIRED = 2


class ActivityDetector:
    """
    Stateful activity classifier that also performs fall detection.

    Maintains a FallDetectionState between calls so the fall pattern
    (impact → immobility) can be detected across sequential readings.
    """

    def __init__(self) -> None:
        self._fall_state = FallDetectionState()

    def classify(self, reading: SensorReading) -> ActivityState:
        """
        Classify the activity state for a single reading.

        Mutates internal fall-detection state.
        """
        mag = reading.acceleration_magnitude
        if mag is None:
            return ActivityState.UNKNOWN

        # ----------------------------------------------------------------
        # Fall detection state machine (checked FIRST)
        # ----------------------------------------------------------------
        fall_state = self._fall_state

        if not fall_state.impact_detected:
            # Watch for impact spike
            if mag >= ACC["fall_impact_min"]:
                fall_state.impact_detected = True
                fall_state.impact_magnitude = mag
                fall_state.pre_impact_magnitude = mag
                fall_state.post_impact_readings = 0
                logger.debug(
                    "Fall state machine: impact candidate detected, magnitude=%.2f", mag
                )
                return ActivityState.HIGH_ACTIVITY  # Still classifying as active at impact moment
        else:
            # Impact already detected — watch for post-impact immobility
            if mag <= ACC["post_fall_max"]:
                fall_state.post_impact_readings += 1
                logger.debug(
                    "Fall state machine: post-impact immobility count=%d",
                    fall_state.post_impact_readings,
                )
                if fall_state.post_impact_readings >= FALL_POST_IMPACT_READINGS_REQUIRED:
                    # POSSIBLE_FALL condition met
                    logger.info(
                        "Fall detection: POSSIBLE_FALL — impact=%.2f g, followed by %d "
                        "low-motion readings",
                        fall_state.impact_magnitude,
                        fall_state.post_impact_readings,
                    )
                    return ActivityState.POSSIBLE_FALL
                # Still waiting for enough post-impact readings
                return ActivityState.POSSIBLE_FALL
            else:
                # High motion after impact — likely not a fall; reset
                logger.debug(
                    "Fall state machine: motion resumed after impact, resetting (mag=%.2f)", mag
                )
                fall_state.reset()

        # ----------------------------------------------------------------
        # Normal activity classification by magnitude
        # ----------------------------------------------------------------
        if mag <= ACC["rest_max"]:
            return ActivityState.REST
        elif mag <= ACC["walking_max"]:
            return ActivityState.WALKING
        elif mag <= ACC["running_max"]:
            return ActivityState.RUNNING
        else:
            return ActivityState.HIGH_ACTIVITY

    def reset_fall_state(self) -> None:
        """Reset the fall detection state (e.g. between scenarios)."""
        self._fall_state.reset()

    @property
    def fall_detection_state(self) -> FallDetectionState:
        return self._fall_state
