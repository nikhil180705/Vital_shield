"""
tests/test_activity_detector.py — Tests for activity classification and fall detection.
"""

import pytest
from app.models.risk_models import ActivityState
from app.context.activity_detector import ActivityDetector
from tests.conftest import make_reading


class TestActivityDetector:

    def test_rest_classification(self, activity_detector):
        r = make_reading(acceleration_x=0.01, acceleration_y=0.02, acceleration_z=0.98)
        state = activity_detector.classify(r)
        assert state == ActivityState.REST

    def test_walking_classification(self, activity_detector):
        r = make_reading(acceleration_x=0.3, acceleration_y=1.8, acceleration_z=0.9)
        state = activity_detector.classify(r)
        assert state == ActivityState.WALKING

    def test_running_classification(self, activity_detector):
        r = make_reading(acceleration_x=1.2, acceleration_y=2.9, acceleration_z=1.3)
        state = activity_detector.classify(r)
        assert state == ActivityState.RUNNING

    def test_high_activity_classification(self, activity_detector):
        r = make_reading(acceleration_x=3.0, acceleration_y=4.0, acceleration_z=2.5)
        state = activity_detector.classify(r)
        assert state == ActivityState.HIGH_ACTIVITY

    def test_unknown_when_no_accelerometer(self, activity_detector):
        r = make_reading(acceleration_x=None, acceleration_y=None, acceleration_z=None)
        state = activity_detector.classify(r)
        assert state == ActivityState.UNKNOWN

    def test_fall_detection_sequence(self):
        """Fall: impact followed by immobility should yield POSSIBLE_FALL."""
        detector = ActivityDetector()

        # Step 1: Normal walking
        r1 = make_reading(acceleration_x=0.3, acceleration_y=1.8, acceleration_z=0.9)
        s1 = detector.classify(r1)
        assert s1 == ActivityState.WALKING

        # Step 2: Impact
        r2 = make_reading(acceleration_x=5.2, acceleration_y=7.8, acceleration_z=4.1)
        s2 = detector.classify(r2)
        # Impact reading is classified as HIGH_ACTIVITY at the moment
        assert s2 in (ActivityState.HIGH_ACTIVITY, ActivityState.POSSIBLE_FALL)

        # Step 3: Post-impact low motion (first)
        r3 = make_reading(acceleration_x=0.05, acceleration_y=0.08, acceleration_z=0.95)
        s3 = detector.classify(r3)
        assert s3 == ActivityState.POSSIBLE_FALL

        # Step 4: Continued immobility
        r4 = make_reading(acceleration_x=0.05, acceleration_y=0.06, acceleration_z=0.94)
        s4 = detector.classify(r4)
        assert s4 == ActivityState.POSSIBLE_FALL

    def test_no_fall_without_impact(self):
        """Low motion without prior impact should not yield POSSIBLE_FALL."""
        detector = ActivityDetector()
        for _ in range(5):
            r = make_reading(acceleration_x=0.02, acceleration_y=0.03, acceleration_z=0.97)
            state = detector.classify(r)
            assert state == ActivityState.REST

    def test_reset_fall_state(self):
        detector = ActivityDetector()
        r_impact = make_reading(acceleration_x=5.0, acceleration_y=7.0, acceleration_z=4.0)
        detector.classify(r_impact)
        assert detector.fall_detection_state.impact_detected

        detector.reset_fall_state()
        assert not detector.fall_detection_state.impact_detected
