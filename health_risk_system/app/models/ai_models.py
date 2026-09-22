"""
ai_models.py — Data models for AI agent inputs and outputs.

Agent 1: Cause analysis
Agent 2: Precaution recommendation
Validation: Cause validator result
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agent 1 — Cause Analysis
# ---------------------------------------------------------------------------

class PossibleCause(BaseModel):
    cause: str
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class CauseAnalysisResult(BaseModel):
    """Structured output from AI Agent 1."""
    event_interpretation: str = ""
    possible_causes: List[PossibleCause] = Field(default_factory=list)
    alternative_explanations: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    recommended_validation_checks: List[str] = Field(default_factory=list)
    # Internal metadata
    raw_response: Optional[str] = None
    parse_success: bool = True
    error_message: Optional[str] = None
    llm_unavailable: bool = False


# ---------------------------------------------------------------------------
# Cause Validator
# ---------------------------------------------------------------------------

class CauseValidationStatus(str):
    SUPPORTED            = "SUPPORTED"
    PARTIALLY_SUPPORTED  = "PARTIALLY_SUPPORTED"
    NOT_SUPPORTED        = "NOT_SUPPORTED"
    INSUFFICIENT_DATA    = "INSUFFICIENT_DATA"


class ValidatedCause(BaseModel):
    cause: str
    confidence: float
    validation_status: str       # CauseValidationStatus values
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    passed_to_agent2: bool = False
    validation_notes: List[str] = Field(default_factory=list)


class CauseValidationResult(BaseModel):
    validated_causes: List[ValidatedCause] = Field(default_factory=list)
    passed_causes: List[ValidatedCause] = Field(default_factory=list)
    rejected_causes: List[ValidatedCause] = Field(default_factory=list)
    validation_summary: str = ""


# ---------------------------------------------------------------------------
# Agent 2 — Precaution Recommendation
# ---------------------------------------------------------------------------

class PrecautionResult(BaseModel):
    """Structured output from AI Agent 2."""
    condition_summary: str = ""
    immediate_precautions: List[str] = Field(default_factory=list)
    monitoring_steps: List[str] = Field(default_factory=list)
    escalation_conditions: List[str] = Field(default_factory=list)
    emergency_warning: bool = False
    reasoning: str = ""
    # Internal metadata
    raw_response: Optional[str] = None
    parse_success: bool = True
    error_message: Optional[str] = None
    llm_unavailable: bool = False
