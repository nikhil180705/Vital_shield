"""
risk_scorer.py — Deterministic risk scoring from triggered rules.

Aggregates rule score contributions, applies multi-sensor bonuses and
persistence multipliers, then maps to a risk level band.

All bands and bonuses are ENGINEERING CATEGORIES for the prototype.
"""

from __future__ import annotations

import logging
from typing import List

from app.config import RISK_SCORE_BANDS
from app.models.risk_models import RiskLevel, RiskScore, TriggeredRule

logger = logging.getLogger(__name__)

# Bonus for multi-sensor confirmation (more than one category of sensor abnormal)
MULTI_SENSOR_BONUS = 10

# Persistence multipliers: applied to base score based on consecutive abnormal readings
PERSISTENCE_MULTIPLIERS = {
    1: 1.0,
    2: 1.15,
    3: 1.30,
    4: 1.40,
    5: 1.50,
}


def score_to_level(score: int) -> RiskLevel:
    for level, (lo, hi) in RISK_SCORE_BANDS.items():
        if lo <= score <= hi:
            return RiskLevel(level)
    return RiskLevel.CRITICAL  # > 100 edge case


class RiskScorer:
    """
    Computes a deterministic risk score from a list of triggered rules.
    """

    def compute(
        self,
        rules: List[TriggeredRule],
        persistence_count: int = 1,
    ) -> RiskScore:
        """
        Parameters
        ----------
        rules:
            All rules evaluated by the rule engine (triggered and not-triggered).
        persistence_count:
            Number of consecutive abnormal readings.

        Returns
        -------
        RiskScore
        """
        triggered = [r for r in rules if r.triggered]

        # ----------------------------------------------------------------
        # Base score: sum of individual rule contributions
        # ----------------------------------------------------------------
        base_score = sum(r.score_contribution for r in triggered)
        breakdown: dict = {r.rule_id: r.score_contribution for r in triggered}

        # ----------------------------------------------------------------
        # Multi-sensor bonus
        # ----------------------------------------------------------------
        # Count distinct "categories" of triggered rules
        categories = set()
        for r in triggered:
            prefix = r.rule_id.split("_")[0]
            categories.add(prefix)

        if len(categories) >= 2:
            base_score += MULTI_SENSOR_BONUS
            breakdown["MULTI_SENSOR_BONUS"] = MULTI_SENSOR_BONUS
            logger.debug("Multi-sensor bonus applied (categories: %s)", categories)

        # ----------------------------------------------------------------
        # Persistence multiplier
        # ----------------------------------------------------------------
        multiplier = PERSISTENCE_MULTIPLIERS.get(
            min(persistence_count, max(PERSISTENCE_MULTIPLIERS.keys())),
            1.5,
        )
        adjusted_score = int(base_score * multiplier)

        # ----------------------------------------------------------------
        # Cap at 100
        # ----------------------------------------------------------------
        final_score = min(adjusted_score, 100)

        contributing_rule_ids = [r.rule_id for r in triggered]
        level = score_to_level(final_score)

        logger.info(
            "Risk score computed: base=%d, multiplier=%.2f, final=%d, level=%s",
            base_score, multiplier, final_score, level,
        )

        return RiskScore(
            score=final_score,
            risk_level=level,
            contributing_rules=contributing_rule_ids,
            breakdown=breakdown,
        )
