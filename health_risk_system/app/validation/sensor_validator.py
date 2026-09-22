"""
sensor_validator.py — Deterministic data validation layer.

Validates a SensorReading BEFORE it enters the rule engine.
Invalid readings are never sent to the LLM.

Detected issues:
  - Missing / None fields
  - Physically impossible values
  - Out-of-plausible-range values
  - Sensor dropout patterns
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from app.models.sensor_models import SensorReading
from app.models.risk_models import ValidationResult, ValidationStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plausible physical bounds  –  NOT medical limits, pure sanity bounds
# ---------------------------------------------------------------------------
BOUNDS = {
    "heart_rate":             (20.0,  300.0),
    "spo2":                   (50.0,  100.0),
    "body_temperature":       (25.0,   45.0),
    "environment_temperature":(-60.0,  60.0),
    "humidity":               (0.0,   100.0),
    "altitude":               (-500.0, 9000.0),
    "atmospheric_pressure":   (250.0, 1100.0),
    "acceleration_x":         (-20.0,  20.0),
    "acceleration_y":         (-20.0,  20.0),
    "acceleration_z":         (-20.0,  20.0),
}

# Fields that are REQUIRED for a reading to be considered valid
REQUIRED_FIELDS = ["heart_rate", "spo2", "body_temperature"]

# Fields that are IMPORTANT but absence only produces a warning
IMPORTANT_FIELDS = [
    "environment_temperature",
    "humidity",
    "altitude",
    "atmospheric_pressure",
    "acceleration_x",
    "acceleration_y",
    "acceleration_z",
]


class SensorValidator:
    """
    Validates a single SensorReading.

    Returns a ValidationResult describing whether the reading is usable,
    partially usable, or should be rejected entirely.
    """

    def validate(self, reading: SensorReading) -> ValidationResult:
        issues: List[str] = []
        warnings: List[str] = []
        rejected_fields: List[str] = []

        # ----------------------------------------------------------------
        # 1. Required field presence
        # ----------------------------------------------------------------
        for field in REQUIRED_FIELDS:
            value = getattr(reading, field, None)
            if value is None:
                issues.append(f"Required field '{field}' is missing or null.")
                rejected_fields.append(field)

        # ----------------------------------------------------------------
        # 2. Important field presence (warnings only)
        # ----------------------------------------------------------------
        for field in IMPORTANT_FIELDS:
            value = getattr(reading, field, None)
            if value is None:
                warnings.append(f"Field '{field}' is missing — sensor may have dropped out.")

        # ----------------------------------------------------------------
        # 3. Physically plausible bounds check
        # ----------------------------------------------------------------
        for field, (lo, hi) in BOUNDS.items():
            value = getattr(reading, field, None)
            if value is None:
                continue
            if not (lo <= value <= hi):
                msg = (
                    f"'{field}' value {value} is outside the physically plausible "
                    f"range [{lo}, {hi}]."
                )
                issues.append(msg)
                rejected_fields.append(field)

        # ----------------------------------------------------------------
        # 4. SpO2-specific checks
        # ----------------------------------------------------------------
        if reading.spo2 is not None:
            if reading.spo2 > 100.0:
                issues.append(f"SpO2 {reading.spo2}% exceeds 100% — physically impossible.")
                if "spo2" not in rejected_fields:
                    rejected_fields.append("spo2")
            elif reading.spo2 < 50.0:
                issues.append(f"SpO2 {reading.spo2}% is below any plausible living threshold.")
                if "spo2" not in rejected_fields:
                    rejected_fields.append("spo2")

        # ----------------------------------------------------------------
        # 5. Heart rate — zero check
        # ----------------------------------------------------------------
        if reading.heart_rate is not None:
            if reading.heart_rate <= 0:
                issues.append("Heart rate must be positive — sensor may have lost contact.")
                if "heart_rate" not in rejected_fields:
                    rejected_fields.append("heart_rate")

        # ----------------------------------------------------------------
        # 6. Body temperature — narrow sanity band
        # ----------------------------------------------------------------
        if reading.body_temperature is not None:
            if reading.body_temperature < 28.0:
                issues.append(
                    f"Body temperature {reading.body_temperature}°C is critically low — "
                    "possible sensor error (wrist sensor may have lost contact)."
                )
                warnings.append("Body temperature reading may be unreliable.")
            elif reading.body_temperature > 43.0:
                issues.append(
                    f"Body temperature {reading.body_temperature}°C exceeds survival range — "
                    "likely sensor error."
                )

        # ----------------------------------------------------------------
        # 7. Determine overall status
        # ----------------------------------------------------------------
        # Any rejected required field → INVALID
        critical_rejected = [f for f in rejected_fields if f in REQUIRED_FIELDS]

        if critical_rejected:
            status = ValidationStatus.INVALID
            valid = False
        elif issues:
            # Non-critical issues (out of bounds on optional sensors)
            status = ValidationStatus.PARTIAL
            valid = True   # Still processable with caveats
        else:
            status = ValidationStatus.VALID
            valid = True

        result = ValidationResult(
            valid=valid,
            status=status,
            issues=issues,
            warnings=warnings,
            rejected_fields=list(set(rejected_fields)),
        )

        if not valid:
            logger.warning(
                "VALIDATION FAILED reading_id=%s issues=%s",
                reading.reading_id,
                issues,
            )
        elif issues or warnings:
            logger.info(
                "VALIDATION PARTIAL reading_id=%s warnings=%s",
                reading.reading_id,
                warnings,
            )

        return result
