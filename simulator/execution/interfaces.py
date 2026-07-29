"""Execution engine interfaces for dependency injection."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from simulator.execution.session import SimulationSession
from simulator.execution.tick import SimulationTick


@runtime_checkable
class EventBusProtocol(Protocol):
    """Notification-only event broadcaster."""

    def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...

    def subscribe(self, event_type: str, handler: Any) -> None: ...


@runtime_checkable
class MetricsEngineProtocol(Protocol):
    """Collects execution metrics."""

    def record_message_generated(self) -> None: ...

    def record_message_processed(self, *, stage_durations: dict[str, float]) -> None: ...

    def snapshot(self) -> dict[str, Any]: ...


@runtime_checkable
class ResourceManagerProtocol(Protocol):
    """Monitors runtime resources."""

    def snapshot(self, *, queue_size: int, processing_rate: float) -> dict[str, Any]: ...

    def should_throttle(self) -> bool: ...


@runtime_checkable
class ExecutionStep(Protocol):
    """One step in the extensible simulation loop."""

    name: str

    def execute(
        self,
        *,
        session: SimulationSession,
        tick: SimulationTick,
        runtime: dict[str, Any],
    ) -> None: ...
