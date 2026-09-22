"""
tests/conftest.py — Shared fixtures for the test suite.
"""

from __future__ import annotations

import pytest
from datetime import datetime

from app.models.sensor_models import SensorReading
from app.models.risk_models import ActivityState, FallDetectionState
from app.context.activity_detector import ActivityDetector
from app.rules.rule_engine import RuleEngine
from app.validation.sensor_validator import SensorValidator


# ---------------------------------------------------------------------------
# Helper factory
# ---------------------------------------------------------------------------

def make_reading(**kwargs) -> SensorReading:
    """Create a SensorReading with safe defaults, override with kwargs."""
    defaults = dict(
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        reading_id="TEST-001",
        heart_rate=72.0,
        spo2=98.0,
        body_temperature=36.7,
        environment_temperature=23.0,
        humidity=50.0,
        altitude=50.0,
        atmospheric_pressure=1013.0,
        acceleration_x=0.01,
        acceleration_y=0.02,
        acceleration_z=0.98,
    )
    defaults.update(kwargs)
    return SensorReading(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def normal_reading():
    return make_reading()


@pytest.fixture
def validator():
    return SensorValidator()


@pytest.fixture
def activity_detector():
    return ActivityDetector()


@pytest.fixture
def rule_engine():
    return RuleEngine()


@pytest.fixture
def make_reading_fn():
    return make_reading
