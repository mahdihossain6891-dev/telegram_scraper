"""Intelligence Quality Score (IQS) — platform health indicator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evaluation.scoring.weights import DEFAULT_WEIGHTS, ScoringWeights
from evaluation.validators.base import EvaluationResult


@dataclass(slots=True)
class IntelligenceQualityScore:
    """Weighted composite score 0–100."""

    iqs: float
    components: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    explainability: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "iqs": round(self.iqs, 2),
            "components": {k: round(v, 2) for k, v in self.components.items()},
            "weights": self.weights,
            "explainability": round(self.explainability, 2),
            "detection_quality": round(
                (self.components.get("keyword", 0) + self.components.get("risk", 0)) / 2, 2
            ),
            "behavior_quality": round(self.components.get("behavior", 0), 2),
            "relationship_quality": round(self.components.get("relationship", 0), 2),
            "alert_quality": round(self.components.get("alert", 0), 2),
            "ai_quality": round(self.components.get("sebastian", 0), 2),
            "performance_quality": round(self.components.get("performance", 0), 2),
        }


def compute_iqs(
    results: dict[str, EvaluationResult],
    *,
    performance_score: float = 0.0,
    weights: ScoringWeights | None = None,
) -> IntelligenceQualityScore:
    w = (weights or DEFAULT_WEIGHTS).normalized()
    components = {
        "keyword": results.get("keyword", EvaluationResult("keyword", 0)).score,
        "risk": results.get("risk", EvaluationResult("risk", 0)).score,
        "behavior": results.get("behavior", EvaluationResult("behavior", 0)).score,
        "relationship": results.get("relationship", EvaluationResult("relationship", 0)).score,
        "alert": results.get("alert", EvaluationResult("alert", 0)).score,
        "sebastian": results.get("sebastian", EvaluationResult("sebastian", 0)).score,
        "performance": performance_score,
    }
    iqs = (
        components["keyword"] * w.keyword
        + components["risk"] * w.risk
        + components["behavior"] * w.behavior
        + components["relationship"] * w.relationship
        + components["alert"] * w.alert
        + components["sebastian"] * w.sebastian
        + components["performance"] * w.performance
    )
    seb = results.get("sebastian")
    explainability = 0.0
    if seb:
        explainability = float(seb.metrics.get("citation_accuracy", 0)) * 100
    return IntelligenceQualityScore(
        iqs=round(iqs, 2),
        components=components,
        weights=w.to_dict(),
        explainability=explainability,
    )
