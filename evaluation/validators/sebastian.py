"""Sebastian / AI investigation evaluator."""

from __future__ import annotations

from typing import Any

from evaluation.validators.base import BaseEvaluator, EvaluationResult


class SebastianEvaluator(BaseEvaluator):
    name = "sebastian"

    def evaluate(self, responses: list[dict[str, Any]]) -> EvaluationResult:
        if not responses:
            return EvaluationResult(subsystem="sebastian", score=0.0, metrics={"evaluated": 0})
        citation_hits = 0
        hallucinations = 0
        tool_hits = 0
        summary_hits = 0
        confidence_errors: list[float] = []
        for resp in responses:
            gt = resp.get("ground_truth") or {}
            structured = resp.get("structured") or resp
            citations = structured.get("citations") or []
            if citations:
                citation_hits += 1
            if structured.get("refused"):
                continue
            summary = str(structured.get("executive_summary") or structured.get("answer") or "")
            if summary and len(summary) > 20:
                summary_hits += 1
            if "I don't know" in summary or "cannot determine" in summary.lower():
                if gt.get("expected_alert"):
                    hallucinations += 1
            conf = structured.get("confidence") or {}
            expected_conf = float(gt.get("expected_confidence") or 0.5)
            actual_conf = float(conf.get("score") or conf.get("value") or 50) / 100.0
            confidence_errors.append(abs(expected_conf - actual_conf))
            tools = structured.get("metadata", {}).get("tools_used") or []
            if tools:
                tool_hits += 1
        n = len(responses)
        score = (
            (citation_hits / n * 0.25)
            + (summary_hits / n * 0.25)
            + ((n - hallucinations) / n * 0.25)
            + ((1 - sum(confidence_errors) / n) * 0.25)
        ) * 100
        return EvaluationResult(
            subsystem="sebastian",
            score=round(score, 2),
            metrics={
                "citation_accuracy": round(citation_hits / n, 4),
                "hallucination_rate": round(hallucinations / n, 4),
                "tool_selection_accuracy": round(tool_hits / n, 4),
                "summary_accuracy": round(summary_hits / n, 4),
                "confidence_calibration_error": round(sum(confidence_errors) / n, 4),
                "evaluated": n,
            },
        )
