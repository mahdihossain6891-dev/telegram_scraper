"""Tests for Intelligence Evaluation Framework."""

from __future__ import annotations

from evaluation.api.facade import EvaluationFacade
from evaluation.benchmark.ground_truth import resolve_ground_truth
from evaluation.benchmark.runner import BenchmarkConfig, BenchmarkRunner
from evaluation.metrics.classification import compute_classification
from evaluation.regression.comparator import RegressionComparator
from evaluation.reports.engine import ReportEngine
from evaluation.scoring.iqs import compute_iqs
from evaluation.scoring.weights import ScoringWeights
from evaluation.validators.base import EvaluationResult
from evaluation.validators.keyword import KeywordEvaluator
from evaluation.metrics.types import EvaluationSample


def test_health_isolated() -> None:
    facade = EvaluationFacade()
    health = facade.health()
    assert health["ok"] is True
    assert health["isolated"] is True
    assert health["environment"] == "evaluation"


def test_ground_truth_from_synthetic_scenario() -> None:
    gt = resolve_ground_truth(normalized_text="please verify account transfer fee urgent")
    assert gt.get("expected_alert") is True
    assert gt.get("synthetic_evaluation") is True


def test_classification_metrics() -> None:
    m = compute_classification(8, 2, 1, 9)
    assert m.precision == 0.8
    assert m.recall == 8 / 9
    assert m.f1_score > 0


def test_keyword_evaluator() -> None:
    samples = [
        EvaluationSample(
            message_id="1",
            scenario_id="synthetic_financial_fraud",
            ground_truth={"expected_keywords": ["transfer", "verify"], "expected_alert": True},
            context={"keywords": ["transfer", "verify"], "alert": {"type": "risk"}},
            stages=[{"stage": "keyword", "latency_ms": 1.2, "result": "ok"}],
        )
    ]
    result = KeywordEvaluator().evaluate(samples)
    assert result.score > 0
    assert "precision" in result.metrics


def test_iqs_computation() -> None:
    results = {
        "keyword": EvaluationResult("keyword", 80.0),
        "risk": EvaluationResult("risk", 75.0),
        "behavior": EvaluationResult("behavior", 70.0),
        "relationship": EvaluationResult("relationship", 65.0),
        "alert": EvaluationResult("alert", 90.0),
        "sebastian": EvaluationResult("sebastian", 60.0),
    }
    iqs = compute_iqs(results, performance_score=85.0)
    assert 0 <= iqs.iqs <= 100
    assert "keyword" in iqs.components


def test_benchmark_runner_reproducible() -> None:
    runner = BenchmarkRunner()
    cfg = BenchmarkConfig(ticks=2, users=50, groups=5, random_seed=42)
    a = runner.run(cfg)
    b = runner.run(cfg)
    assert "iqs" in a
    assert "confusion_matrix" in a
    assert a["samples_evaluated"] == b["samples_evaluated"]


def test_regression_detection() -> None:
    comp = RegressionComparator()
    baseline = {"iqs": {"iqs": 70.0}, "subsystems": {"keyword": {"score": 70}}}
    improved = {"iqs": {"iqs": 85.0}, "subsystems": {"keyword": {"score": 90}}}
    result = comp.compare(baseline, improved)
    assert result["verdict"] == "improved"
    assert result["iqs_delta"] == 15.0


def test_report_generation() -> None:
    engine = ReportEngine()
    benchmark = {
        "iqs": {"iqs": 78.5, "detection_quality": 80, "alert_quality": 75},
        "subsystems": {"pipeline": {"metrics": {"stages": {}}}},
        "samples_evaluated": 10,
    }
    reports = engine.generate(benchmark=benchmark)
    assert len(reports) >= 4
    csv = engine.export(reports[0], "csv")
    assert "metric" in csv


def test_configurable_weights() -> None:
    w = ScoringWeights(keyword=0.5, risk=0.1, behavior=0.1, relationship=0.1, alert=0.1, sebastian=0.05, performance=0.05)
    norm = w.normalized()
    assert abs(sum(norm.to_dict().values()) - 1.0) < 0.01
