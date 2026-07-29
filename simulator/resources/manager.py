"""ResourceManager — monitors runtime resources and throttling."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ResourceManager:
    """Monitors CPU, memory, queue sizes, and processing rate."""

    memory_limit_mb: float = 2048.0
    cpu_limit_percent: float = 90.0
    queue_limit: int = 1000
    _last_snapshot: dict[str, Any] = field(default_factory=dict, init=False)
    _processing_times: list[float] = field(default_factory=list, init=False)

    def snapshot(self, *, queue_size: int, processing_rate: float) -> dict[str, Any]:
        memory_mb = self._estimate_memory_mb()
        cpu_percent = self._estimate_cpu_percent()
        record = {
            "memory_usage_mb": memory_mb,
            "cpu_usage_percent": cpu_percent,
            "queue_size": queue_size,
            "processing_rate": processing_rate,
            "estimated_remaining_ticks": self._estimate_remaining_ticks(processing_rate),
            "timestamp": time.time(),
        }
        self._last_snapshot = record
        return record

    def should_throttle(self) -> bool:
        if not self._last_snapshot:
            return False
        return (
            self._last_snapshot.get("memory_usage_mb", 0) >= self.memory_limit_mb
            or self._last_snapshot.get("cpu_usage_percent", 0) >= self.cpu_limit_percent
            or self._last_snapshot.get("queue_size", 0) >= self.queue_limit
        )

    def record_processing_duration(self, duration_ms: float) -> None:
        self._processing_times.append(duration_ms)
        if len(self._processing_times) > 100:
            self._processing_times = self._processing_times[-100:]

    def _estimate_memory_mb(self) -> float:
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if os.name == "nt":
                return round(usage / (1024 * 1024), 2)
            return round(usage / 1024, 2)
        except Exception:  # noqa: BLE001
            return 0.0

    def _estimate_cpu_percent(self) -> float:
        if not self._processing_times:
            return 0.0
        avg_ms = sum(self._processing_times) / len(self._processing_times)
        return round(min(100.0, avg_ms / 10.0), 2)

    def _estimate_remaining_ticks(self, processing_rate: float) -> float | None:
        if processing_rate <= 0:
            return None
        return round(1.0 / processing_rate, 2)
