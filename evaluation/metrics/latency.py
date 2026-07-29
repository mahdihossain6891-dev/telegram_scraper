"""Latency aggregation helpers."""

from __future__ import annotations

from evaluation.metrics.types import LatencyMetrics


def aggregate_latency(stage_durations: list[dict[str, float]]) -> LatencyMetrics:
    if not stage_durations:
        return LatencyMetrics()
    per_stage: dict[str, list[float]] = {}
    totals: list[float] = []
    for row in stage_durations:
        tick_total = sum(row.values())
        totals.append(tick_total)
        for stage, ms in row.items():
            per_stage.setdefault(stage, []).append(ms)
    avg_per_stage = {k: sum(v) / len(v) for k, v in per_stage.items()}
    sorted_totals = sorted(totals)
    p95_idx = max(0, int(len(sorted_totals) * 0.95) - 1)
    return LatencyMetrics(
        average_ms=sum(totals) / len(totals),
        p95_ms=sorted_totals[p95_idx] if sorted_totals else 0.0,
        per_stage={k: round(v, 3) for k, v in avg_per_stage.items()},
    )
