"""Scoring engine — orchestrates evaluators and IQS."""

from __future__ import annotations

from typing import Any

from evaluation.metrics.types import EvaluationSample
from evaluation.plugins.registry import EvaluatorRegistry
from evaluation.scoring.iqs import IntelligenceQualityScore, compute_iqs
from evaluation.scoring.weights import ScoringWeights
from evaluation.validators.base import EvaluationResult


class ScoringEngine:
    def __init__(self, registry: EvaluatorRegistry | None = None) -> None:
        self._registry = registry or EvaluatorRegistry.with_defaults()

    def score(
        self,
        samples: list[EvaluationSample],
        *,
        sebastian_responses: list[dict[str, Any]] | None = None,
        performance: dict[str, Any] | None = None,
        weights: ScoringWeights | None = None,
    ) -> dict[str, Any]:
        results: dict[str, EvaluationResult] = {}
        for evaluator in self._registry.all():
            if evaluator.name == "sebastian":
                results["sebastian"] = evaluator.evaluate(sebastian_responses or [])
            else:
                results[evaluator.name] = evaluator.evaluate(samples)
        perf_score = self._performance_score(performance or {})
        iqs = compute_iqs(results, performance_score=perf_score, weights=weights)
        return {
            "subsystems": {k: {"score": v.score, "metrics": v.metrics} for k, v in results.items()},
            "iqs": iqs.to_dict(),
            "performance": performance or {},
        }

    def _performance_score(self, perf: dict[str, Any]) -> float:
        throughput = float(perf.get("messages_per_sec") or perf.get("pipeline_throughput_per_tick") or 0)
        cpu = float(perf.get("cpu_usage_percent") or perf.get("cpu_percent") or 0)
        throughput_score = min(100.0, throughput * 10)
        cpu_score = max(0.0, 100.0 - cpu)
        return round((throughput_score * 0.6 + cpu_score * 0.4), 2)
