"""Shared evaluation data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EvaluationSample:
    """Single message evaluation unit — ground truth never exposed during simulation."""

    message_id: str
    scenario_id: str | None
    ground_truth: dict[str, Any]
    context: dict[str, Any]
    stages: list[dict[str, Any]] = field(default_factory=list)
    chat_id: int | None = None
    tick: int = 0


@dataclass(slots=True)
class StageMetric:
    stage: str
    latency_ms: float
    success: bool
    error: str | None = None


@dataclass(slots=True)
class LatencyMetrics:
    average_ms: float = 0.0
    p95_ms: float = 0.0
    per_stage: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class SubsystemScore:
    name: str
    score: float
    weight: float
    details: dict[str, Any] = field(default_factory=dict)
