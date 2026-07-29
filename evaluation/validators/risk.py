"""Risk scoring evaluator."""

from __future__ import annotations

from evaluation.metrics.types import EvaluationSample
from evaluation.validators.base import BaseEvaluator, EvaluationResult

_RISK_ORDER = {"normal": 0, "elevated": 1, "high": 2, "critical": 3}


class RiskEvaluator(BaseEvaluator):
    name = "risk"

    def evaluate(self, samples: list[EvaluationSample]) -> EvaluationResult:
        errors: list[float] = []
        drift = 0
        confidence_bins: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        matches = 0
        for sample in samples:
            gt = sample.ground_truth
            ctx = sample.context
            expected = str(gt.get("expected_risk_level") or "normal")
            actual = str(ctx.get("risk_level") or "normal")
            exp_i = _RISK_ORDER.get(expected, 0)
            act_i = _RISK_ORDER.get(actual, 0)
            errors.append(abs(exp_i - act_i))
            if exp_i != act_i:
                drift += 1
            else:
                matches += 1
            score_val = float(ctx.get("risk_score") or 0)
            if score_val < 0.33:
                confidence_bins["low"] += 1
            elif score_val < 0.66:
                confidence_bins["medium"] += 1
            else:
                confidence_bins["high"] += 1
        n = len(samples) or 1
        risk_error = sum(errors) / n
        accuracy = matches / n
        return EvaluationResult(
            subsystem="risk",
            score=round(accuracy * 100, 2),
            metrics={
                "risk_error": round(risk_error, 4),
                "risk_drift_count": drift,
                "accuracy": round(accuracy, 4),
                "confidence_distribution": confidence_bins,
            },
        )
