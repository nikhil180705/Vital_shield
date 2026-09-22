"""
main.py — Entry point for the Health Risk Monitoring System prototype.

Run with:
    python main.py

All output is directed to the terminal.
No web UI, no frontend, no dashboard.
"""

import sys
import os

# Ensure the health_risk_system package root is on the path
sys.path.insert(0, os.path.dirname(__file__))

# Reconfigure stdout to UTF-8 on Windows (box-drawing chars require UTF-8)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

from app.logger_setup import setup_logging
from app.config import LM_STUDIO_BASE_URL, LM_STUDIO_MODEL
from app.mock.scenarios import ALL_SCENARIOS
from app.pipeline import HealthRiskPipeline
from app.renderer import TerminalRenderer
from app.models.risk_models import RiskLevel


def main() -> None:
    setup_logging()

    pipeline = HealthRiskPipeline()
    renderer = TerminalRenderer()

    llm_available = pipeline.llm_available

    # -----------------------------------------------------------------------
    # System header
    # -----------------------------------------------------------------------
    renderer.render_system_header(
        model=LM_STUDIO_MODEL,
        base_url=LM_STUDIO_BASE_URL,
        llm_available=llm_available,
    )

    print(f"\n  Running {len(ALL_SCENARIOS)} mock scenarios...\n")

    # -----------------------------------------------------------------------
    # Quick summary line per scenario
    # -----------------------------------------------------------------------
    results = []
    for scenario in ALL_SCENARIOS:
        result = pipeline.process_scenario(scenario, inter_reading_delay=0.0)
        results.append(result)
        renderer.render_scenario_summary_line(
            scenario_id=result.scenario_id,
            scenario_name=result.scenario_name,
            risk_level=result.final_risk_level,
            ai_called=result.ai_called,
            fall=(result.final_risk_level == RiskLevel.CRITICAL and "Fall" in result.scenario_name),
            altitude="Altitude" in result.scenario_name,
        )

    print()

    # -----------------------------------------------------------------------
    # Detailed output per scenario
    # -----------------------------------------------------------------------
    for result in results:
        renderer.render_complete_result(result)

    # -----------------------------------------------------------------------
    # Footer
    # -----------------------------------------------------------------------
    renderer.render_system_footer(results, llm_available)


if __name__ == "__main__":
    main()
