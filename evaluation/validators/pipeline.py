"""Pipeline stage-by-stage validator."""

from __future__ import annotations

from collections import defaultdict

from evaluation.metrics.types import EvaluationSample
from evaluation.validators.base import BaseEvaluator, EvaluationResult


class PipelineValidator(BaseEvaluator):
    name = "pipeline"

    STAGES = (
        "validation",
        "normalization",
        "keyword",
        "entity_extraction",
        "risk",
        "behavior",
        "relationship",
        "alert",
        "persistence",
        "metrics",
    )

    def evaluate(self, samples: list[EvaluationSample]) -> EvaluationResult:
        stage_stats: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"processed": 0, "failures": 0, "latency_sum": 0.0}
        )
        for sample in samples:
            for stage in sample.stages:
                name = str(stage.get("stage") or "")
                if not name:
                    continue
                stats = stage_stats[name]
                stats["processed"] = int(stats["processed"]) + 1
                stats["latency_sum"] = float(stats["latency_sum"]) + float(stage.get("latency_ms") or 0)
                if stage.get("result") == "error":
                    stats["failures"] = int(stats["failures"]) + 1
        report: dict[str, dict[str, float | int | str]] = {}
        healthy = 0
        for stage_name in self.STAGES:
            stats = stage_stats.get(stage_name, {"processed": 0, "failures": 0, "latency_sum": 0.0})
            processed = int(stats["processed"])
            failures = int(stats["failures"])
            avg_lat = float(stats["latency_sum"]) / processed if processed else 0.0
            status = "healthy"
            if failures:
                status = "error"
            elif avg_lat > 500:
                status = "warning"
            else:
                healthy += 1
            report[stage_name] = {
                "status": status,
                "average_latency_ms": round(avg_lat, 3),
                "messages_processed": processed,
                "failures": failures,
            }
        score = (healthy / len(self.STAGES)) * 100 if self.STAGES else 0
        return EvaluationResult(subsystem="pipeline", score=round(score, 2), metrics={"stages": report})
