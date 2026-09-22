"""
cause_agent.py — AI Agent 1: Possible Cause Analysis.

Receives a structured RiskEvent and asks the LLM to identify plausible
explanations. The model MUST NOT diagnose. It distinguishes:
  - possible explanation
  - candidate pattern
  - NOT a confirmed diagnosis

Output is a structured CauseAnalysisResult (validated JSON).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.models.ai_models import CauseAnalysisResult, PossibleCause
from app.models.risk_models import RiskEvent
from app.ai.llm_client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI assistant for a health monitoring prototype system.
You are NOT a doctor and you CANNOT diagnose any medical condition.
Your role is to analyze sensor patterns and suggest possible explanations,
NOT confirmed diagnoses.

IMPORTANT RULES:
1. Use language like: "possible", "may be consistent with", "candidate explanation", "requires further evaluation".
2. NEVER say "You have [disease]" or "You are experiencing [condition]".
3. Consider sensor quality, activity context, altitude, and environmental factors.
4. Always consider alternative explanations including sensor artifacts.
5. Output ONLY valid JSON matching the schema below. No additional text.

OUTPUT SCHEMA (respond with ONLY this JSON structure):
{
  "event_interpretation": "Brief summary of the detected pattern",
  "possible_causes": [
    {
      "cause": "Name of possible explanation",
      "supporting_evidence": ["evidence 1", "evidence 2"],
      "contradicting_evidence": ["counter 1"],
      "confidence": 0.0
    }
  ],
  "alternative_explanations": ["explanation 1", "explanation 2"],
  "missing_information": ["what data would help clarify"],
  "recommended_validation_checks": ["check 1", "check 2"]
}

Confidence values must be between 0.0 and 1.0.
Include 2-4 possible causes ordered from most to least likely.
"""


class CauseAgent:
    """AI Agent 1 — analyzes a RiskEvent and produces a CauseAnalysisResult."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    def analyze(self, event: RiskEvent) -> CauseAnalysisResult:
        """
        Analyze the risk event and produce possible causes.
        """
        if not self._client.is_available():
            logger.warning("Agent 1 skipped — LM Studio unavailable.")
            return CauseAnalysisResult(
                event_interpretation="AI analysis skipped — LM Studio unavailable.",
                llm_unavailable=True,
                parse_success=False,
            )

        user_prompt = self._build_prompt(event)
        logger.info("Agent 1: sending request for event_id=%s", event.event_id)

        result = self._client.chat(SYSTEM_PROMPT, user_prompt, expect_json=True)

        if result["unavailable"]:
            return CauseAnalysisResult(
                event_interpretation="AI analysis skipped — LM Studio unavailable.",
                llm_unavailable=True,
                parse_success=False,
            )

        if not result["success"] or result["json_data"] is None:
            logger.warning(
                "Agent 1: JSON parse failed. Error: %s. Raw: %s",
                result["error"],
                (result["raw_text"] or "")[:300],
            )
            return CauseAnalysisResult(
                event_interpretation="AI parse failed.",
                raw_response=result["raw_text"],
                parse_success=False,
                error_message=result["error"],
            )

        return self._parse_response(result["json_data"], result["raw_text"])

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_prompt(self, event: RiskEvent) -> str:
        triggered_summaries = []
        for rule in event.triggered_rules:
            triggered_summaries.append(
                f"  - [{rule.rule_id}] {rule.rule_name}: {rule.reason}"
            )

        triggered_text = "\n".join(triggered_summaries) if triggered_summaries else "  - None"

        prompt = f"""HEALTH MONITORING SYSTEM — RISK EVENT ANALYSIS

Event ID: {event.event_id}
Risk Level: {event.risk_level}
Risk Score: {event.risk_score}/100
Activity State: {event.activity_state}
Persistence: {event.persistence_count} consecutive abnormal readings

SENSOR READINGS:
  Heart Rate:            {event.sensor_snapshot.get('heart_rate')} bpm
  SpO2:                  {event.sensor_snapshot.get('spo2')} %
  Body Temperature:      {event.sensor_snapshot.get('body_temperature')} °C
  Environment Temp:      {event.sensor_snapshot.get('environment_temperature')} °C
  Humidity:              {event.sensor_snapshot.get('humidity')} %
  Altitude:              {event.sensor_snapshot.get('altitude')} m
  Atmospheric Pressure:  {event.environment_context.get('pressure')} hPa
  Accel Magnitude:       {event.sensor_snapshot.get('acceleration_magnitude')} g

PERSONAL BASELINE:
  Resting HR:      {event.baseline.get('heart_rate_bpm')} bpm
  SpO2:            {event.baseline.get('spo2_pct')} %
  Body Temp:       {event.baseline.get('body_temperature_c')} °C

TRIGGERED RULES:
{triggered_text}

ALTITUDE CONTEXT: {event.altitude_context_note or 'N/A'}

Analyze the above pattern and respond with ONLY the JSON structure requested.
Do NOT diagnose. Use hedged, candidate-explanation language.
"""
        return prompt

    def _parse_response(
        self,
        data: Dict,
        raw: str,
    ) -> CauseAnalysisResult:
        try:
            causes = []
            for c in data.get("possible_causes", []):
                causes.append(
                    PossibleCause(
                        cause=c.get("cause", ""),
                        supporting_evidence=c.get("supporting_evidence", []),
                        contradicting_evidence=c.get("contradicting_evidence", []),
                        confidence=float(c.get("confidence", 0.0)),
                    )
                )

            return CauseAnalysisResult(
                event_interpretation=data.get("event_interpretation", ""),
                possible_causes=causes,
                alternative_explanations=data.get("alternative_explanations", []),
                missing_information=data.get("missing_information", []),
                recommended_validation_checks=data.get("recommended_validation_checks", []),
                raw_response=raw,
                parse_success=True,
            )
        except Exception as e:
            logger.error("Agent 1: error parsing structured response: %s", e)
            return CauseAnalysisResult(
                event_interpretation="AI response structure invalid.",
                raw_response=raw,
                parse_success=False,
                error_message=str(e),
            )
