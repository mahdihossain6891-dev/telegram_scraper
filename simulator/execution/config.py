"""Execution engine configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from simulator.execution.labels import TickInterval


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Controls simulation execution behaviour."""

    tick_interval: TickInterval = TickInterval.ONE_MINUTE
    simulation_speed: float = 720.0
    max_messages_per_tick: int = 5
    max_active_conversations: int = 6
    max_active_users: int = 50
    queue_size: int = 1000
    pipeline_timeout_seconds: float = 30.0
    retry_count: int = 2
    checkpoint_frequency_ticks: int = 10
    metrics_interval_ticks: int = 1
    max_ticks: int = 100

    def __post_init__(self) -> None:
        if self.simulation_speed <= 0:
            raise ValueError("simulation_speed must be positive.")
        if self.max_messages_per_tick < 1:
            raise ValueError("max_messages_per_tick must be at least 1.")
        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick_interval": self.tick_interval.value,
            "simulation_speed": self.simulation_speed,
            "max_messages_per_tick": self.max_messages_per_tick,
            "max_active_conversations": self.max_active_conversations,
            "max_active_users": self.max_active_users,
            "queue_size": self.queue_size,
            "pipeline_timeout_seconds": self.pipeline_timeout_seconds,
            "retry_count": self.retry_count,
            "checkpoint_frequency_ticks": self.checkpoint_frequency_ticks,
            "metrics_interval_ticks": self.metrics_interval_ticks,
            "max_ticks": self.max_ticks,
        }
