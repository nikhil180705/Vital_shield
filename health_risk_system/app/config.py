"""
config.py — Central configuration for the Health Risk Monitoring System.

All thresholds here are:
    SCREENING / PROTOTYPE THRESHOLDS
    NOT MEDICAL DIAGNOSTIC LIMITS

They are tunable engineering parameters for the prototype only.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# LM Studio configuration
# ---------------------------------------------------------------------------
LM_STUDIO_BASE_URL: str = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
LM_STUDIO_MODEL: str = os.getenv("LM_STUDIO_MODEL", "qwen2.5-3b-instruct")
LM_STUDIO_API_KEY: str = "lm-studio"          # dummy key – local model only
LM_STUDIO_TIMEOUT: int = int(os.getenv("LM_STUDIO_TIMEOUT", "180"))
LM_STUDIO_MAX_TOKENS: int = int(os.getenv("LM_STUDIO_MAX_TOKENS", "1024"))
LM_STUDIO_TEMPERATURE: float = float(os.getenv("LM_STUDIO_TEMPERATURE", "0.2"))

# ---------------------------------------------------------------------------
# Persistence configuration (consecutive abnormal readings required before
# promoting a monitor state to a risk event)
# ---------------------------------------------------------------------------
PERSISTENCE = {
    "monitor_threshold": 1,      # readings before MONITOR
    "risk_threshold": 3,         # readings before RISK EVENT
}

# ---------------------------------------------------------------------------
# Personal baseline (prototype defaults – would be user-calibrated in prod)
# ---------------------------------------------------------------------------
BASELINE = {
    "heart_rate_bpm": 72,
    "spo2_pct": 98.0,
    "body_temperature_c": 36.8,
    "systolic_bp_mmhg": 120,
}

# ---------------------------------------------------------------------------
# SCREENING / PROTOTYPE THRESHOLDS  –  NOT MEDICAL DIAGNOSTIC LIMITS
# ---------------------------------------------------------------------------
THRESHOLDS = {
    "heart_rate": {
        "low_monitoring": 50,
        "low_risk": 49,
        "resting_normal_min": 60,
        "resting_normal_max": 100,
        "elevated": 101,
        "high": 111,
        "high_risk": 120,           # at REST
        "severe_risk": 140,
        "exercise_high_risk": 185,  # during vigorous exercise
    },
    "spo2": {
        "normal_min": 95.0,
        "monitor": 93.0,
        "high_risk": 92.0,
        "critical": 90.0,
        # Altitude adjustment – above this altitude SpO2 screening bands widen
        "altitude_adjustment_threshold_m": 2000,
    },
    "body_temperature": {
        "normal_min": 35.5,
        "normal_max": 37.3,
        "elevated": 37.4,
        "fever_candidate": 38.0,
        "high": 39.0,
        "severe": 40.0,
    },
    "environment_temperature": {
        "cold": 10.0,
        "comfortable_max": 27.0,
        "warm": 30.0,
        "hot": 35.0,
        "extreme": 40.0,
    },
    "humidity": {
        "low": 20.0,
        "comfortable_max": 60.0,
        "high": 70.0,
        "very_high": 80.0,
    },
    "pressure": {
        "normal_sea_level": 1013.25,   # hPa
        "low_concern": 980.0,
        "high_concern": 1040.0,
    },
    "altitude": {
        "low": 0,
        "moderate": 1500,
        "high": 2500,
        "very_high": 3500,
        "extreme": 5000,
    },
    "acceleration": {
        # g units  (magnitude ~ 1.0 at rest)
        "rest_max": 1.5,
        "walking_max": 2.5,
        "running_max": 4.0,
        "fall_impact_min": 3.5,      # sudden spike indicating possible impact
        "post_fall_max": 1.2,        # low movement after possible impact
    },
    "baseline_deviation": {
        "hr_significant_bpm": 20,
        "spo2_significant_pct": 3.0,
        "temp_significant_c": 0.8,
    },
    # Heat-stress composite thresholds
    "heat_stress": {
        "env_temp_trigger": 32.0,
        "humidity_trigger": 65.0,
        "body_temp_trigger": 37.5,
        "hr_trigger_rest": 100,
    },
}

# ---------------------------------------------------------------------------
# Risk score bands  –  ENGINEERING CATEGORIES for prototype only
# ---------------------------------------------------------------------------
RISK_SCORE_BANDS = {
    "NORMAL":   (0,  20),
    "LOW":      (21, 40),
    "MODERATE": (41, 60),
    "HIGH":     (61, 80),
    "CRITICAL": (81, 100),
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", "health_risk_system.log")
