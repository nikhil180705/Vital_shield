"""
precaution_agent.py — AI Agent 2: Precaution Recommendation.

Receives:
  - risk event
  - validated causes (from cause validator)
  - supporting evidence

Outputs conservative, safe, non-diagnostic precautionary guidance.

STRICT SAFETY CONSTRAINTS:
  - Must NOT prescribe medication
  - Must NOT diagnose disease
  - Must NOT invent symptoms
  - Must NOT invent measurements
  - Must NOT claim certainty
  - Must recommend professional evaluation when appropriate
"""

from __future__ import annotations

import logging
from typing import List

from app.models.ai_models import (
    CauseValidationResult,
    PrecautionResult,
    ValidatedCause,
)
from app.models.risk_models import RiskEvent, RiskLevel
from app.ai.llm_client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI assistant for a health monitoring wearable prototype.
You provide conservative, non-diagnostic safety precaution guidance.

STRICT RULES:
1. Do NOT prescribe any medication.
2. Do NOT diagnose any disease or condition.
3. Do NOT invent symptoms not mentioned in the data.
4. Do NOT invent sensor measurements.
5. Do NOT express certainty about medical conditions.
6. Always use language like "may", "could", "consider", "it may be advisable".
7. Always recommend professional medical evaluation for significant events.
8. If there is any possibility of emergency, explicitly recommend calling emergency services.
9. Output ONLY valid JSON matching the schema below. No additional text.

OUTPUT SCHEMA (respond with ONLY this JSON structure):
{
  "condition_summary": "Brief non-diagnostic description of the detected pattern",
  "immediate_precautions": ["precaution 1", "precaution 2"],
  "monitoring_steps": ["monitoring step 1", "monitoring step 2"],
  "escalation_conditions": ["condition that warrants emergency/medical contact"],
  "emergency_warning": false,
  "reasoning": "Brief explanation of why these precautions are recommended"
}

emergency_warning must be true if the detected pattern may indicate a time-sensitive emergency.
"""


class PrecautionAgent:
    """AI Agent 2 — generates precautionary guidance from validated causes."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    def recommend(
        self,
        event: RiskEvent,
        validation_result: CauseValidationResult,
    ) -> PrecautionResult:
        """
        Generate precautionary recommendations.
        """
        if not self._client.is_available():
            logger.warning("Agent 2 skipped — LM Studio unavailable.")
            return PrecautionResult(
                condition_summary="Precaution analysis skipped — LM Studio unavailable.",
                llm_unavailable=True,
                parse_success=False,
            )

        if not validation_result.passed_causes:
            logger.info("Agent 2: no validated causes to act on.")
            return PrecautionResult(
                condition_summary=(
                    "No validated causes available. "
                    "Rule engine detected an anomaly, but AI could not confirm a cause pattern."
                ),
                immediate_precautions=["Monitor the situation.", "Rest if possible."],
                monitoring_steps=["Continue observing readings over the next few minutes."],
                escalation_conditions=["Symptoms worsen or readings deteriorate significantly."],
                emergency_warning=False,
                reasoning="Cause validator did not pass any causes to this agent.",
                parse_success=True,
            )

        user_prompt = self._build_prompt(event, validation_result.passed_causes)
        logger.info("Agent 2: sending request for event_id=%s", event.event_id)

        result = self._client.chat(SYSTEM_PROMPT, user_prompt, expect_json=True)

        if result["unavailable"]:
            return PrecautionResult(
                condition_summary="Precaution analysis skipped — LM Studio unavailable.",
                llm_unavailable=True,
                parse_success=False,
            )

        if not result["success"] or result["json_data"] is None:
            logger.warning(
                "Agent 2: JSON parse failed. Error: %s", result["error"]
            )
            return PrecautionResult(
                condition_summary="Precaution analysis could not be parsed.",
                raw_response=result["raw_text"],
                parse_success=False,
                error_message=result["error"],
            )

        return self._parse_response(result["json_data"], result["raw_text"])

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_prompt(
        self,
        event: RiskEvent,
        passed_causes: List[ValidatedCause],
    ) -> str:
        cause_lines = []
        for vc in passed_causes:
            cause_lines.append(f"  • {vc.cause} (confidence: {vc.confidence:.2f}, validation: {vc.validation_status})")
            for e in vc.supporting_evidence[:3]:
                cause_lines.append(f"      Evidence: {e}")

        cause_text = "\n".join(cause_lines) if cause_lines else "  None"

        fall_involved = event.activity_state == "POSSIBLE_FALL"
        critical = event.risk_level == RiskLevel.CRITICAL

        prompt = f"""HEALTH MONITORING SYSTEM — PRECAUTION RECOMMENDATION REQUEST

Risk Level: {event.risk_level}
Risk Score: {event.risk_score}/100
Activity State: {event.activity_state}
{'⚠ POSSIBLE FALL EVENT INVOLVED' if fall_involved else ''}
{'⚠ CRITICAL RISK LEVEL' if critical else ''}

SENSOR READINGS:
  Heart Rate:       {event.sensor_snapshot.get('heart_rate')} bpm
  SpO2:             {event.sensor_snapshot.get('spo2')} %
  Body Temperature: {event.sensor_snapshot.get('body_temperature')} °C
  Environment Temp: {event.sensor_snapshot.get('environment_temperature')} °C
  Humidity:         {event.sensor_snapshot.get('humidity')} %
  Altitude:         {event.sensor_snapshot.get('altitude')} m

VALIDATED CAUSES (passed by deterministic validator):
{cause_text}

ALTITUDE CONTEXT: {event.altitude_context_note or 'Not applicable'}

Generate conservative, non-diagnostic precautionary guidance.
Respond ONLY with the JSON structure requested.
Do NOT diagnose. Do NOT prescribe medication. Do NOT invent data.
"""
        return prompt

    def _parse_response(self, data: dict, raw: str) -> PrecautionResult:
        try:
            return PrecautionResult(
                condition_summary=data.get("condition_summary", ""),
                immediate_precautions=data.get("immediate_precautions", []),
                monitoring_steps=data.get("monitoring_steps", []),
                escalation_conditions=data.get("escalation_conditions", []),
                emergency_warning=bool(data.get("emergency_warning", False)),
                reasoning=data.get("reasoning", ""),
                raw_response=raw,
                parse_success=True,
            )
        except Exception as e:
            logger.error("Agent 2: error parsing response: %s", e)
            return PrecautionResult(
                condition_summary="Precaution response parsing failed.",
                raw_response=raw,
                parse_success=False,
                error_message=str(e),
            )
