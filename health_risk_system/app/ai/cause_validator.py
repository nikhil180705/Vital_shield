"""
cause_validator.py — Deterministic cause validation layer.

Validates each proposed cause from Agent 1 against available sensor
evidence. This layer ensures the LLM cannot fabricate unsupported causes.

Validation statuses:
    SUPPORTED            — Strong sensor evidence backs this cause
    PARTIALLY_SUPPORTED  — Some evidence, incomplete confirmation
    NOT_SUPPORTED        — Evidence contradicts or is absent
    INSUFFICIENT_DATA    — Not enough sensor data to evaluate

Only SUPPORTED and PARTIALLY_SUPPORTED causes are passed to Agent 2.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.config import THRESHOLDS, BASELINE
from app.models.ai_models import (
    CauseAnalysisResult,
    CauseValidationResult,
    CauseValidationStatus,
    ValidatedCause,
)
from app.models.risk_models import ActivityState, RiskEvent

logger = logging.getLogger(__name__)

HR   = THRESHOLDS["heart_rate"]
SPO2 = THRESHOLDS["spo2"]
TEMP = THRESHOLDS["body_temperature"]
ENV  = THRESHOLDS["environment_temperature"]
HUM  = THRESHOLDS["humidity"]
HEAT = THRESHOLDS["heat_stress"]


# ---------------------------------------------------------------------------
# Keyword-to-evidence mapping
# Each tuple: (keyword_in_cause, validator_function)
# ---------------------------------------------------------------------------

def _get_sensor(event: RiskEvent, key: str) -> Optional[float]:
    """Safe accessor for sensor snapshot."""
    return event.sensor_snapshot.get(key)


def _validate_heat_stress(event: RiskEvent) -> tuple:
    """Validate heat-related cause."""
    et = _get_sensor(event, "environment_temperature")
    hum = _get_sensor(event, "humidity")
    hr = _get_sensor(event, "heart_rate")
    bt = _get_sensor(event, "body_temperature")

    evidence = []
    contra = []
    notes = []

    if et is not None:
        if et >= HEAT["env_temp_trigger"]:
            evidence.append(f"Environment temperature {et}°C ≥ {HEAT['env_temp_trigger']}°C")
        else:
            contra.append(f"Environment temperature {et}°C is not markedly elevated")
    else:
        notes.append("Environment temperature data missing")

    if hum is not None:
        if hum >= HEAT["humidity_trigger"]:
            evidence.append(f"Humidity {hum}% ≥ {HEAT['humidity_trigger']}%")
        else:
            contra.append(f"Humidity {hum}% is not critically high")
    else:
        notes.append("Humidity data missing")

    if hr is not None and hr >= HEAT["hr_trigger_rest"]:
        evidence.append(f"Elevated HR {hr} bpm consistent with heat stress response")

    if bt is not None and bt >= HEAT["body_temp_trigger"]:
        evidence.append(f"Elevated body temperature {bt}°C")

    if len(evidence) >= 3:
        status = CauseValidationStatus.SUPPORTED
    elif len(evidence) >= 1:
        status = CauseValidationStatus.PARTIALLY_SUPPORTED
    elif notes:
        status = CauseValidationStatus.INSUFFICIENT_DATA
    else:
        status = CauseValidationStatus.NOT_SUPPORTED

    return status, evidence, contra, notes


def _validate_tachycardia_rest(event: RiskEvent) -> tuple:
    """Validate resting tachycardia cause."""
    hr = _get_sensor(event, "heart_rate")
    activity = event.activity_state
    baseline = BASELINE["heart_rate_bpm"]

    evidence = []
    contra = []
    notes = []

    if hr is not None:
        if hr > HR["resting_normal_max"]:
            evidence.append(f"HR {hr} bpm exceeds resting normal max ({HR['resting_normal_max']} bpm)")
        else:
            contra.append(f"HR {hr} bpm is within normal resting range")

        dev = hr - baseline
        if dev >= THRESHOLDS["baseline_deviation"]["hr_significant_bpm"]:
            evidence.append(f"HR elevated {dev} bpm above personal baseline {baseline} bpm")
    else:
        notes.append("Heart rate data missing")

    if activity in ("REST", "UNKNOWN"):
        evidence.append(f"Activity state ({activity}) confirms low-movement context")
    elif activity in ("RUNNING", "HIGH_ACTIVITY"):
        contra.append(f"Activity state is {activity} — elevated HR may be physiological")

    if len(evidence) >= 2:
        status = CauseValidationStatus.SUPPORTED
    elif len(evidence) == 1:
        status = CauseValidationStatus.PARTIALLY_SUPPORTED
    elif notes:
        status = CauseValidationStatus.INSUFFICIENT_DATA
    else:
        status = CauseValidationStatus.NOT_SUPPORTED

    return status, evidence, contra, notes


def _validate_low_oxygen(event: RiskEvent) -> tuple:
    """Validate low oxygen / SpO2 cause."""
    spo2 = _get_sensor(event, "spo2")
    alt = _get_sensor(event, "altitude")
    activity = event.activity_state

    evidence = []
    contra = []
    notes = []

    if spo2 is not None:
        if spo2 < SPO2["critical"]:
            evidence.append(f"SpO2 {spo2}% below critical threshold {SPO2['critical']}%")
        elif spo2 < SPO2["high_risk"]:
            evidence.append(f"SpO2 {spo2}% in high-risk band")
        elif spo2 < SPO2["monitor"]:
            evidence.append(f"SpO2 {spo2}% in monitor band — below normal")
        else:
            contra.append(f"SpO2 {spo2}% is within normal range — does not support low-oxygen cause")
    else:
        notes.append("SpO2 data missing")

    if alt is not None and alt >= THRESHOLDS["altitude"]["high"]:
        evidence.append(f"Altitude {alt} m may contribute to SpO2 reduction")

    if activity in ("RUNNING", "HIGH_ACTIVITY"):
        notes.append("Activity may transiently affect SpO2 reading quality")

    if len(evidence) >= 2:
        status = CauseValidationStatus.SUPPORTED
    elif len(evidence) == 1:
        status = CauseValidationStatus.PARTIALLY_SUPPORTED
    elif notes:
        status = CauseValidationStatus.INSUFFICIENT_DATA
    else:
        status = CauseValidationStatus.NOT_SUPPORTED

    return status, evidence, contra, notes


def _validate_illness_stress(event: RiskEvent) -> tuple:
    """Validate illness/stress pattern cause."""
    bt = _get_sensor(event, "body_temperature")
    hr = _get_sensor(event, "heart_rate")
    activity = event.activity_state

    evidence = []
    contra = []
    notes = []

    if bt is not None:
        if bt >= TEMP["fever_candidate"]:
            evidence.append(f"Body temperature {bt}°C ≥ fever-candidate threshold {TEMP['fever_candidate']}°C")
        elif bt >= TEMP["elevated"]:
            evidence.append(f"Body temperature {bt}°C is mildly elevated above reference")
        else:
            contra.append(f"Body temperature {bt}°C within normal range")
    else:
        notes.append("Body temperature data missing")

    if hr is not None and hr > HR["resting_normal_max"]:
        evidence.append(f"Elevated resting HR {hr} bpm may reflect physiological stress")

    if activity in ("REST", "WALKING", "UNKNOWN"):
        evidence.append("Low activity level rules out exercise as cause of elevated HR")
    elif activity in ("RUNNING", "HIGH_ACTIVITY"):
        contra.append("Elevated HR could be physiological exercise response")

    if len(evidence) >= 2:
        status = CauseValidationStatus.SUPPORTED
    elif len(evidence) == 1:
        status = CauseValidationStatus.PARTIALLY_SUPPORTED
    elif notes:
        status = CauseValidationStatus.INSUFFICIENT_DATA
    else:
        status = CauseValidationStatus.NOT_SUPPORTED

    return status, evidence, contra, notes


def _validate_fall(event: RiskEvent) -> tuple:
    """Validate possible fall cause."""
    activity = event.activity_state
    accel = _get_sensor(event, "acceleration_magnitude")
    has_fall_rule = any(
        r.rule_id == "FALL_POSSIBLE_001" for r in event.triggered_rules
    )

    evidence = []
    contra = []
    notes = []

    if activity == "POSSIBLE_FALL":
        evidence.append("Activity state classified as POSSIBLE_FALL by accelerometer pattern")
    if has_fall_rule:
        evidence.append("Fall detection rule (FALL_POSSIBLE_001) triggered")

    if not evidence:
        contra.append("Activity state does not indicate a fall pattern")

    if len(evidence) >= 1:
        status = CauseValidationStatus.SUPPORTED
    else:
        status = CauseValidationStatus.NOT_SUPPORTED

    return status, evidence, contra, notes


def _validate_altitude_effect(event: RiskEvent) -> tuple:
    """Validate altitude-related SpO2 cause."""
    alt = _get_sensor(event, "altitude")
    spo2 = _get_sensor(event, "spo2")
    alt_change = event.environment_context.get("altitude_change")

    evidence = []
    contra = []
    notes = []

    if alt is not None and alt >= THRESHOLDS["altitude"]["high"]:
        evidence.append(f"Significant altitude {alt} m (≥{THRESHOLDS['altitude']['high']} m)")
    elif alt is not None:
        contra.append(f"Altitude {alt} m is not high enough to significantly affect SpO2")
    else:
        notes.append("Altitude data not available")

    if spo2 is not None and spo2 < SPO2["normal_min"]:
        evidence.append(f"SpO2 {spo2}% below normal — consistent with altitude effect")

    if alt_change is not None and alt_change > 200:
        evidence.append(f"Rapid altitude gain of {alt_change} m noted")

    if len(evidence) >= 2:
        status = CauseValidationStatus.SUPPORTED
    elif len(evidence) == 1:
        status = CauseValidationStatus.PARTIALLY_SUPPORTED
    elif notes:
        status = CauseValidationStatus.INSUFFICIENT_DATA
    else:
        status = CauseValidationStatus.NOT_SUPPORTED

    return status, evidence, contra, notes


def _validate_sensor_artifact(event: RiskEvent) -> tuple:
    """Sensor artifact / noise cause — always partially supported (can't rule out)."""
    return (
        CauseValidationStatus.PARTIALLY_SUPPORTED,
        ["Wrist-based sensors have known accuracy limitations",
         "Movement artifacts can affect SpO2 and HR readings"],
        [],
        [],
    )


# ---------------------------------------------------------------------------
# Cause matching
# ---------------------------------------------------------------------------

CAUSE_VALIDATORS = {
    "heat": _validate_heat_stress,
    "hyperthermia": _validate_heat_stress,
    "dehydrat": _validate_heat_stress,
    "tachycardia": _validate_tachycardia_rest,
    "resting heart": _validate_tachycardia_rest,
    "elevated heart": _validate_tachycardia_rest,
    "oxygen": _validate_low_oxygen,
    "hypoxia": _validate_low_oxygen,
    "spo2": _validate_low_oxygen,
    "saturation": _validate_low_oxygen,
    "illness": _validate_illness_stress,
    "fever": _validate_illness_stress,
    "infection": _validate_illness_stress,
    "stress": _validate_illness_stress,
    "fall": _validate_fall,
    "impact": _validate_fall,
    "altitude": _validate_altitude_effect,
    "elevation": _validate_altitude_effect,
    "artifact": _validate_sensor_artifact,
    "sensor": _validate_sensor_artifact,
    "noise": _validate_sensor_artifact,
}


class CauseValidator:
    """
    Deterministic validation of AI-proposed causes against sensor evidence.
    Prevents unsupported LLM claims from propagating to Agent 2.
    """

    def validate(
        self,
        cause_analysis: CauseAnalysisResult,
        event: RiskEvent,
    ) -> CauseValidationResult:
        """
        Validate each proposed cause and separate into passed/rejected lists.
        """
        validated: List[ValidatedCause] = []
        passed: List[ValidatedCause] = []
        rejected: List[ValidatedCause] = []

        for cause_obj in cause_analysis.possible_causes:
            status, evidence, contra, notes = self._validate_cause(cause_obj.cause, event)

            vc = ValidatedCause(
                cause=cause_obj.cause,
                confidence=cause_obj.confidence,
                validation_status=status,
                supporting_evidence=evidence + cause_obj.supporting_evidence,
                contradicting_evidence=contra + cause_obj.contradicting_evidence,
                validation_notes=notes,
                passed_to_agent2=(
                    status in (
                        CauseValidationStatus.SUPPORTED,
                        CauseValidationStatus.PARTIALLY_SUPPORTED,
                    )
                ),
            )
            validated.append(vc)

            if vc.passed_to_agent2:
                passed.append(vc)
                logger.info(
                    "Cause PASSED validation: '%s' → %s", cause_obj.cause, status
                )
            else:
                rejected.append(vc)
                logger.warning(
                    "Cause REJECTED: '%s' → %s", cause_obj.cause, status
                )

        summary_parts = []
        if passed:
            summary_parts.append(
                f"{len(passed)} cause(s) passed validation and will be sent to Agent 2."
            )
        if rejected:
            summary_parts.append(
                f"{len(rejected)} cause(s) rejected due to insufficient sensor evidence."
            )

        return CauseValidationResult(
            validated_causes=validated,
            passed_causes=passed,
            rejected_causes=rejected,
            validation_summary=" ".join(summary_parts),
        )

    def _validate_cause(
        self, cause_text: str, event: RiskEvent
    ) -> tuple:
        """Match cause text to a validator function and run it."""
        cause_lower = cause_text.lower()

        for keyword, validator_fn in CAUSE_VALIDATORS.items():
            if keyword in cause_lower:
                return validator_fn(event)

        # Unknown cause — INSUFFICIENT_DATA (can't support or reject)
        logger.debug("No specific validator for cause: '%s' — INSUFFICIENT_DATA", cause_text)
        return (
            CauseValidationStatus.INSUFFICIENT_DATA,
            [],
            [],
            ["No specific validation rule available for this cause category."],
        )
