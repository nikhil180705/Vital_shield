"""
tests/test_validation.py — Tests for the sensor data validator.
"""

import pytest
from app.models.risk_models import ValidationStatus
from tests.conftest import make_reading


class TestSensorValidator:

    def test_valid_normal_reading(self, validator, normal_reading):
        result = validator.validate(normal_reading)
        assert result.valid is True
        assert result.status == ValidationStatus.VALID
        assert result.issues == []

    def test_missing_heart_rate(self, validator):
        r = make_reading(heart_rate=None)
        result = validator.validate(r)
        assert result.valid is False
        assert any("heart_rate" in i for i in result.issues)

    def test_missing_spo2(self, validator):
        r = make_reading(spo2=None)
        result = validator.validate(r)
        assert result.valid is False

    def test_missing_body_temperature(self, validator):
        r = make_reading(body_temperature=None)
        result = validator.validate(r)
        assert result.valid is False

    def test_impossible_spo2_over_100(self, validator):
        r = make_reading(spo2=105.0)
        result = validator.validate(r)
        assert result.valid is False
        assert any("SpO2" in i or "spo2" in i.lower() for i in result.issues)

    def test_impossible_spo2_below_50(self, validator):
        r = make_reading(spo2=10.0)
        result = validator.validate(r)
        assert result.valid is False

    def test_impossible_heart_rate_zero(self, validator):
        r = make_reading(heart_rate=0.0)
        result = validator.validate(r)
        assert result.valid is False

    def test_impossible_heart_rate_negative(self, validator):
        r = make_reading(heart_rate=-10.0)
        result = validator.validate(r)
        assert result.valid is False

    def test_invalid_body_temperature_too_high(self, validator):
        r = make_reading(body_temperature=50.0)
        result = validator.validate(r)
        assert result.valid is False

    def test_invalid_body_temperature_too_low(self, validator):
        r = make_reading(body_temperature=10.0)
        result = validator.validate(r)
        assert result.valid is False

    def test_invalid_humidity_over_100(self, validator):
        r = make_reading(humidity=110.0)
        result = validator.validate(r)
        # Humidity is not a required field — should be PARTIAL not INVALID
        assert "humidity" in result.rejected_fields

    def test_invalid_pressure(self, validator):
        r = make_reading(atmospheric_pressure=50.0)
        result = validator.validate(r)
        assert "atmospheric_pressure" in result.rejected_fields

    def test_missing_optional_field_produces_warning(self, validator):
        r = make_reading(humidity=None)
        result = validator.validate(r)
        assert result.valid is True   # Humidity is optional
        assert any("humidity" in w for w in result.warnings)

    def test_boundary_spo2_valid(self, validator):
        # 50% is the lower bound — exactly on boundary
        r = make_reading(spo2=50.0)
        result = validator.validate(r)
        assert result.valid is True   # Just within bounds

    def test_all_fields_valid(self, validator, normal_reading):
        result = validator.validate(normal_reading)
        assert result.valid is True
        assert result.rejected_fields == []
