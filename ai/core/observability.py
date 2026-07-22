"""AI platform observability — latency, cache, tokens, failures."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ObservabilityRecord:
    """One orchestration turn metrics."""

    llm_latency_ms: float = 0.0
    tool_latency_ms: dict[str, float] = field(default_factory=dict)
    rag_latency_ms: float = 0.0
    cache_hit: bool = False
    cache_miss: bool = False
    token_usage: int = 0
    prompt_version: str = ""
    provider: str = ""
    failures: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.perf_counter)

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.started_at) * 1000, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "llm_latency_ms": self.llm_latency_ms,
            "tool_latency_ms": dict(self.tool_latency_ms),
            "rag_latency_ms": self.rag_latency_ms,
            "cache_hit": self.cache_hit,
            "cache_miss": self.cache_miss,
            "token_usage": self.token_usage,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "failures": list(self.failures),
            "total_elapsed_ms": self.elapsed_ms(),
        }


class ObservabilityTracker:
    """Collects per-turn observability metrics."""

    def __init__(self) -> None:
        self._history: list[ObservabilityRecord] = []

    def start_turn(self) -> ObservabilityRecord:
        record = ObservabilityRecord()
        self._history.append(record)
        return record

    @property
    def history(self) -> list[ObservabilityRecord]:
        return list(self._history)

    def summary(self) -> dict[str, Any]:
        if not self._history:
            return {"turns": 0}
        hits = sum(1 for r in self._history if r.cache_hit)
        return {
            "turns": len(self._history),
            "cache_hits": hits,
            "cache_misses": len(self._history) - hits,
            "avg_elapsed_ms": round(
                sum(r.elapsed_ms() for r in self._history) / len(self._history), 2
            ),
        }
