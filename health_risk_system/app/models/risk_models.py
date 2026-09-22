"""
risk_models.py — Data models for the risk detection pipeline stages.

Covers:
  - ValidationResult
  - TriggeredRule
  - RiskScore
  - RiskEvent
  - FallDetectionState (mutable tracking state)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ActivityState(str, Enum):
    REST          = "REST"
    WALKING       = "WALKING"
    RUNNING       = "RUNNING"
    HIGH_ACTIVITY = "HIGH_ACTIVITY"
    POSSIBLE_FALL = "POSSIBLE_FALL"
    UNKNOWN       = "UNKNOWN"


class RiskLevel(str, Enum):
    NORMAL   = "NORMAL"
    LOW      = "LOW"
    MODERATE = "MODERATE"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class Severity(str, Enum):
    INFO     = "INFO"
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class ValidationStatus(str, Enum):
    VALID   = "VALID"
    INVALID = "INVALID"
    PARTIAL = "PARTIAL"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    valid: bool
    status: ValidationStatus = ValidationStatus.VALID
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    rejected_fields: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule engine output
# ---------------------------------------------------------------------------

class TriggeredRule(BaseModel):
    rule_id: str
    rule_name: str
    description: str
    severity: Severity
    triggered: bool
    reason: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    score_contribution: int = 0     # how much this rule adds to risk score


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------

class RiskScore(BaseModel):
    score: int = 0                                         # 0-100
    risk_level: RiskLevel = RiskLevel.NORMAL
    contributing_rules: List[str] = Field(default_factory=list)
    breakdown: Dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Risk event  —  the unit passed to the AI agents
# ---------------------------------------------------------------------------

class RiskEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    scenario_id: Optional[int] = None
    scenario_name: Optional[str] = None

    risk_score: int
    risk_level: RiskLevel
    activity_state: str

    triggered_rules: List[TriggeredRule]
    sensor_snapshot: Dict[str, Any] = Field(default_factory=dict)
    baseline: Dict[str, Any] = Field(default_factory=dict)
    environment_context: Dict[str, Any] = Field(default_factory=dict)

    # How many consecutive abnormal readings contributed
    persistence_count: int = 1
    duration_seconds: Optional[float] = None

    # Altitude context flag
    high_altitude: bool = False
    altitude_context_note: Optional[str] = None


# ---------------------------------------------------------------------------
# Fall detection state tracker
# ---------------------------------------------------------------------------

class FallDetectionState(BaseModel):
    """Mutable state machine for fall detection across readings."""
    impact_detected: bool = False
    impact_magnitude: float = 0.0
    post_impact_readings: int = 0
    pre_impact_magnitude: float = 0.0
    fall_confirmed: bool = False    # We never confirm – only suggest

    def reset(self) -> None:
        self.impact_detected = False
        self.impact_magnitude = 0.0
        self.post_impact_readings = 0
        self.pre_impact_magnitude = 0.0
        self.fall_confirmed = False
