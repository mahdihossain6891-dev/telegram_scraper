"""MetricsEngine — collects execution and pipeline metrics."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MetricsEngine:
    """Tracks simulation runtime metrics."""

    messages_generated: int = 0
    messages_processed: int = 0
    pipeline_throughput_per_tick: float = 0.0
    total_processing_time_ms: float = 0.0
    stage_duration_totals_ms: dict[str, float] = field(default_factory=dict)
    stage_duration_counts: dict[str, int] = field(default_factory=dict)
    active_users: int = 0
    active_conversations: int = 0
    scenario_distribution: dict[str, int] = field(default_factory=dict)
    alerts_generated: int = 0
    relationship_updates: int = 0
    behavior_updates: int = 0
    cases_created: int = 0
    processing_errors: int = 0
    dropped_messages: int = 0
    retry_count: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    session_duration_seconds: float = 0.0
    ticks_completed: int = 0
    _session_started_at: float | None = None

    def start_session(self) -> None:
        self._session_started_at = time.perf_counter()

    def end_session(self) -> None:
        if self._session_started_at is not None:
            self.session_duration_seconds = round(time.perf_counter() - self._session_started_at, 3)

    def record_message_generated(self, count: int = 1) -> None:
        self.messages_generated += count

    def record_message_processed(self, *, stage_durations: dict[str, float], success: bool) -> None:
        self.messages_processed += 1
        if not success:
            self.processing_errors += 1
        total = sum(stage_durations.values())
        self.total_processing_time_ms += total
        for stage, duration in stage_durations.items():
            self.stage_duration_totals_ms[stage] = self.stage_duration_totals_ms.get(stage, 0.0) + duration
            self.stage_duration_counts[stage] = self.stage_duration_counts.get(stage, 0) + 1

    def record_tick(self, *, messages_processed: int) -> None:
        self.ticks_completed += 1
        self.pipeline_throughput_per_tick = float(messages_processed)

    def record_scenario(self, scenario_id: str) -> None:
        self.scenario_distribution[scenario_id] = self.scenario_distribution.get(scenario_id, 0) + 1

    def record_alert(self) -> None:
        self.alerts_generated += 1

    def record_relationship_update(self, count: int = 1) -> None:
        self.relationship_updates += count

    def record_behavior_update(self) -> None:
        self.behavior_updates += 1

    def record_retry(self, count: int = 1) -> None:
        self.retry_count += count

    def update_resource_snapshot(self, *, memory_mb: float, cpu_percent: float) -> None:
        self.memory_usage_mb = memory_mb
        self.cpu_usage_percent = cpu_percent

    def average_stage_duration_ms(self, stage: str) -> float:
        count = self.stage_duration_counts.get(stage, 0)
        if count == 0:
            return 0.0
        return round(self.stage_duration_totals_ms[stage] / count, 3)

    def snapshot(self) -> dict[str, Any]:
        avg_stages = {
            stage: self.average_stage_duration_ms(stage)
            for stage in self.stage_duration_totals_ms
        }
        return {
            "messages_generated": self.messages_generated,
            "messages_processed": self.messages_processed,
            "pipeline_throughput_per_tick": self.pipeline_throughput_per_tick,
            "total_processing_time_ms": round(self.total_processing_time_ms, 3),
            "average_stage_duration_ms": avg_stages,
            "active_users": self.active_users,
            "active_conversations": self.active_conversations,
            "scenario_distribution": dict(self.scenario_distribution),
            "alerts_generated": self.alerts_generated,
            "relationship_updates": self.relationship_updates,
            "behavior_updates": self.behavior_updates,
            "cases_created": self.cases_created,
            "processing_errors": self.processing_errors,
            "dropped_messages": self.dropped_messages,
            "retry_count": self.retry_count,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "session_duration_seconds": self.session_duration_seconds,
            "ticks_completed": self.ticks_completed,
        }
