"""
rule_definitions.py — All individual rule check functions.

Every rule receives (reading, activity_state, baseline) and returns
a TriggeredRule.  Rules are self-contained and inspectable.

ALL thresholds here come from config.THRESHOLDS.

DISCLAIMER: These are SCREENING / PROTOTYPE THRESHOLDS,
NOT MEDICAL DIAGNOSTIC LIMITS.
"""

from __future__ import annotations

from typing import Optional

from app.config import THRESHOLDS, BASELINE
from app.models.sensor_models import SensorReading
from app.models.risk_models import ActivityState, Severity, TriggeredRule

HR   = THRESHOLDS["heart_rate"]
SPO2 = THRESHOLDS["spo2"]
TEMP = THRESHOLDS["body_temperature"]
ENV  = THRESHOLDS["environment_temperature"]
HUM  = THRESHOLDS["humidity"]
ALT  = THRESHOLDS["altitude"]
HEAT = THRESHOLDS["heat_stress"]
BASE_DEV = THRESHOLDS["baseline_deviation"]


def _make_rule(
    rule_id: str,
    rule_name: str,
    description: str,
    severity: Severity,
    triggered: bool,
    reason: str,
    evidence: dict,
    score: int = 0,
) -> TriggeredRule:
    return TriggeredRule(
        rule_id=rule_id,
        rule_name=rule_name,
        description=description,
        severity=severity,
        triggered=triggered,
        reason=reason,
        evidence=evidence,
        score_contribution=score if triggered else 0,
    )


# ---------------------------------------------------------------------------
# Heart Rate Rules
# ---------------------------------------------------------------------------

def rule_hr_rest_elevated(
    reading: SensorReading,
    activity: ActivityState,
) -> TriggeredRule:
    """HR elevated at rest — resting tachycardia candidate."""
    hr = reading.heart_rate
    baseline_hr = BASELINE["heart_rate_bpm"]
    is_rest = activity in (ActivityState.REST, ActivityState.UNKNOWN)
    triggered = (
        hr is not None
        and is_rest
        and hr > HR["resting_normal_max"]
    )
    dev = round(hr - baseline_hr, 1) if hr is not None else 0

    if hr is not None and hr >= HR["severe_risk"] and is_rest:
        sev = Severity.CRITICAL
        score = 35
    elif hr is not None and hr >= HR["high_risk"] and is_rest:
        sev = Severity.HIGH
        score = 25
    elif hr is not None and hr >= HR["high"] and is_rest:
        sev = Severity.MEDIUM
        score = 15
    else:
        sev = Severity.LOW
        score = 8

    return _make_rule(
        rule_id="HR_REST_HIGH_001",
        rule_name="Elevated Resting Heart Rate",
        description="Heart rate significantly above resting normal range while user is at rest.",
        severity=sev,
        triggered=triggered,
        reason=(
            f"Resting HR {hr} bpm exceeds resting-normal max {HR['resting_normal_max']} bpm "
            f"(+{dev} bpm above personal baseline {baseline_hr} bpm)."
            if triggered else "Heart rate within acceptable range for activity level."
        ),
        evidence={"heart_rate": hr, "baseline": baseline_hr, "deviation": dev, "activity": activity},
        score=score,
    )


def rule_hr_low(reading: SensorReading) -> TriggeredRule:
    """Low heart rate (bradycardia candidate)."""
    hr = reading.heart_rate
    triggered = hr is not None and hr < HR["low_monitoring"]
    sev = Severity.HIGH if (hr is not None and hr < HR["low_risk"]) else Severity.MEDIUM

    return _make_rule(
        rule_id="HR_LOW_001",
        rule_name="Low Heart Rate",
        description="Heart rate below the low-monitoring threshold.",
        severity=sev,
        triggered=triggered,
        reason=(
            f"HR {hr} bpm is below the low-monitoring threshold ({HR['low_monitoring']} bpm)."
            if triggered else "Heart rate not critically low."
        ),
        evidence={"heart_rate": hr, "low_threshold": HR["low_monitoring"]},
        score=12 if triggered else 0,
    )


def rule_hr_exercise_extreme(
    reading: SensorReading,
    activity: ActivityState,
) -> TriggeredRule:
    """Extremely high HR even during vigorous exercise."""
    hr = reading.heart_rate
    is_active = activity in (ActivityState.RUNNING, ActivityState.HIGH_ACTIVITY)
    triggered = hr is not None and is_active and hr >= HR["exercise_high_risk"]

    return _make_rule(
        rule_id="HR_EXERCISE_HIGH_001",
        rule_name="Extreme Heart Rate During Exercise",
        description="Heart rate exceeds safe exercise bounds even accounting for vigorous activity.",
        severity=Severity.HIGH,
        triggered=triggered,
        reason=(
            f"HR {hr} bpm exceeds exercise upper bound ({HR['exercise_high_risk']} bpm)."
            if triggered else "Exercise HR within expected range."
        ),
        evidence={"heart_rate": hr, "activity": activity, "threshold": HR["exercise_high_risk"]},
        score=20 if triggered else 0,
    )


# ---------------------------------------------------------------------------
# SpO2 Rules
# ---------------------------------------------------------------------------

def rule_spo2_critical(reading: SensorReading) -> TriggeredRule:
    """SpO2 below critical threshold."""
    spo2 = reading.spo2
    triggered = spo2 is not None and spo2 < SPO2["critical"]

    return _make_rule(
        rule_id="SPO2_CRITICAL_001",
        rule_name="Critical SpO2",
        description="Oxygen saturation below critical screening threshold.",
        severity=Severity.CRITICAL,
        triggered=triggered,
        reason=(
            f"SpO2 {spo2}% is below critical threshold {SPO2['critical']}%."
            if triggered else "SpO2 not at critical level."
        ),
        evidence={"spo2": spo2, "critical_threshold": SPO2["critical"]},
        score=40 if triggered else 0,
    )


def rule_spo2_high_risk(reading: SensorReading) -> TriggeredRule:
    """SpO2 at high-risk level (not yet critical)."""
    spo2 = reading.spo2
    triggered = (
        spo2 is not None
        and SPO2["critical"] <= spo2 < SPO2["high_risk"]
    )

    return _make_rule(
        rule_id="SPO2_HIGH_RISK_001",
        rule_name="High-Risk SpO2",
        description="Oxygen saturation at high-risk screening level.",
        severity=Severity.HIGH,
        triggered=triggered,
        reason=(
            f"SpO2 {spo2}% is in the high-risk band [{SPO2['critical']}–{SPO2['high_risk']}%)."
            if triggered else "SpO2 not in high-risk band."
        ),
        evidence={"spo2": spo2},
        score=28 if triggered else 0,
    )


def rule_spo2_monitor(reading: SensorReading) -> TriggeredRule:
    """SpO2 in the monitor band."""
    spo2 = reading.spo2
    triggered = (
        spo2 is not None
        and SPO2["high_risk"] <= spo2 < SPO2["monitor"]
    )

    return _make_rule(
        rule_id="SPO2_MONITOR_001",
        rule_name="SpO2 Monitor Band",
        description="Oxygen saturation below normal but above high-risk threshold.",
        severity=Severity.MEDIUM,
        triggered=triggered,
        reason=(
            f"SpO2 {spo2}% is in the monitor band [{SPO2['high_risk']}–{SPO2['monitor']}%)."
            if triggered else "SpO2 not in monitor band."
        ),
        evidence={"spo2": spo2},
        score=12 if triggered else 0,
    )


# ---------------------------------------------------------------------------
# Body Temperature Rules
# ---------------------------------------------------------------------------

def rule_temp_severe(reading: SensorReading) -> TriggeredRule:
    """Body temperature at severe-risk level."""
    t = reading.body_temperature
    triggered = t is not None and t >= TEMP["severe"]

    return _make_rule(
        rule_id="TEMP_SEVERE_001",
        rule_name="Severe Elevated Body Temperature",
        description="Wrist skin temperature at severe prototype screening threshold.",
        severity=Severity.CRITICAL,
        triggered=triggered,
        reason=(
            f"Body temperature {t}°C ≥ severe threshold {TEMP['severe']}°C."
            if triggered else "Body temperature below severe threshold."
        ),
        evidence={"body_temperature": t, "threshold": TEMP["severe"]},
        score=35 if triggered else 0,
    )


def rule_temp_high(reading: SensorReading) -> TriggeredRule:
    """Body temperature in the 'high' band."""
    t = reading.body_temperature
    triggered = (
        t is not None
        and TEMP["high"] <= t < TEMP["severe"]
    )

    return _make_rule(
        rule_id="TEMP_HIGH_001",
        rule_name="Elevated Body Temperature — High",
        description="Wrist skin temperature above high threshold.",
        severity=Severity.HIGH,
        triggered=triggered,
        reason=(
            f"Body temperature {t}°C is in the high band [{TEMP['high']}–{TEMP['severe']}°C)."
            if triggered else "Body temperature not in high band."
        ),
        evidence={"body_temperature": t},
        score=20 if triggered else 0,
    )


def rule_temp_fever_candidate(reading: SensorReading) -> TriggeredRule:
    """Body temperature in the fever-candidate band."""
    t = reading.body_temperature
    triggered = (
        t is not None
        and TEMP["fever_candidate"] <= t < TEMP["high"]
    )

    return _make_rule(
        rule_id="TEMP_FEVER_001",
        rule_name="Elevated Body Temperature — Fever Candidate",
        description="Wrist skin temperature above fever-candidate threshold.",
        severity=Severity.MEDIUM,
        triggered=triggered,
        reason=(
            f"Body temperature {t}°C is in the fever-candidate band "
            f"[{TEMP['fever_candidate']}–{TEMP['high']}°C)."
            if triggered else "Body temperature below fever-candidate threshold."
        ),
        evidence={"body_temperature": t, "normal_max": TEMP["normal_max"]},
        score=12 if triggered else 0,
    )


def rule_temp_elevated(reading: SensorReading) -> TriggeredRule:
    """Body temperature in the elevated band."""
    t = reading.body_temperature
    triggered = (
        t is not None
        and TEMP["elevated"] <= t < TEMP["fever_candidate"]
    )

    return _make_rule(
        rule_id="TEMP_ELEVATED_001",
        rule_name="Slightly Elevated Body Temperature",
        description="Wrist skin temperature mildly elevated above reference.",
        severity=Severity.LOW,
        triggered=triggered,
        reason=(
            f"Body temperature {t}°C in elevated band "
            f"[{TEMP['elevated']}–{TEMP['fever_candidate']}°C)."
            if triggered else "Body temperature not elevated."
        ),
        evidence={"body_temperature": t},
        score=5 if triggered else 0,
    )


# ---------------------------------------------------------------------------
# Environmental + Heat Stress Rules
# ---------------------------------------------------------------------------

def rule_heat_stress(
    reading: SensorReading,
    activity: ActivityState,
) -> TriggeredRule:
    """
    Composite heat-stress rule.
    Requires combination of:
      - elevated environment temperature
      - high humidity
      - elevated HR (at or above rest trigger)
      AND/OR elevated body temperature
    """
    et = reading.environment_temperature
    hum = reading.humidity
    hr = reading.heart_rate
    bt = reading.body_temperature

    env_hot = et is not None and et >= HEAT["env_temp_trigger"]
    hum_high = hum is not None and hum >= HEAT["humidity_trigger"]
    hr_elevated = hr is not None and hr >= HEAT["hr_trigger_rest"]
    bt_elevated = bt is not None and bt >= HEAT["body_temp_trigger"]

    triggered = env_hot and hum_high and hr_elevated

    if triggered and bt_elevated:
        sev = Severity.HIGH
        score = 30
        reason = (
            f"Heat stress composite: env_temp {et}°C, humidity {hum}%, "
            f"HR {hr} bpm, body_temp {bt}°C — all above thresholds."
        )
    elif triggered:
        sev = Severity.MEDIUM
        score = 18
        reason = (
            f"Heat stress composite: env_temp {et}°C, humidity {hum}%, HR {hr} bpm."
        )
    else:
        sev = Severity.LOW
        score = 0
        reason = "Heat stress composite conditions not all met."

    return _make_rule(
        rule_id="HEAT_STRESS_001",
        rule_name="Possible Heat-Related Physiological Stress",
        description="Combined elevated environmental temperature, humidity, HR, and/or body temperature.",
        severity=sev,
        triggered=triggered,
        reason=reason,
        evidence={
            "environment_temperature": et,
            "humidity": hum,
            "heart_rate": hr,
            "body_temperature": bt,
            "activity": activity,
            "thresholds": HEAT,
        },
        score=score,
    )


# ---------------------------------------------------------------------------
# Altitude / Pressure Rules
# ---------------------------------------------------------------------------

def rule_high_altitude_spo2_concern(reading: SensorReading) -> TriggeredRule:
    """
    SpO2 concern at high altitude — requires altitude context.
    SpO2 reduction at altitude is expected; this rule flags it for context
    rather than diagnosing altitude sickness.
    """
    alt = reading.altitude
    spo2 = reading.spo2
    alt_threshold = SPO2["altitude_adjustment_threshold_m"]

    at_altitude = alt is not None and alt >= alt_threshold
    spo2_below_normal = spo2 is not None and spo2 < SPO2["normal_min"]

    triggered = at_altitude and spo2_below_normal

    return _make_rule(
        rule_id="ALTITUDE_SPO2_001",
        rule_name="SpO2 Decrease at Altitude",
        description="SpO2 has declined below normal at significant altitude. Altitude context required for interpretation.",
        severity=Severity.MEDIUM,
        triggered=triggered,
        reason=(
            f"Altitude {alt} m (≥{alt_threshold} m) with SpO2 {spo2}% below normal {SPO2['normal_min']}%."
            if triggered else "Either altitude not significant or SpO2 within normal range."
        ),
        evidence={"altitude": alt, "spo2": spo2, "altitude_threshold": alt_threshold},
        score=15 if triggered else 0,
    )


def rule_rapid_altitude_change(reading: SensorReading) -> TriggeredRule:
    """Rapid altitude change in one reading interval."""
    alt_change = reading.altitude_change
    triggered = alt_change is not None and abs(alt_change) >= 300

    return _make_rule(
        rule_id="ALTITUDE_RAPID_001",
        rule_name="Rapid Altitude Change",
        description="Altitude changed significantly between readings.",
        severity=Severity.LOW,
        triggered=triggered,
        reason=(
            f"Altitude changed by {alt_change} m in one reading interval."
            if triggered else "Altitude change within normal range."
        ),
        evidence={"altitude_change": alt_change},
        score=8 if triggered else 0,
    )


# ---------------------------------------------------------------------------
# Multi-Sensor / Composite Rules
# ---------------------------------------------------------------------------

def rule_spo2_hr_rest_combined(
    reading: SensorReading,
    activity: ActivityState,
) -> TriggeredRule:
    """
    Combined oxygen + cardiovascular anomaly at rest.
    Low SpO2 + Elevated HR + REST = stronger multi-sensor concern.
    """
    spo2 = reading.spo2
    hr = reading.heart_rate
    is_rest = activity in (ActivityState.REST, ActivityState.UNKNOWN)

    spo2_low = spo2 is not None and spo2 < SPO2["monitor"]
    hr_high = hr is not None and hr > HR["resting_normal_max"]

    triggered = is_rest and spo2_low and hr_high

    return _make_rule(
        rule_id="MULTI_SPO2_HR_001",
        rule_name="Combined Low SpO2 + Elevated Resting HR",
        description="SpO2 below normal AND heart rate elevated at rest — multi-sensor anomaly.",
        severity=Severity.HIGH,
        triggered=triggered,
        reason=(
            f"SpO2 {spo2}% + HR {hr} bpm both abnormal during REST."
            if triggered else "Single-sensor or activity mismatch — not a combined anomaly."
        ),
        evidence={"spo2": spo2, "heart_rate": hr, "activity": activity},
        score=22 if triggered else 0,
    )


def rule_illness_pattern(
    reading: SensorReading,
    activity: ActivityState,
) -> TriggeredRule:
    """
    Possible illness / physiological stress pattern:
      elevated body temp + elevated resting HR + low activity.
    """
    bt = reading.body_temperature
    hr = reading.heart_rate
    is_low_activity = activity in (
        ActivityState.REST, ActivityState.WALKING, ActivityState.UNKNOWN
    )

    bt_elevated = bt is not None and bt >= TEMP["fever_candidate"]
    hr_elevated = hr is not None and hr > HR["resting_normal_max"]

    triggered = bt_elevated and hr_elevated and is_low_activity

    return _make_rule(
        rule_id="ILLNESS_PATTERN_001",
        rule_name="Possible Illness / Physiological Stress Pattern",
        description="Elevated body temperature combined with elevated resting HR during low activity.",
        severity=Severity.HIGH,
        triggered=triggered,
        reason=(
            f"Body temperature {bt}°C (≥{TEMP['fever_candidate']}°C) with HR {hr} bpm "
            f"elevated during {activity} — possible illness/stress pattern."
            if triggered else "Illness pattern criteria not met."
        ),
        evidence={"body_temperature": bt, "heart_rate": hr, "activity": activity},
        score=20 if triggered else 0,
    )


def rule_possible_fall(activity: ActivityState) -> TriggeredRule:
    """POSSIBLE_FALL detection (activity state already classified by ActivityDetector)."""
    triggered = activity == ActivityState.POSSIBLE_FALL

    return _make_rule(
        rule_id="FALL_POSSIBLE_001",
        rule_name="Possible Fall Detected",
        description=(
            "Sudden high acceleration followed by near-zero movement — "
            "pattern consistent with a possible fall. NOT a confirmed fall."
        ),
        severity=Severity.CRITICAL,
        triggered=triggered,
        reason=(
            "Activity state classified as POSSIBLE_FALL: "
            "impact-level acceleration followed by post-event immobility."
            if triggered else "No fall pattern detected."
        ),
        evidence={"activity_state": activity},
        score=50 if triggered else 0,
    )


def rule_exercise_normal(
    reading: SensorReading,
    activity: ActivityState,
) -> TriggeredRule:
    """
    Identifies normal physiological activity during exercise.
    This rule short-circuits AI analysis when elevated HR is fully
    explained by vigorous activity.
    """
    hr = reading.heart_rate
    spo2 = reading.spo2
    bt = reading.body_temperature
    is_running = activity in (ActivityState.RUNNING, ActivityState.HIGH_ACTIVITY)

    spo2_ok = spo2 is None or spo2 >= SPO2["monitor"]
    temp_ok = bt is None or bt < TEMP["high"]
    hr_ok_for_exercise = hr is None or hr < HR["exercise_high_risk"]

    triggered = is_running and spo2_ok and temp_ok and hr_ok_for_exercise

    return _make_rule(
        rule_id="EXERCISE_NORMAL_001",
        rule_name="Normal Physiological Activity",
        description="Elevated HR fully explained by vigorous physical activity. Not a medical risk event.",
        severity=Severity.INFO,
        triggered=triggered,
        reason=(
            f"HR {hr} bpm with activity={activity} — normal physiological exercise response."
            if triggered else "Exercise normalisation conditions not met."
        ),
        evidence={"heart_rate": hr, "spo2": spo2, "body_temperature": bt, "activity": activity},
        score=0,  # This is a NORMALISING rule — reduces concern
    )


def rule_baseline_deviation_hr(reading: SensorReading) -> TriggeredRule:
    """Significant deviation from personal HR baseline."""
    hr = reading.heart_rate
    baseline = BASELINE["heart_rate_bpm"]
    dev_threshold = BASE_DEV["hr_significant_bpm"]

    dev = abs(hr - baseline) if hr is not None else 0
    triggered = hr is not None and dev >= dev_threshold

    return _make_rule(
        rule_id="BASELINE_HR_DEV_001",
        rule_name="Significant HR Baseline Deviation",
        description="Heart rate deviates significantly from personal baseline.",
        severity=Severity.LOW,
        triggered=triggered,
        reason=(
            f"HR {hr} bpm deviates {dev} bpm from personal baseline {baseline} bpm "
            f"(threshold: {dev_threshold} bpm)."
            if triggered else "HR within acceptable deviation from baseline."
        ),
        evidence={"heart_rate": hr, "baseline": baseline, "deviation": dev, "threshold": dev_threshold},
        score=5 if triggered else 0,
    )
