"""Keyword detection evaluator."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from evaluation.metrics.classification import compute_classification
from evaluation.metrics.types import EvaluationSample
from evaluation.validators.base import BaseEvaluator, EvaluationResult


class KeywordEvaluator(BaseEvaluator):
    name = "keyword"

    def evaluate(self, samples: list[EvaluationSample]) -> EvaluationResult:
        tp = fp = fn = tn = 0
        per_keyword: dict[str, dict[str, int]] = defaultdict(lambda: {"hit": 0, "miss": 0})
        latencies: list[float] = []
        for sample in samples:
            gt = sample.ground_truth
            ctx = sample.context
            expected = set(gt.get("expected_keywords") or [])
            actual = set(ctx.get("keywords") or [])
            if not expected and not actual:
                tn += 1
                continue
            if expected:
                for kw in expected:
                    if kw in actual:
                        per_keyword[kw]["hit"] += 1
                    else:
                        per_keyword[kw]["miss"] += 1
            if expected and actual and expected & actual:
                tp += 1
            elif expected and not (expected & actual):
                fn += 1
            elif not expected and actual:
                fp += 1
            for stage in sample.stages:
                if stage.get("stage") == "keyword":
                    latencies.append(float(stage.get("latency_ms") or 0))
        cls = compute_classification(tp, fp, fn, tn)
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        score = cls.f1_score * 100 if (tp + fp + fn + tn) else 100.0
        return EvaluationResult(
            subsystem="keyword",
            score=round(score, 2),
            metrics={
                **cls.to_dict(),
                "average_detection_latency_ms": round(avg_latency, 3),
                "per_keyword": dict(per_keyword),
            },
        )
