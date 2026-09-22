"""
renderer.py — Terminal output renderer for the health risk monitoring system.

Produces formatted, readable terminal output for each scenario result.
No web UI, no HTML, no dashboards — pure terminal output.
"""

from __future__ import annotations

from typing import List, Optional

from app.models.ai_models import (
    CauseAnalysisResult,
    CauseValidationResult,
    PrecautionResult,
)
from app.models.risk_models import ActivityState, RiskEvent, RiskLevel
from app.pipeline import PipelineResult, ReadingResult

# ANSI colour codes
R  = "\033[91m"    # Red
Y  = "\033[93m"    # Yellow
G  = "\033[92m"    # Green
B  = "\033[94m"    # Blue
C  = "\033[96m"    # Cyan
M  = "\033[95m"    # Magenta
W  = "\033[97m"    # White / Bold
DIM = "\033[2m"    # Dim
RST = "\033[0m"    # Reset
BLD = "\033[1m"    # Bold


LEVEL_COLORS = {
    RiskLevel.NORMAL:   G,
    RiskLevel.LOW:      G,
    RiskLevel.MODERATE: Y,
    RiskLevel.HIGH:     R,
    RiskLevel.CRITICAL: R + BLD,
}

ACTIVITY_ICONS = {
    "REST":          "🛌",
    "WALKING":       "🚶",
    "RUNNING":       "🏃",
    "HIGH_ACTIVITY": "⚡",
    "POSSIBLE_FALL": "🚨",
    "UNKNOWN":       "❓",
}


def _divider(char: str = "─", width: int = 64) -> str:
    return char * width


def _header(title: str, width: int = 64) -> str:
    return f"\n{'═' * width}\n{BLD}{title}{RST}\n{'═' * width}"


def _section(title: str, width: int = 64) -> str:
    return f"\n{DIM}{_divider('─', width)}{RST}\n{BLD}{C}{title}{RST}\n{DIM}{_divider('─', width)}{RST}"


def _level_str(level: RiskLevel) -> str:
    color = LEVEL_COLORS.get(level, W)
    return f"{color}{BLD}{level.value}{RST}"


class TerminalRenderer:
    """
    Renders a PipelineResult to the terminal in a structured, readable format.
    """

    def render_system_header(self, model: str, base_url: str, llm_available: bool) -> None:
        print()
        print(f"{'=' * 64}")
        print(f"{BLD}{C}  HEALTH RISK MONITORING SYSTEM{RST}")
        print(f"{BLD}{C}  Real-Time Wearable AI Analysis Prototype{RST}")
        print(f"{'=' * 64}")
        print(f"  {BLD}Terminal Prototype  -  All output to terminal{RST}")
        print(f"{'─' * 64}")
        print(f"  Model      : {W}{model}{RST}")
        print(f"  LM Studio  : {W}{base_url}{RST}")
        if llm_available:
            print(f"  LLM Status : {G}[CONNECTED]{RST}")
        else:
            print(f"  LLM Status : {Y}[UNAVAILABLE] -- AI analysis will be skipped{RST}")
        print(f"{'=' * 64}")

    def render_scenario_summary_line(
        self,
        scenario_id: int,
        scenario_name: str,
        risk_level: RiskLevel,
        ai_called: bool,
        fall: bool = False,
        altitude: bool = False,
    ) -> None:
        icons = []
        if fall:
            icons.append("🚨")
        if altitude:
            icons.append("⛰")
        icon_str = " ".join(icons)
        ai_str = f"  {M}→ AI ANALYSIS{RST}" if ai_called else ""
        print(
            f"  Scenario {scenario_id:02d}: {W}{scenario_name:<35}{RST} "
            f"{_level_str(risk_level)}{ai_str} {icon_str}"
        )

    def render_complete_result(self, result: PipelineResult) -> None:
        """Render the full detail for a single scenario."""
        self._render_scenario_header(result)
        self._render_last_reading(result)
        self._render_validation(result)
        self._render_rule_engine(result)
        self._render_decision(result)

        if result.risk_event:
            if result.cause_analysis:
                self._render_agent1(result.cause_analysis, result.llm_available)
            if result.cause_validation:
                self._render_validation_result(result.cause_validation)
            if result.precaution_result:
                self._render_agent2(result.precaution_result, result.llm_available)
            self._render_final_summary(result)

        print(f"\n{'═' * 64}")

    # -----------------------------------------------------------------------
    # Section renderers
    # -----------------------------------------------------------------------

    def _render_scenario_header(self, result: PipelineResult) -> None:
        print(_header(f"SCENARIO {result.scenario_id}: {result.scenario_name.upper()}"))
        print(f"  {DIM}{result.description}{RST}")
        print(f"  {DIM}Expected: {result.expected_outcome}{RST}")
        print(f"  {DIM}Readings processed: {len(result.reading_results)}{RST}")

    def _render_last_reading(self, result: PipelineResult) -> None:
        if not result.reading_results:
            return
        # Use peak reading
        peak = result.peak_engine_result
        if peak is None:
            return
        r = peak.reading
        activity = peak.activity

        print(_section("RAW SENSOR DATA"))

        icon = ACTIVITY_ICONS.get(str(activity), "❓")
        print(f"  {icon} Activity State    : {BLD}{activity}{RST}")
        print()
        self._val_line("Heart Rate",       r.heart_rate,            "bpm")
        self._val_line("SpO2",             r.spo2,                  "%")
        self._val_line("Body Temperature", r.body_temperature,      "°C")
        self._val_line("Environ Temp",     r.environment_temperature, "°C")
        self._val_line("Humidity",         r.humidity,              "%")
        self._val_line("Altitude",         r.altitude,              "m")
        self._val_line("Pressure",         r.atmospheric_pressure,  "hPa")
        self._val_line("Accel X",          r.acceleration_x,        "g")
        self._val_line("Accel Y",          r.acceleration_y,        "g")
        self._val_line("Accel Z",          r.acceleration_z,        "g")
        self._val_line("Accel Magnitude",  r.acceleration_magnitude, "g")
        if r.altitude_change is not None:
            self._val_line("Altitude Δ",   r.altitude_change,       "m")
        if r.pressure_change is not None:
            self._val_line("Pressure Δ",   r.pressure_change,       "hPa")

    def _render_validation(self, result: PipelineResult) -> None:
        if not result.reading_results:
            return
        last = result.reading_results[-1].validation
        print(_section("DATA VALIDATION"))

        if last.valid:
            print(f"  Status  : {G}✓ VALID{RST}")
        else:
            print(f"  Status  : {R}✗ INVALID{RST}")

        if last.issues:
            print(f"\n  {R}Issues:{RST}")
            for issue in last.issues:
                print(f"    • {issue}")

        if last.warnings:
            print(f"\n  {Y}Warnings:{RST}")
            for warn in last.warnings:
                print(f"    ⚠ {warn}")

        if last.rejected_fields:
            print(f"\n  {R}Rejected fields: {', '.join(last.rejected_fields)}{RST}")

        if last.valid and not last.issues and not last.warnings:
            print(f"  {DIM}All fields within plausible ranges.{RST}")

    def _render_rule_engine(self, result: PipelineResult) -> None:
        peak = result.peak_engine_result
        if peak is None:
            return

        print(_section("RULE ENGINE  (Deterministic — LLM not involved)"))

        triggered = [r for r in peak.rules if r.triggered]
        if triggered:
            print(f"  {BLD}Triggered Rules:{RST}")
            for rule in triggered:
                sev_color = {
                    "INFO": DIM, "LOW": G, "MEDIUM": Y, "HIGH": R, "CRITICAL": R + BLD
                }.get(rule.severity.value, W)
                print(f"\n  {sev_color}[{rule.rule_id}]{RST}")
                print(f"    {BLD}{rule.rule_name}{RST}")
                print(f"    {rule.reason}")
                if rule.score_contribution:
                    print(f"    {DIM}Score contribution: +{rule.score_contribution}{RST}")
        else:
            print(f"  {G}No rules triggered.{RST}")

        print()
        level = peak.risk_score.risk_level
        score = peak.risk_score.score
        color = LEVEL_COLORS.get(level, W)
        print(f"  Risk Score  : {color}{BLD}{score}/100{RST}")
        print(f"  Risk Level  : {_level_str(level)}")

        if peak.persistence_count > 0:
            print(f"  Persistence : {peak.persistence_count} consecutive abnormal readings")

        if peak.is_exercise_normal:
            print(f"\n  {G}✓ Elevated HR explained by exercise — NORMAL PHYSIOLOGICAL ACTIVITY{RST}")

    def _render_decision(self, result: PipelineResult) -> None:
        print(_section("DECISION"))
        peak = result.peak_engine_result

        if peak is None:
            print(f"  {G}✓ No readings available.{RST}")
            return

        if peak.is_exercise_normal:
            print(f"  {G}✓ Normal physiological exercise response detected.{RST}")
            print(f"  {G}✓ AI analysis not required.{RST}")
        elif result.risk_event is None:
            print(f"  {G}✓ No significant risk detected.{RST}")
            print(f"  {G}✓ AI analysis not required.{RST}")
        else:
            level = peak.risk_score.risk_level
            print(f"  {R}⚠ Risk event detected — risk level: {_level_str(level)}{RST}")
            print(f"  {M}→ Triggering AI analysis pipeline...{RST}")

            fall = any(
                r.rule_id == "FALL_POSSIBLE_001" and r.triggered
                for r in peak.rules
            )
            if fall:
                print(f"  {R + BLD}⚠ POSSIBLE FALL DETECTED — URGENT REVIEW REQUIRED{RST}")

        if result.risk_event and result.risk_event.high_altitude:
            print(f"\n  {C}⛰ Altitude context: {result.risk_event.altitude_context_note}{RST}")

    def _render_agent1(
        self, analysis: CauseAnalysisResult, llm_available: bool
    ) -> None:
        print(_section("AI AGENT 1 — CAUSE ANALYSIS"))

        if not llm_available or analysis.llm_unavailable:
            print(f"  {Y}⚠ LM Studio is unavailable. AI analysis skipped.{RST}")
            print(f"  {Y}  Rule engine completed successfully.{RST}")
            return

        if not analysis.parse_success:
            print(f"  {R}⚠ AI Agent 1 response could not be parsed.{RST}")
            if analysis.error_message:
                print(f"  Error: {analysis.error_message}")
            return

        print(f"  {BLD}Interpretation:{RST}")
        print(f"  {analysis.event_interpretation}")

        if analysis.possible_causes:
            print(f"\n  {BLD}Possible causes:{RST}")
            for i, cause in enumerate(analysis.possible_causes, 1):
                conf_color = (
                    G if cause.confidence >= 0.7
                    else Y if cause.confidence >= 0.4
                    else DIM
                )
                print(f"\n  {i}. {BLD}{cause.cause}{RST}")
                print(f"     Confidence: {conf_color}{cause.confidence:.2f}{RST}")
                if cause.supporting_evidence:
                    print(f"     {G}Supporting:{RST}")
                    for e in cause.supporting_evidence:
                        print(f"       + {e}")
                if cause.contradicting_evidence:
                    print(f"     {R}Contradicting:{RST}")
                    for e in cause.contradicting_evidence:
                        print(f"       - {e}")

        if analysis.alternative_explanations:
            print(f"\n  {BLD}Alternative explanations:{RST}")
            for alt in analysis.alternative_explanations:
                print(f"    • {alt}")

        if analysis.missing_information:
            print(f"\n  {DIM}Missing information:{RST}")
            for mi in analysis.missing_information:
                print(f"    ? {mi}")

    def _render_validation_result(self, validation: CauseValidationResult) -> None:
        print(_section("CAUSE VALIDATION  (Deterministic)"))

        if not validation.validated_causes:
            print(f"  {DIM}No causes to validate.{RST}")
            return

        for vc in validation.validated_causes:
            status = vc.validation_status
            status_color = {
                "SUPPORTED":           G,
                "PARTIALLY_SUPPORTED": Y,
                "NOT_SUPPORTED":       R,
                "INSUFFICIENT_DATA":   DIM,
            }.get(status, W)
            print(f"\n  Cause  : {BLD}{vc.cause}{RST}")
            print(f"  Status : {status_color}{BLD}{status}{RST}")

            if vc.supporting_evidence:
                print(f"  {G}Evidence:{RST}")
                for e in vc.supporting_evidence[:4]:
                    print(f"    ✓ {e}")

            if vc.contradicting_evidence:
                print(f"  {R}Contradictions:{RST}")
                for e in vc.contradicting_evidence[:3]:
                    print(f"    ✗ {e}")

            passed_str = (
                f"{G}→ Passed to Agent 2{RST}"
                if vc.passed_to_agent2
                else f"{R}→ Rejected — not passed to Agent 2{RST}"
            )
            print(f"  {passed_str}")

        print(f"\n  {DIM}{validation.validation_summary}{RST}")

    def _render_agent2(self, precaution: PrecautionResult, llm_available: bool) -> None:
        print(_section("AI AGENT 2 — PRECAUTION RECOMMENDATIONS"))

        if not llm_available or precaution.llm_unavailable:
            print(f"  {Y}⚠ LM Studio is unavailable. Precaution analysis skipped.{RST}")
            return

        if not precaution.parse_success:
            print(f"  {R}⚠ Agent 2 response could not be parsed.{RST}")
            return

        if precaution.emergency_warning:
            print(f"  {R + BLD}🚨 EMERGENCY WARNING — Consider calling emergency services immediately.{RST}")
        print()

        print(f"  {BLD}Condition Summary:{RST}")
        print(f"  {precaution.condition_summary}")

        if precaution.immediate_precautions:
            print(f"\n  {BLD}{R}Immediate Precautions:{RST}")
            for i, p in enumerate(precaution.immediate_precautions, 1):
                print(f"    {i}. {p}")

        if precaution.monitoring_steps:
            print(f"\n  {BLD}{Y}Monitoring Steps:{RST}")
            for i, m in enumerate(precaution.monitoring_steps, 1):
                print(f"    {i}. {m}")

        if precaution.escalation_conditions:
            print(f"\n  {BLD}{R}Seek Medical Attention If:{RST}")
            for i, e in enumerate(precaution.escalation_conditions, 1):
                print(f"    {i}. {e}")

        if precaution.reasoning:
            print(f"\n  {DIM}Reasoning: {precaution.reasoning}{RST}")

    def _render_final_summary(self, result: PipelineResult) -> None:
        print(_section("FINAL SYSTEM RESULT"))

        peak = result.peak_engine_result
        level = result.final_risk_level
        color = LEVEL_COLORS.get(level, W)

        print(f"  Risk Level : {color}{BLD}{level.value}{RST}")

        if result.cause_validation and result.cause_validation.passed_causes:
            top_cause = result.cause_validation.passed_causes[0]
            print(f"  Cause      : {top_cause.cause}")
            print(f"  Validation : {top_cause.validation_status}")

        if result.precaution_result and result.precaution_result.parse_success:
            precs = result.precaution_result.immediate_precautions
            if precs:
                print(f"  Action     : {precs[0]}")

        if not result.llm_available:
            print(f"\n  {Y}⚠ WARNING: LM Studio was unavailable.{RST}")
            print(f"  {Y}  Rule engine completed successfully.{RST}")
            print(f"  {Y}  AI analysis skipped.{RST}")

        print(f"\n  {DIM}Processing time: {result.processing_time_seconds:.2f}s{RST}")

    # -----------------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------------

    def _val_line(self, label: str, value, unit: str, width: int = 22) -> None:
        val_str = f"{value:.1f}" if isinstance(value, float) else str(value)
        print(f"  {label:<{width}}: {W}{val_str}{RST} {unit}")

    def render_system_footer(
        self, results: List[PipelineResult], llm_available: bool
    ) -> None:
        print(f"\n{'═' * 64}")
        print(f"{BLD}{C}  SYSTEM COMPLETE{RST}")
        print(f"{'─' * 64}")
        print(f"  Scenarios executed : {len(results)}")
        normal_count = sum(
            1 for r in results if r.final_risk_level in (RiskLevel.NORMAL, RiskLevel.LOW)
        )
        risk_count   = sum(
            1 for r in results if r.final_risk_level not in (RiskLevel.NORMAL, RiskLevel.LOW)
        )
        ai_count     = sum(1 for r in results if r.ai_called)
        print(f"  Normal scenarios   : {G}{normal_count}{RST}")
        print(f"  Risk scenarios     : {R}{risk_count}{RST}")
        print(f"  AI analyses run    : {M}{ai_count}{RST}")
        if not llm_available:
            print(f"\n  {Y}⚠ LM Studio was unavailable during this session.{RST}")
            print(f"  {Y}  All deterministic rule results are valid.{RST}")
            print(f"  {Y}  AI analyses were skipped.{RST}")
        print(f"{'═' * 64}\n")
