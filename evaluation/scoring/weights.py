"""Default IQS component weights (configurable)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ScoringWeights:
    keyword: float = 0.20
    risk: float = 0.15
    behavior: float = 0.15
    relationship: float = 0.15
    alert: float = 0.10
    sebastian: float = 0.15
    performance: float = 0.10

    def to_dict(self) -> dict[str, float]:
        return {
            "keyword": self.keyword,
            "risk": self.risk,
            "behavior": self.behavior,
            "relationship": self.relationship,
            "alert": self.alert,
            "sebastian": self.sebastian,
            "performance": self.performance,
        }

    def normalized(self) -> "ScoringWeights":
        total = (
            self.keyword
            + self.risk
            + self.behavior
            + self.relationship
            + self.alert
            + self.sebastian
            + self.performance
        )
        if total <= 0:
            return ScoringWeights()
        return ScoringWeights(
            keyword=self.keyword / total,
            risk=self.risk / total,
            behavior=self.behavior / total,
            relationship=self.relationship / total,
            alert=self.alert / total,
            sebastian=self.sebastian / total,
            performance=self.performance / total,
        )

DEFAULT_WEIGHTS = ScoringWeights()
