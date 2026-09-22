"""
pipeline.py — The complete health risk monitoring pipeline.

Processes one SensorReadingSequence (scenario) end-to-end:

    SensorReading
        ↓
    DataValidation
        ↓
    ActivityDetector
        ↓
    RuleEngine
        ↓
    [NORMAL] or [RISK EVENT]
        ↓ (risk only)
    AI Agent 1 (Cause Analysis)
        ↓
    Cause Validator
        ↓
    AI Agent 2 (Precautions)
        ↓
    PipelineResult

The pipeline processes one reading at a time. For mock scenarios,
all readings in a sequence are processed and the final risk state is reported.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.ai.cause_agent import CauseAgent
from app.ai.cause_validator import CauseValidator
from app.ai.llm_client import LLMClient
from app.ai.precaution_agent import PrecautionAgent
from app.context.activity_detector import ActivityDetector
from app.models.ai_models import (
    CauseAnalysisResult,
    CauseValidationResult,
    PrecautionResult,
)
from app.models.risk_models import ActivityState, RiskEvent, RiskLevel, ValidationResult
from app.models.sensor_models import SensorReading, SensorReadingSequence
from app.rules.rule_engine import RuleEngine, RuleEngineResult
from app.validation.sensor_validator import SensorValidator

logger = logging.getLogger(__name__)


@dataclass
class ReadingResult:
    """Result for a single reading within a scenario."""
    reading: SensorReading
    validation: ValidationResult
    activity: ActivityState
    engine_result: RuleEngineResult


@dataclass
class PipelineResult:
    """Final aggregated result for a complete scenario."""
    scenario_id: int
    scenario_name: str
    description: str
    expected_outcome: str

    reading_results: List[ReadingResult] = field(default_factory=list)

    # Represents the highest-risk reading in this scenario
    peak_engine_result: Optional[RuleEngineResult] = None
    risk_event: Optional[RiskEvent] = None

    # AI outputs (only populated if risk event triggered)
    cause_analysis: Optional[CauseAnalysisResult] = None
    cause_validation: Optional[CauseValidationResult] = None
    precaution_result: Optional[PrecautionResult] = None

    # Summary flags
    ai_called: bool = False
    llm_available: bool = True
    processing_time_seconds: float = 0.0

    @property
    def final_risk_level(self) -> RiskLevel:
        if self.peak_engine_result:
            return self.peak_engine_result.risk_score.risk_level
        return RiskLevel.NORMAL


class HealthRiskPipeline:
    """
    The complete health-risk monitoring pipeline.

    Can be used with any SensorDataProvider:
        for reading in provider.stream():
            pipeline.process_reading(reading, ...)
    """

    def __init__(self) -> None:
        self._validator = SensorValidator()
        self._activity_detector = ActivityDetector()
        self._rule_engine = RuleEngine()
        self._llm_client = LLMClient()
        self._cause_agent = CauseAgent(self._llm_client)
        self._cause_validator = CauseValidator()
        self._precaution_agent = PrecautionAgent(self._llm_client)

    @property
    def llm_available(self) -> bool:
        return self._llm_client.is_available()

    def process_scenario(
        self,
        scenario: SensorReadingSequence,
        inter_reading_delay: float = 0.0,
    ) -> PipelineResult:
        """
        Process a complete scenario (multiple readings) and return results.
        """
        start_time = time.time()

        # Reset stateful components for each new scenario
        self._activity_detector.reset_fall_state()
        self._rule_engine.reset()

        result = PipelineResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.scenario_name,
            description=scenario.description,
            expected_outcome=scenario.expected_outcome,
        )

        logger.info(
            "=== Processing Scenario %d: %s ===",
            scenario.scenario_id,
            scenario.scenario_name,
        )

        peak_score = -1
        peak_engine_result: Optional[RuleEngineResult] = None

        # ----------------------------------------------------------------
        # Process each reading sequentially
        # ----------------------------------------------------------------
        for reading in scenario.readings:
            reading_result = self._process_reading(
                reading=reading,
                scenario_id=scenario.scenario_id,
                scenario_name=scenario.scenario_name,
            )
            result.reading_results.append(reading_result)

            if reading_result.engine_result.risk_score.score > peak_score:
                peak_score = reading_result.engine_result.risk_score.score
                peak_engine_result = reading_result.engine_result

            if inter_reading_delay > 0:
                time.sleep(inter_reading_delay)

        result.peak_engine_result = peak_engine_result

        # ----------------------------------------------------------------
        # AI pipeline — triggered if any reading produced a risk event
        # ----------------------------------------------------------------
        # Use the highest-risk reading's event
        risk_event = (
            peak_engine_result.risk_event if peak_engine_result else None
        )

        if risk_event is None:
            # Fall back to checking all reading results for any risk event
            for rr in result.reading_results:
                if rr.engine_result.risk_event is not None:
                    risk_event = rr.engine_result.risk_event
                    break

        result.risk_event = risk_event

        if risk_event is not None:
            result.ai_called = True
            result.llm_available = self._llm_client.is_available()

            logger.info(
                "Scenario %d: Risk event detected — calling AI pipeline.",
                scenario.scenario_id,
            )

            # Agent 1 — Cause Analysis
            cause_analysis = self._cause_agent.analyze(risk_event)
            result.cause_analysis = cause_analysis

            # Cause Validation
            if cause_analysis.parse_success and not cause_analysis.llm_unavailable:
                cause_validation = self._cause_validator.validate(cause_analysis, risk_event)
                result.cause_validation = cause_validation

                # Agent 2 — Precautions
                precaution = self._precaution_agent.recommend(risk_event, cause_validation)
                result.precaution_result = precaution
            else:
                logger.warning(
                    "Scenario %d: Agent 1 failed — skipping validation and Agent 2.",
                    scenario.scenario_id,
                )

        result.processing_time_seconds = time.time() - start_time
        logger.info(
            "Scenario %d complete in %.2fs — final risk: %s",
            scenario.scenario_id,
            result.processing_time_seconds,
            result.final_risk_level,
        )

        return result

    def _process_reading(
        self,
        reading: SensorReading,
        scenario_id: int,
        scenario_name: str,
    ) -> ReadingResult:
        """Process a single sensor reading through validation → activity → rules."""

        # Step 1: Validate
        validation = self._validator.validate(reading)
        if not validation.valid:
            logger.warning(
                "Reading %s validation FAILED — skipping rule engine. Issues: %s",
                reading.reading_id,
                validation.issues,
            )
            # Return a stub result for invalid readings
            activity = ActivityState.UNKNOWN
            engine_result = _stub_engine_result(reading, activity)
            return ReadingResult(
                reading=reading,
                validation=validation,
                activity=activity,
                engine_result=engine_result,
            )

        # Step 2: Activity detection
        activity = self._activity_detector.classify(reading)
        reading.activity_state = str(activity)

        # Step 3: Rule engine
        engine_result = self._rule_engine.evaluate(
            reading=reading,
            activity=activity,
            scenario_id=scenario_id,
            scenario_name=scenario_name,
        )

        return ReadingResult(
            reading=reading,
            validation=validation,
            activity=activity,
            engine_result=engine_result,
        )


# ---------------------------------------------------------------------------
# Helper — stub result for invalid readings
# ---------------------------------------------------------------------------

def _stub_engine_result(reading: SensorReading, activity: ActivityState) -> RuleEngineResult:
    """Minimal stub when a reading fails validation."""
    from app.rules.risk_scorer import RiskScore
    return RuleEngineResult(
        rules=[],
        risk_score=RiskScore(),
        activity=activity,
        reading=reading,
        is_exercise_normal=False,
        requires_ai=False,
        risk_event=None,
        persistence_count=0,
    )
