"""Simplified star scoring for Trend Validation v1.

This module provides a lightweight facade score (1-5 stars) derived from stable
core metrics (`blended_priority_score`) while remaining transparent and stateless.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoreResult:
    """Scoring result object for JSON output."""

    stars: float
    decision: str
    metrics: dict
    explanation: str


def _clip_0_1(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _decision_from_stars(stars: float) -> str:
    if stars >= 4.0:
        return "POST"
    if stars >= 2.5:
        return "ADAPT"
    return "AVOID"


def score_candidate(
    blended_priority_score: float,
    prompt_quality_score: float,
    rights: str,
) -> ScoreResult:
    """Compute v1 star score and transparent explanation.

    The facade exposes extra simple indicators for future UI without changing core:
    - engagement_ratio proxy from prompt quality
    - velocity_score proxy from blended priority
    - saturation_score proxy from rights risk
    """
    blended_norm = _clip_0_1(blended_priority_score / 100.0)
    engagement_ratio = _clip_0_1(prompt_quality_score / 100.0)
    velocity_score = blended_norm
    demand_score = blended_norm

    rights_upper = (rights or "").upper()
    if rights_upper == "FREE_REPOST":
        saturation_score = 0.2
    elif rights_upper == "REWRITE_REQUIRED":
        saturation_score = 0.35
    elif rights_upper == "INSPIRE_ONLY":
        saturation_score = 0.55
    else:
        saturation_score = 0.75

    raw = (
        (velocity_score * 0.4)
        + (engagement_ratio * 0.3)
        + (demand_score * 0.2)
        - (saturation_score * 0.1)
    )
    raw = _clip_0_1(raw)
    stars = round(1.0 + (raw * 4.0), 1)
    decision = _decision_from_stars(stars)

    explanation = (
        "Score basé sur blended_priority_score + qualité prompt + risque saturation "
        f"(rights={rights_upper or 'UNKNOWN'})."
    )

    return ScoreResult(
        stars=stars,
        decision=decision,
        metrics={
            "blended_priority_score": round(blended_norm, 3),
            "engagement_ratio": round(engagement_ratio, 3),
            "velocity_score": round(velocity_score, 3),
            "saturation_score": round(saturation_score, 3),
        },
        explanation=explanation,
    )
