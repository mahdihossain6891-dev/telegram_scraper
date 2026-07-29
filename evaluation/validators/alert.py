"""Alert evaluation."""

from __future__ import annotations

from evaluation.metrics.classification import compute_classification
from evaluation.metrics.types import EvaluationSample
from evaluation.validators.base import BaseEvaluator, EvaluationResult


class AlertEvaluator(BaseEvaluator):
    name = "alert"

    def evaluate(self, samples: list[EvaluationSample]) -> EvaluationResult:
        tp = fp = fn = tn = 0
        delays: list[float] = []
        duplicates = 0
        seen_alerts: set[str] = set()
        for sample in samples:
            gt = sample.ground_truth
            ctx = sample.context
            exp = bool(gt.get("expected_alert"))
            got = bool(ctx.get("alert"))
            if exp and got:
                tp += 1
            elif not exp and got:
                fp += 1
            elif exp and not got:
                fn += 1
            else:
                tn += 1
            if got:
                alert_key = str((ctx.get("alert") or {}).get("type") or sample.message_id)
                if alert_key in seen_alerts:
                    duplicates += 1
                seen_alerts.add(alert_key)
                for stage in sample.stages:
                    if stage.get("stage") == "alert":
                        delays.append(float(stage.get("latency_ms") or 0))
        cls = compute_classification(tp, fp, fn, tn)
        return EvaluationResult(
            subsystem="alert",
            score=round(cls.f1_score * 100, 2),
            metrics={
                **cls.to_dict(),
                "average_alert_delay_ms": round(sum(delays) / len(delays), 3) if delays else 0.0,
                "duplicate_alerts": duplicates,
                "missed_alerts": fn,
            },
        )
