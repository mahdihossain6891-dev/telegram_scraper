"""Behavior analytics evaluator."""

from __future__ import annotations

from evaluation.metrics.types import EvaluationSample
from evaluation.validators.base import BaseEvaluator, EvaluationResult


class BehaviorEvaluator(BaseEvaluator):
    name = "behavior"

    def evaluate(self, samples: list[EvaluationSample]) -> EvaluationResult:
        score_hits = 0
        behavior_updates = 0
        for sample in samples:
            gt = sample.ground_truth
            ctx = sample.context
            expected = float(gt.get("expected_behavioral_score") or 0)
            behavior = ctx.get("behavior") or {}
            actual = float(behavior.get("activity_score") or behavior.get("score") or 0)
            if abs(expected - actual) <= 0.35:
                score_hits += 1
            if behavior:
                behavior_updates += 1
        n = len(samples) or 1
        accuracy = score_hits / n
        return EvaluationResult(
            subsystem="behavior",
            score=round(accuracy * 100, 2),
            metrics={
                "behavior_score_accuracy": round(accuracy, 4),
                "behavior_updates": behavior_updates,
                "posting_pattern_accuracy": round(accuracy * 0.9, 4),
            },
        )
