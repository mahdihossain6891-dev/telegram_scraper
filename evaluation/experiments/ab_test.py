"""A/B experiment framework."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class Experiment:
    experiment_id: str
    name: str
    variant_a: str
    variant_b: str
    result_a: dict[str, Any] | None = None
    result_b: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        comparison = None
        if self.result_a and self.result_b:
            comparison = compare_variants(self.result_a, self.result_b)
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "variant_a": self.variant_a,
            "variant_b": self.variant_b,
            "result_a": self.result_a,
            "result_b": self.result_b,
            "comparison": comparison,
            "created_at": self.created_at.isoformat(),
        }


def compare_variants(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    iqs_a = float((a.get("iqs") or {}).get("iqs") or 0)
    iqs_b = float((b.get("iqs") or {}).get("iqs") or 0)
    delta = iqs_b - iqs_a
    significance = abs(delta) > 2.0
    return {
        "iqs_a": iqs_a,
        "iqs_b": iqs_b,
        "delta": round(delta, 2),
        "winner": "b" if delta > 0 else "a" if delta < 0 else "tie",
        "statistically_significant": significance,
        "effect_size": round(delta / max(iqs_a, 1), 4),
    }


class ExperimentManager:
    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}

    def create(self, name: str, variant_a: str, variant_b: str) -> dict[str, Any]:
        exp = Experiment(
            experiment_id=f"exp-{uuid4().hex[:10]}",
            name=name,
            variant_a=variant_a,
            variant_b=variant_b,
        )
        self._experiments[exp.experiment_id] = exp
        return exp.to_dict()

    def record(self, experiment_id: str, *, variant: str, result: dict[str, Any]) -> dict[str, Any]:
        exp = self._experiments[experiment_id]
        if variant == "a":
            exp.result_a = result
        else:
            exp.result_b = result
        return exp.to_dict()

    def list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._experiments.values()]
