"""Benchmark history store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class BenchmarkRecord:
    benchmark_id: str
    dataset_id: str | None
    session_id: str | None
    version: str
    iqs: float
    results: dict[str, Any]
    duration_seconds: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "dataset_id": self.dataset_id,
            "session_id": self.session_id,
            "version": self.version,
            "iqs": self.iqs,
            "results": self.results,
            "duration_seconds": round(self.duration_seconds, 3),
            "created_at": self.created_at.isoformat(),
            "tags": list(self.tags),
        }


class HistoryStore:
    def __init__(self) -> None:
        self._records: list[BenchmarkRecord] = []

    def add(self, record: BenchmarkRecord) -> BenchmarkRecord:
        self._records.append(record)
        return record

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return [r.to_dict() for r in reversed(self._records[-limit:])]

    def get(self, benchmark_id: str) -> BenchmarkRecord:
        for r in self._records:
            if r.benchmark_id == benchmark_id:
                return r
        raise KeyError(f"Benchmark {benchmark_id} not found")

    def iqs_trend(self) -> list[dict[str, Any]]:
        return [
            {"benchmark_id": r.benchmark_id, "iqs": r.iqs, "created_at": r.created_at.isoformat(), "version": r.version}
            for r in self._records
        ]


def new_benchmark_id() -> str:
    return f"bench-{uuid4().hex[:12]}"
