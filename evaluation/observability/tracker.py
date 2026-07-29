"""Evaluation observability tracker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ObsEvent:
    event_type: str
    detail: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


class EvaluationTracker:
    def __init__(self) -> None:
        self._events: list[ObsEvent] = []

    def record(self, event_type: str, detail: str, **metadata: Any) -> None:
        self._events.append(ObsEvent(event_type=event_type, detail=detail, metadata=metadata))
        if len(self._events) > 500:
            self._events = self._events[-500:]

    def log_benchmark(self, benchmark_id: str, duration: float, iqs: float) -> None:
        self.record("benchmark_complete", benchmark_id, duration_seconds=duration, iqs=iqs)

    def log_failure(self, detail: str, **metadata: Any) -> None:
        self.record("evaluation_failure", detail, **metadata)

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "event_type": e.event_type,
                "detail": e.detail,
                "timestamp": e.timestamp.isoformat(),
                "metadata": e.metadata,
            }
            for e in reversed(self._events[-100:])
        ]
