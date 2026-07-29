"""Classification metrics — precision, recall, F1, etc."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ClassificationMetrics:
    precision: float = 0.0
    recall: float = 0.0
    accuracy: float = 0.0
    f1_score: float = 0.0
    false_positives: int = 0
    false_negatives: int = 0
    true_positives: int = 0
    true_negatives: int = 0

    def to_dict(self) -> dict[str, float | int]:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "accuracy": round(self.accuracy, 4),
            "f1_score": round(self.f1_score, 4),
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
        }


def compute_classification(tp: int, fp: int, fn: int, tn: int) -> ClassificationMetrics:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return ClassificationMetrics(
        precision=precision,
        recall=recall,
        accuracy=accuracy,
        f1_score=f1,
        false_positives=fp,
        false_negatives=fn,
        true_positives=tp,
        true_negatives=tn,
    )
