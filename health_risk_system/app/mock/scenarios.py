"""
scenarios.py — Eight realistic mock scenarios for the health risk monitoring prototype.

Each scenario contains multiple SensorReading snapshots over time, simulating
a wearable stream. Readings are deterministic — they are not randomly generated.

NOTE: These are synthetic data for prototype/demonstration purposes only.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from app.models.sensor_models import SensorReading, SensorReadingSequence


def _ts(base: datetime, offset_seconds: int) -> datetime:
    return base + timedelta(seconds=offset_seconds)


# ---------------------------------------------------------------------------
# Scenario 1 — Normal Rest
# Expected: NORMAL, no AI call
# ---------------------------------------------------------------------------
def scenario_1_normal_rest() -> SensorReadingSequence:
    base = datetime(2026, 9, 22, 8, 0, 0)
    readings = [
        SensorReading(
            timestamp=_ts(base, i * 10),
            reading_id=f"S1-R{i+1}",
            heart_rate=72.0 + (i * 0.1),
            spo2=98.0,
            body_temperature=36.7,
            environment_temperature=25.0,
            humidity=55.0,
            altitude=50.0,
            atmospheric_pressure=1012.0,
            acceleration_x=0.01,
            acceleration_y=0.02,
            acceleration_z=0.98,
            previous_altitude=50.0 if i > 0 else None,
            previous_pressure=1012.0 if i > 0 else None,
        )
        for i in range(5)
    ]
    return SensorReadingSequence(
        scenario_id=1,
        scenario_name="Normal Rest",
        description="User resting at home. All vitals within normal ranges.",
        readings=readings,
        expected_outcome="NORMAL — No risk event, no AI call.",
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Normal Exercise
# Expected: NORMAL_PHYSIOLOGICAL_ACTIVITY, no AI call
# ---------------------------------------------------------------------------
def scenario_2_normal_exercise() -> SensorReadingSequence:
    base = datetime(2026, 9, 22, 9, 0, 0)
    hrs = [80, 110, 130, 145, 148]
    accs = [
        (0.3, 1.2, 0.9),
        (0.8, 2.1, 1.1),
        (1.2, 2.8, 1.4),
        (1.5, 3.1, 1.6),
        (1.4, 3.0, 1.5),
    ]
    readings = [
        SensorReading(
            timestamp=_ts(base, i * 15),
            reading_id=f"S2-R{i+1}",
            heart_rate=float(hrs[i]),
            spo2=97.0,
            body_temperature=36.9 + i * 0.1,
            environment_temperature=24.0,
            humidity=50.0,
            altitude=55.0,
            atmospheric_pressure=1011.5,
            acceleration_x=accs[i][0],
            acceleration_y=accs[i][1],
            acceleration_z=accs[i][2],
            previous_altitude=55.0 if i > 0 else None,
            previous_pressure=1011.5 if i > 0 else None,
        )
        for i in range(5)
    ]
    return SensorReadingSequence(
        scenario_id=2,
        scenario_name="Normal Exercise",
        description="User jogging. Elevated HR with matching high accelerometer activity.",
        readings=readings,
        expected_outcome="NORMAL_PHYSIOLOGICAL_ACTIVITY — Elevated HR expected during running. No AI call.",
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Elevated Resting Heart Rate
# Expected: RISK EVENT → Agent 1 → Validation → Agent 2
# ---------------------------------------------------------------------------
def scenario_3_elevated_resting_hr() -> SensorReadingSequence:
    base = datetime(2026, 9, 22, 10, 0, 0)
    hrs = [108, 112, 116, 119, 121]
    readings = [
        SensorReading(
            timestamp=_ts(base, i * 30),
            reading_id=f"S3-R{i+1}",
            heart_rate=float(hrs[i]),
            spo2=97.0,
            body_temperature=36.9,
            environment_temperature=24.0,
            humidity=52.0,
            altitude=45.0,
            atmospheric_pressure=1013.0,
            acceleration_x=0.01,
            acceleration_y=0.02,
            acceleration_z=0.99,
            previous_altitude=45.0 if i > 0 else None,
            previous_pressure=1013.0 if i > 0 else None,
        )
        for i in range(5)
    ]
    return SensorReadingSequence(
        scenario_id=3,
        scenario_name="Elevated Resting Heart Rate",
        description="User at rest with persistently elevated HR (108–121 bpm). Low movement confirms rest state.",
        readings=readings,
        expected_outcome="RISK EVENT — Resting tachycardia candidate. AI analysis triggered.",
    )


# ---------------------------------------------------------------------------
# Scenario 4 — Low SpO2
# Expected: HIGH/CRITICAL candidate → Agent 1 → Validation → Agent 2
# ---------------------------------------------------------------------------
def scenario_4_low_spo2() -> SensorReadingSequence:
    base = datetime(2026, 9, 22, 11, 0, 0)
    spo2_vals = [92.0, 91.0, 90.5, 89.5, 88.0]
    readings = [
        SensorReading(
            timestamp=_ts(base, i * 20),
            reading_id=f"S4-R{i+1}",
            heart_rate=78.0 + i,
            spo2=spo2_vals[i],
            body_temperature=36.8,
            environment_temperature=23.0,
            humidity=48.0,
            altitude=80.0,
            atmospheric_pressure=1010.0,
            acceleration_x=0.02,
            acceleration_y=0.01,
            acceleration_z=0.97,
            previous_altitude=80.0 if i > 0 else None,
            previous_pressure=1010.0 if i > 0 else None,
        )
        for i in range(5)
    ]
    return SensorReadingSequence(
        scenario_id=4,
        scenario_name="Low SpO2",
        description="User at rest with progressively declining SpO2 (92% → 88%). Persistent over multiple readings.",
        readings=readings,
        expected_outcome="CRITICAL/HIGH candidate — Possible low oxygen pattern. AI analysis triggered.",
    )


# ---------------------------------------------------------------------------
# Scenario 5 — Heat Stress
# Expected: POSSIBLE_HEAT_STRESS event → Agent 1 → Validation → Agent 2
# ---------------------------------------------------------------------------
def scenario_5_heat_stress() -> SensorReadingSequence:
    base = datetime(2026, 9, 22, 13, 0, 0)
    hrs = [95, 102, 108, 112, 115]
    accs = [
        (0.4, 1.5, 0.8),
        (0.5, 1.8, 0.9),
        (0.6, 2.0, 1.0),
        (0.5, 1.9, 0.9),
        (0.4, 1.7, 0.8),
    ]
    body_temps = [37.2, 37.5, 37.8, 38.0, 38.2]
    readings = [
        SensorReading(
            timestamp=_ts(base, i * 60),
            reading_id=f"S5-R{i+1}",
            heart_rate=float(hrs[i]),
            spo2=96.0,
            body_temperature=body_temps[i],
            environment_temperature=38.0,
            humidity=82.0,
            altitude=30.0,
            atmospheric_pressure=1010.5,
            acceleration_x=accs[i][0],
            acceleration_y=accs[i][1],
            acceleration_z=accs[i][2],
            previous_altitude=30.0 if i > 0 else None,
            previous_pressure=1010.5 if i > 0 else None,
        )
        for i in range(5)
    ]
    return SensorReadingSequence(
        scenario_id=5,
        scenario_name="Heat Stress",
        description="User active outdoors. Env temp 38°C, humidity 82%, rising body temp and HR.",
        readings=readings,
        expected_outcome="POSSIBLE_HEAT_STRESS event. AI analysis triggered.",
    )


# ---------------------------------------------------------------------------
# Scenario 6 — Elevated Temperature + Resting HR (Possible Illness Pattern)
# Expected: Possible illness/physiological stress pattern → AI
# ---------------------------------------------------------------------------
def scenario_6_illness_pattern() -> SensorReadingSequence:
    base = datetime(2026, 9, 22, 14, 0, 0)
    hrs = [95, 98, 100, 102, 104]
    body_temps = [38.0, 38.1, 38.3, 38.4, 38.5]
    readings = [
        SensorReading(
            timestamp=_ts(base, i * 30),
            reading_id=f"S6-R{i+1}",
            heart_rate=float(hrs[i]),
            spo2=96.5,
            body_temperature=body_temps[i],
            environment_temperature=22.0,
            humidity=45.0,
            altitude=40.0,
            atmospheric_pressure=1012.0,
            acceleration_x=0.01,
            acceleration_y=0.02,
            acceleration_z=0.98,
            previous_altitude=40.0 if i > 0 else None,
            previous_pressure=1012.0 if i > 0 else None,
        )
        for i in range(5)
    ]
    return SensorReadingSequence(
        scenario_id=6,
        scenario_name="Elevated Temperature + Resting HR",
        description="User resting with fever-candidate body temperature and mildly elevated HR.",
        readings=readings,
        expected_outcome="Possible illness/physiological stress pattern. AI analysis triggered.",
    )


# ---------------------------------------------------------------------------
# Scenario 7 — Possible Fall
# Simulates: normal activity → sudden impact → immobility
# Expected: POSSIBLE_FALL → HIGH risk event → AI
# ---------------------------------------------------------------------------
def scenario_7_possible_fall() -> SensorReadingSequence:
    base = datetime(2026, 9, 22, 15, 0, 0)
    # Pre-fall normal walking
    pre_fall = [
        SensorReading(
            timestamp=_ts(base, 0),
            reading_id="S7-R1",
            heart_rate=80.0,
            spo2=97.5,
            body_temperature=36.8,
            environment_temperature=22.0,
            humidity=50.0,
            altitude=42.0,
            atmospheric_pressure=1012.0,
            acceleration_x=0.3,
            acceleration_y=1.8,
            acceleration_z=0.9,
        ),
        SensorReading(
            timestamp=_ts(base, 10),
            reading_id="S7-R2",
            heart_rate=82.0,
            spo2=97.5,
            body_temperature=36.8,
            environment_temperature=22.0,
            humidity=50.0,
            altitude=42.0,
            atmospheric_pressure=1012.0,
            acceleration_x=0.4,
            acceleration_y=1.9,
            acceleration_z=0.9,
            previous_altitude=42.0,
            previous_pressure=1012.0,
        ),
    ]
    # Impact reading — sudden very high acceleration
    impact = SensorReading(
        timestamp=_ts(base, 20),
        reading_id="S7-R3-IMPACT",
        heart_rate=90.0,
        spo2=97.0,
        body_temperature=36.8,
        environment_temperature=22.0,
        humidity=50.0,
        altitude=42.0,
        atmospheric_pressure=1012.0,
        acceleration_x=5.2,
        acceleration_y=7.8,
        acceleration_z=4.1,
        previous_altitude=42.0,
        previous_pressure=1012.0,
    )
    # Post-fall immobility
    post_fall = [
        SensorReading(
            timestamp=_ts(base, 30 + i * 10),
            reading_id=f"S7-R{i+4}-POST",
            heart_rate=92.0,
            spo2=97.0,
            body_temperature=36.8,
            environment_temperature=22.0,
            humidity=50.0,
            altitude=42.0,
            atmospheric_pressure=1012.0,
            acceleration_x=0.05,
            acceleration_y=0.08,
            acceleration_z=0.95,
            previous_altitude=42.0,
            previous_pressure=1012.0,
        )
        for i in range(3)
    ]
    readings = pre_fall + [impact] + post_fall
    return SensorReadingSequence(
        scenario_id=7,
        scenario_name="Possible Fall",
        description="User walking, sudden high-acceleration impact event, followed by near-zero movement (immobility).",
        readings=readings,
        expected_outcome="POSSIBLE_FALL — HIGH risk event. AI analysis triggered.",
    )


# ---------------------------------------------------------------------------
# Scenario 8 — High Altitude with SpO2 Decrease
# Expected: Altitude context noted; SpO2 interpretation contextualized
# ---------------------------------------------------------------------------
def scenario_8_high_altitude() -> SensorReadingSequence:
    base = datetime(2026, 9, 22, 6, 0, 0)
    altitudes  = [500,  1200, 1800, 2600, 3200]
    pressures  = [1000,  878,  815,  745,  695]
    spo2_vals  = [98.0, 96.5, 95.0, 93.5, 92.0]
    hrs        = [72,    76,   80,   85,   90]
    readings = [
        SensorReading(
            timestamp=_ts(base, i * 300),
            reading_id=f"S8-R{i+1}",
            heart_rate=float(hrs[i]),
            spo2=spo2_vals[i],
            body_temperature=36.5,
            environment_temperature=12.0 - i * 1.5,
            humidity=40.0 - i * 2.0,
            altitude=float(altitudes[i]),
            atmospheric_pressure=float(pressures[i]),
            acceleration_x=0.1,
            acceleration_y=0.3,
            acceleration_z=0.95,
            previous_altitude=float(altitudes[i - 1]) if i > 0 else None,
            previous_pressure=float(pressures[i - 1]) if i > 0 else None,
        )
        for i in range(5)
    ]
    return SensorReadingSequence(
        scenario_id=8,
        scenario_name="High Altitude SpO2 Decrease",
        description="User ascending to ~3200 m. Pressure drops, SpO2 gradually declines. Altitude context applied.",
        readings=readings,
        expected_outcome="Altitude context included. SpO2 interpretation contextualized. AI analysis if threshold crossed.",
    )


# ---------------------------------------------------------------------------
# Public API — returns all scenarios in order
# ---------------------------------------------------------------------------
ALL_SCENARIOS: List[SensorReadingSequence] = [
    scenario_1_normal_rest(),
    scenario_2_normal_exercise(),
    scenario_3_elevated_resting_hr(),
    scenario_4_low_spo2(),
    scenario_5_heat_stress(),
    scenario_6_illness_pattern(),
    scenario_7_possible_fall(),
    scenario_8_high_altitude(),
]
