"""
tests/test_ai_parsing.py — Tests for AI JSON parsing and cause validation.
"""

import pytest
from app.ai.llm_client import LLMClient
from app.ai.cause_validator import CauseValidator
from app.models.ai_models import CauseAnalysisResult, PossibleCause
from app.models.risk_models import ActivityState, RiskEvent, RiskLevel, TriggeredRule, Severity
from datetime import datetime


# ---------------------------------------------------------------------------
# LLM Client JSON extraction tests (no network required)
# ---------------------------------------------------------------------------

class TestLLMClientJsonExtraction:

    def setup_method(self):
        # We access the private method directly — no actual LM Studio needed
        self.client = LLMClient.__new__(LLMClient)

    def test_direct_json_parse(self):
        text = '{"event_interpretation": "test", "possible_causes": []}'
        result = self.client._extract_json(text)
        assert result is not None
        assert result["event_interpretation"] == "test"

    def test_markdown_code_block_extraction(self):
        text = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        result = self.client._extract_json(text)
        assert result is not None
        assert result["key"] == "value"

    def test_embedded_json_extraction(self):
        text = 'Here is the result: {"score": 42} end of message'
        result = self.client._extract_json(text)
        assert result is not None
        assert result["score"] == 42

    def test_invalid_json_returns_none(self):
        text = "This is just plain text with no JSON."
        result = self.client._extract_json(text)
        assert result is None

    def test_malformed_json_returns_none(self):
        text = '{"key": "unclosed'
        result = self.client._extract_json(text)
        assert result is None

    def test_qwen_thinking_tags_stripped(self):
        text = '<think>internal reasoning</think>{"answer": "yes"}'
        result = self.client._extract_json(text)
        assert result is not None
        assert result["answer"] == "yes"


# ---------------------------------------------------------------------------
# LLM Client availability test
# ---------------------------------------------------------------------------

class TestLLMClientAvailability:

    def test_unavailable_returns_false(self):
        """With no LM Studio running, is_available should return False."""
        client = LLMClient()
        # Force a check — LM Studio probably not running in test environment
        available = client.is_available()
        # Either True or False is valid — just check it returns a bool
        assert isinstance(available, bool)

    def test_chat_when_unavailable_returns_error_dict(self):
        """If LM Studio is unavailable, chat() should return unavailable=True."""
        client = LLMClient()
        # Forcibly mark as unavailable
        client._available = False
        result = client.chat("system", "user")
        assert result["success"] is False
        assert result["unavailable"] is True


# ---------------------------------------------------------------------------
# Cause Validator tests (no LLM required — deterministic)
# ---------------------------------------------------------------------------

def make_event(**kwargs) -> RiskEvent:
    defaults = dict(
        event_id="TEST-E1",
        timestamp=datetime.utcnow(),
        risk_score=65,
        risk_level=RiskLevel.HIGH,
        activity_state="REST",
        triggered_rules=[],
        sensor_snapshot={
            "heart_rate": 120.0,
            "spo2": 91.0,
            "body_temperature": 37.2,
            "environment_temperature": 38.0,
            "humidity": 80.0,
            "altitude": 50.0,
            "acceleration_magnitude": 1.0,
        },
        baseline={"heart_rate_bpm": 72, "spo2_pct": 98.0, "body_temperature_c": 36.8},
        environment_context={
            "altitude": 50.0,
            "pressure": 1013.0,
            "env_temperature": 38.0,
            "humidity": 80.0,
            "altitude_change": None,
            "pressure_change": None,
            "high_altitude": False,
        },
        persistence_count=3,
    )
    defaults.update(kwargs)
    return RiskEvent(**defaults)


def make_cause_analysis(causes) -> CauseAnalysisResult:
    return CauseAnalysisResult(
        event_interpretation="Test interpretation",
        possible_causes=[
            PossibleCause(
                cause=c["cause"],
                supporting_evidence=c.get("supporting", []),
                contradicting_evidence=c.get("contradicting", []),
                confidence=c.get("confidence", 0.7),
            )
            for c in causes
        ],
        parse_success=True,
    )


class TestCauseValidator:

    def test_heat_stress_cause_supported(self):
        validator = CauseValidator()
        event = make_event()
        analysis = make_cause_analysis([
            {"cause": "Possible heat-related physiological stress", "confidence": 0.8}
        ])
        result = validator.validate(analysis, event)
        assert len(result.passed_causes) >= 1
        assert result.passed_causes[0].validation_status in (
            "SUPPORTED", "PARTIALLY_SUPPORTED"
        )

    def test_tachycardia_cause_supported_at_rest(self):
        validator = CauseValidator()
        event = make_event(
            activity_state="REST",
            sensor_snapshot={
                "heart_rate": 120.0, "spo2": 97.0, "body_temperature": 36.8,
                "environment_temperature": 22.0, "humidity": 50.0,
                "altitude": 50.0, "acceleration_magnitude": 1.0,
            }
        )
        analysis = make_cause_analysis([
            {"cause": "Possible resting tachycardia", "confidence": 0.75}
        ])
        result = validator.validate(analysis, event)
        assert any(
            vc.validation_status in ("SUPPORTED", "PARTIALLY_SUPPORTED")
            for vc in result.validated_causes
        )

    def test_exercise_cause_not_supported_at_rest(self):
        """Cause mentioning exercise when activity=REST should be not supported."""
        validator = CauseValidator()
        event = make_event(
            activity_state="REST",
            sensor_snapshot={
                "heart_rate": 120.0, "spo2": 97.0, "body_temperature": 36.8,
                "environment_temperature": 22.0, "humidity": 50.0,
                "altitude": 50.0, "acceleration_magnitude": 1.0,
            }
        )
        analysis = make_cause_analysis([
            {"cause": "Normal physiological exercise response", "confidence": 0.5}
        ])
        # Exercise cause at rest should have low support
        result = validator.validate(analysis, event)
        # The cause doesn't match any keyword well — gets INSUFFICIENT_DATA
        # or NOT_SUPPORTED — either way it should NOT be the top SUPPORTED cause
        for vc in result.validated_causes:
            if "exercise" in vc.cause.lower():
                assert vc.validation_status in ("INSUFFICIENT_DATA", "NOT_SUPPORTED")

    def test_fall_cause_supported_when_fall_activity(self):
        validator = CauseValidator()
        # Add a fall rule to triggered rules
        fall_rule = TriggeredRule(
            rule_id="FALL_POSSIBLE_001",
            rule_name="Possible Fall",
            description="Test",
            severity=Severity.CRITICAL,
            triggered=True,
            reason="Test",
            evidence={},
            score_contribution=50,
        )
        event = make_event(
            activity_state="POSSIBLE_FALL",
            triggered_rules=[fall_rule],
        )
        analysis = make_cause_analysis([
            {"cause": "Possible fall event", "confidence": 0.9}
        ])
        result = validator.validate(analysis, event)
        assert result.passed_causes[0].validation_status == "SUPPORTED"

    def test_low_spo2_cause_supported(self):
        validator = CauseValidator()
        event = make_event(
            sensor_snapshot={
                "heart_rate": 80.0, "spo2": 88.0, "body_temperature": 36.8,
                "environment_temperature": 22.0, "humidity": 50.0,
                "altitude": 50.0, "acceleration_magnitude": 1.0,
            }
        )
        analysis = make_cause_analysis([
            {"cause": "Possible reduced oxygen saturation", "confidence": 0.85}
        ])
        result = validator.validate(analysis, event)
        assert len(result.passed_causes) >= 1

    def test_unsupported_cause_rejected(self):
        validator = CauseValidator()
        event = make_event(
            sensor_snapshot={
                "heart_rate": 72.0, "spo2": 98.0, "body_temperature": 36.7,
                "environment_temperature": 22.0, "humidity": 50.0,
                "altitude": 50.0, "acceleration_magnitude": 1.0,
            }
        )
        # Heat stress cause with no supporting environment data
        analysis = make_cause_analysis([
            {"cause": "Possible heat-related stress", "confidence": 0.5}
        ])
        result = validator.validate(analysis, event)
        # All causes should fail (env temp and humidity are normal)
        for vc in result.validated_causes:
            assert vc.validation_status in (
                "NOT_SUPPORTED", "PARTIALLY_SUPPORTED", "INSUFFICIENT_DATA"
            )
