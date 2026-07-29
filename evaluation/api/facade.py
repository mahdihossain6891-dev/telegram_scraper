"""Evaluation API facade — isolated from production monitoring."""

from __future__ import annotations

from typing import Any

from evaluation.benchmark.runner import BenchmarkConfig, BenchmarkRunner
from evaluation.datasets.manager import DatasetManager
from evaluation.experiments.ab_test import ExperimentManager
from evaluation.history.store import HistoryStore
from evaluation.leaderboard.rankings import Leaderboard
from evaluation.observability.tracker import EvaluationTracker
from evaluation.regression.comparator import RegressionComparator
from evaluation.reports.engine import ReportEngine
from evaluation.scoring.weights import ScoringWeights


class EvaluationFacade:
    """Intelligence Validation & Benchmarking — simulation/evaluation only."""

    def __init__(
        self,
        *,
        runner: BenchmarkRunner | None = None,
        simulator_facade: Any | None = None,
    ) -> None:
        self._history = HistoryStore()
        self._datasets = DatasetManager()
        self._tracker = EvaluationTracker()
        self._runner = runner or BenchmarkRunner(
            datasets=self._datasets,
            history=self._history,
            tracker=self._tracker,
        )
        self._regression = RegressionComparator()
        self._experiments = ExperimentManager()
        self._leaderboard = Leaderboard(self._history)
        self._reports = ReportEngine()
        self._simulator = simulator_facade

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "module": "intelligence_evaluation",
            "environment": "evaluation",
            "isolated": True,
            "benchmark_count": len(self._history._records),
            "dataset_count": len(self._datasets.list()),
        }

    def run_benchmark(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = config or {}
        weights = None
        if cfg.get("weights"):
            w = cfg["weights"]
            weights = ScoringWeights(**{k: float(v) for k, v in w.items() if k in ScoringWeights.__dataclass_fields__})
        return self._runner.run(
            BenchmarkConfig(
                dataset_id=cfg.get("dataset_id"),
                version=str(cfg.get("version", "1.0.0")),
                ticks=int(cfg.get("ticks", 5)),
                users=int(cfg.get("users", 40)),
                groups=int(cfg.get("groups", 6)),
                random_seed=int(cfg.get("random_seed", 42)),
                weights=weights,
                tags=list(cfg.get("tags") or []),
            )
        )

    def evaluate_session(self, session_id: str) -> dict[str, Any]:
        inspections = self._get_session_inspections(session_id)
        performance = self._get_session_metrics(session_id)
        return self._runner.evaluate_session_inspections(
            inspections,
            version="session-eval",
            performance=performance,
        )

    def latest(self, session_id: str | None = None) -> dict[str, Any]:
        if session_id:
            return self.evaluate_session(session_id)
        records = self._history.list(limit=1)
        if not records:
            return self.run_benchmark({"ticks": 3, "users": 30, "groups": 4})
        return records[0]

    def history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._history.list(limit=limit)

    def trend(self) -> list[dict[str, Any]]:
        return self._history.iqs_trend()

    def compare_regression(self, baseline_id: str, candidate_id: str) -> dict[str, Any]:
        baseline = self._history.get(baseline_id).results
        candidate = self._history.get(candidate_id).results
        return self._regression.compare(baseline, candidate)

    def datasets(self) -> list[dict[str, Any]]:
        return self._datasets.list()

    def import_dataset(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._datasets.import_dataset(
            name=str(body.get("name", "imported")),
            scenario_ids=list(body.get("scenario_ids") or []),
            version=str(body.get("version", "1.0.0")),
            tags=list(body.get("tags") or []),
        )

    def leaderboard(self) -> dict[str, Any]:
        return self._leaderboard.rankings()

    def experiments(self) -> list[dict[str, Any]]:
        return self._experiments.list()

    def create_experiment(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._experiments.create(
            name=str(body.get("name", "experiment")),
            variant_a=str(body.get("variant_a", "A")),
            variant_b=str(body.get("variant_b", "B")),
        )

    def record_experiment(self, experiment_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._experiments.record(
            experiment_id,
            variant=str(body.get("variant", "a")),
            result=body.get("result") or {},
        )

    def reports(self, benchmark_id: str | None = None) -> list[dict[str, Any]]:
        if benchmark_id:
            record = self._history.get(benchmark_id)
            benchmark = record.results
            benchmark["benchmark_id"] = benchmark_id
            benchmark["samples_evaluated"] = benchmark.get("samples_evaluated")
        else:
            records = self._history.list(limit=1)
            benchmark = records[0]["results"] if records else {}
        return self._reports.generate(benchmark=benchmark)

    def export_report(self, report_id: str, benchmark_id: str | None, fmt: str) -> str:
        reports = self.reports(benchmark_id)
        for r in reports:
            if r["id"] == report_id:
                return self._reports.export(r, fmt)
        raise KeyError(f"Report {report_id} not found")

    def observability(self) -> dict[str, Any]:
        return {"events": self._tracker.snapshot()}

    def scoring_weights(self) -> dict[str, float]:
        return ScoringWeights().to_dict()

    def _get_session_inspections(self, session_id: str) -> dict[str, dict[str, Any]]:
        if self._simulator is None:
            from simulator.api.facade import SimulationConsoleFacade

            self._simulator = SimulationConsoleFacade()
        record = self._simulator._require_record(session_id)  # noqa: SLF001 — evaluation bridge
        self._simulator._ingest_runtime(record)  # noqa: SLF001
        return dict(record.pipeline_inspections)

    def _get_session_metrics(self, session_id: str) -> dict[str, Any]:
        if self._simulator is None:
            return {}
        record = self._simulator._require_record(session_id)  # noqa: SLF001
        return record.engine.metrics.snapshot()
