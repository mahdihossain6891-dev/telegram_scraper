"""Relationship graph evaluator."""

from __future__ import annotations

from evaluation.metrics.types import EvaluationSample
from evaluation.validators.base import BaseEvaluator, EvaluationResult


class RelationshipEvaluator(BaseEvaluator):
    name = "relationship"

    def evaluate(self, samples: list[EvaluationSample]) -> EvaluationResult:
        expected_total = 0
        matched = 0
        actual_edges = 0
        missing = 0
        for sample in samples:
            gt = sample.ground_truth
            ctx = sample.context
            expected_rels = set(gt.get("expected_relationships") or [])
            actual_rels = ctx.get("relationships") or []
            actual_types = {str(r.get("type") or r.get("relationship") or "") for r in actual_rels}
            expected_total += len(expected_rels)
            actual_edges += len(actual_rels)
            for rel in expected_rels:
                if rel in actual_types or actual_rels:
                    matched += 1
                else:
                    missing += 1
        accuracy = matched / expected_total if expected_total else 1.0
        density = actual_edges / (len(samples) or 1)
        return EvaluationResult(
            subsystem="relationship",
            score=round(accuracy * 100, 2),
            metrics={
                "relationship_accuracy": round(accuracy, 4),
                "missing_links": missing,
                "graph_density": round(density, 4),
                "actual_edges": actual_edges,
            },
        )
