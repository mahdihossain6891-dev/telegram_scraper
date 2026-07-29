"""BenchmarkRunner — load dataset, run simulation, evaluate, store history."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from evaluation.benchmark.ground_truth import resolve_ground_truth
from evaluation.datasets.manager import DatasetManager
from evaluation.history.store import BenchmarkRecord, HistoryStore, new_benchmark_id
from evaluation.metrics.types import EvaluationSample
from evaluation.observability.tracker import EvaluationTracker
from evaluation.scoring.engine import ScoringEngine
from evaluation.scoring.weights import ScoringWeights
from simulator.execution.config import ExecutionConfig
from simulator.execution.engine import SimulationExecutionEngine
from simulator.execution.labels import TickInterval
from simulator.generation_config import GenerationConfig
from simulator.scenario.config import ScenarioConfig
from simulator.scenario.registry import ScenarioRegistry


@dataclass(slots=True)
class BenchmarkConfig:
    dataset_id: str | None = None
    version: str = "1.0.0"
    ticks: int = 5
    users: int = 40
    groups: int = 6
    random_seed: int = 42
    simulation_name: str = "benchmark-run"
    weights: ScoringWeights | None = None
    tags: list[str] = field(default_factory=list)


class BenchmarkRunner:
    """Orchestrates end-to-end intelligence evaluation."""

    def __init__(
        self,
        *,
        datasets: DatasetManager | None = None,
        history: HistoryStore | None = None,
        scoring: ScoringEngine | None = None,
        tracker: EvaluationTracker | None = None,
    ) -> None:
        self._datasets = datasets or DatasetManager()
        self._history = history or HistoryStore()
        self._scoring = scoring or ScoringEngine()
        self._tracker = tracker or EvaluationTracker()
        self._registry = ScenarioRegistry.with_builtins()

    @property
    def history(self) -> HistoryStore:
        return self._history

    def run(self, config: BenchmarkConfig | None = None) -> dict[str, Any]:
        cfg = config or BenchmarkConfig()
        t0 = time.perf_counter()
        try:
            samples, session_id, performance = self._execute_simulation(cfg)
            results = self._scoring.score(samples, performance=performance, weights=cfg.weights)
            duration = time.perf_counter() - t0
            iqs_val = float((results.get("iqs") or {}).get("iqs") or 0)
            record = BenchmarkRecord(
                benchmark_id=new_benchmark_id(),
                dataset_id=cfg.dataset_id,
                session_id=session_id,
                version=cfg.version,
                iqs=iqs_val,
                results=results,
                duration_seconds=duration,
                tags=list(cfg.tags),
            )
            self._history.add(record)
            self._tracker.log_benchmark(record.benchmark_id, duration, iqs_val)
            if cfg.dataset_id:
                try:
                    ds = self._datasets.get(cfg.dataset_id)
                    if not ds.frozen:
                        self._datasets.freeze(cfg.dataset_id)
                except KeyError:
                    pass
            return {
                "benchmark_id": record.benchmark_id,
                "session_id": session_id,
                "samples_evaluated": len(samples),
                "duration_seconds": round(duration, 3),
                **results,
                "confusion_matrix": self._confusion_matrix(samples),
                "trend": self._history.iqs_trend(),
            }
        except Exception as exc:
            self._tracker.log_failure(str(exc), config=cfg.version)
            raise

    def evaluate_session_inspections(
        self,
        inspections: dict[str, dict[str, Any]],
        *,
        version: str = "1.0.0",
        performance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate pre-captured pipeline inspections (from Threat Simulation session)."""
        samples = self._samples_from_inspections(inspections)
        results = self._scoring.score(samples, performance=performance or {})
        iqs_val = float((results.get("iqs") or {}).get("iqs") or 0)
        record = BenchmarkRecord(
            benchmark_id=new_benchmark_id(),
            dataset_id=None,
            session_id=None,
            version=version,
            iqs=iqs_val,
            results=results,
            duration_seconds=0.0,
        )
        self._history.add(record)
        return {
            "benchmark_id": record.benchmark_id,
            "samples_evaluated": len(samples),
            **results,
            "confusion_matrix": self._confusion_matrix(samples),
            "trend": self._history.iqs_trend(),
        }

    def _execute_simulation(self, cfg: BenchmarkConfig) -> tuple[list[EvaluationSample], str, dict[str, Any]]:
        gen_cfg = GenerationConfig(user_count=cfg.users, group_count=cfg.groups, random_seed=cfg.random_seed)
        exec_cfg = ExecutionConfig(
            max_ticks=cfg.ticks,
            tick_interval=TickInterval.ONE_MINUTE,
            max_messages_per_tick=8,
            checkpoint_frequency_ticks=max(2, cfg.ticks // 2),
        )
        engine = SimulationExecutionEngine(
            execution_config=exec_cfg,
            generation_config=gen_cfg,
            scenario_config=ScenarioConfig(random_seed=cfg.random_seed),
            simulation_name=cfg.simulation_name,
        )
        session = engine.initialize_session()
        session_id = str(session.session_id)
        for _ in range(cfg.ticks):
            try:
                if not engine.run_single_tick():
                    break
            except Exception:
                break
        snap = engine.runtime_snapshot()
        samples = self._samples_from_snapshot(snap, scenario_contexts=engine._runtime.get("scenario_contexts"))
        metrics = snap.get("metrics") or {}
        performance = {
            **metrics,
            "messages_per_sec": round(
                metrics.get("messages_processed", 0) / max(metrics.get("session_duration_seconds", 0.1), 0.1),
                2,
            ),
        }
        engine.shutdown()
        return samples, session_id, performance

    def _samples_from_snapshot(
        self,
        snap: dict[str, Any],
        *,
        scenario_contexts: dict[str, Any] | None = None,
    ) -> list[EvaluationSample]:
        samples: list[EvaluationSample] = []
        scenario_contexts = scenario_contexts or {}
        default_gt: dict[str, Any] | None = None
        for ctx in scenario_contexts.values():
            if getattr(ctx, "ground_truth", None):
                default_gt = ctx.ground_truth.to_dict()
                break
        for result in snap.get("pipeline_results") or []:
            ctx = result.get("context") if isinstance(result, dict) else None
            if ctx is None and hasattr(result, "context"):
                ctx = result.context.to_dict()
            if not ctx:
                continue
            msg_id = str(ctx.get("message_id") or "")
            stages_raw = ctx.get("stage_durations_ms") or {}
            errors = ctx.get("stage_errors") or {}
            stages = [
                {
                    "stage": name,
                    "latency_ms": ms,
                    "result": "error" if name in errors else "ok",
                    "error": errors.get(name),
                }
                for name, ms in stages_raw.items()
            ]
            gt = resolve_ground_truth(
                normalized_text=str(ctx.get("normalized_text") or ""),
                keywords=ctx.get("keywords") or [],
                has_alert=bool(ctx.get("alert")),
                registry=self._registry,
            )
            if default_gt and not gt.get("synthetic_evaluation"):
                gt = default_gt
            samples.append(
                EvaluationSample(
                    message_id=msg_id,
                    scenario_id=None,
                    ground_truth=gt,
                    context=ctx,
                    stages=stages,
                    tick=int(ctx.get("tick") or 0),
                )
            )
        return samples

    def _samples_from_inspections(self, inspections: dict[str, dict[str, Any]]) -> list[EvaluationSample]:
        samples: list[EvaluationSample] = []
        for msg_id, inspection in inspections.items():
            ctx = inspection.get("context") or inspection.get("final_context") or {}
            gt = inspection.get("ground_truth") or resolve_ground_truth(
                normalized_text=str(ctx.get("normalized_text") or ""),
                keywords=ctx.get("keywords") or [],
                has_alert=bool(ctx.get("alert")),
                registry=self._registry,
            )
            samples.append(
                EvaluationSample(
                    message_id=str(msg_id),
                    scenario_id=inspection.get("scenario_id"),
                    ground_truth=gt,
                    context=ctx,
                    stages=inspection.get("stages") or [],
                )
            )
        return samples

    def _confusion_matrix(self, samples: list[EvaluationSample]) -> dict[str, int]:
        tp = fp = fn = tn = 0
        for s in samples:
            exp = bool(s.ground_truth.get("expected_alert"))
            got = bool(s.context.get("alert"))
            if exp and got:
                tp += 1
            elif not exp and got:
                fp += 1
            elif exp and not got:
                fn += 1
            else:
                tn += 1
        return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}
