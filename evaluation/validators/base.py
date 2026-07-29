"""Base evaluator and plugin contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from evaluation.metrics.types import EvaluationSample


@dataclass(slots=True)
class EvaluationResult:
    subsystem: str
    score: float
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class BaseEvaluator(ABC):
    """Plugin-ready evaluator base."""

    name: str = "base"

    @abstractmethod
    def evaluate(self, samples: list[EvaluationSample]) -> EvaluationResult: ...
