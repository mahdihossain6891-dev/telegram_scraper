"""Future provider contracts — responsibilities only (Phase 1).

Implementations will be supplied in later phases and injected into managers
or orchestrators without rewriting the control plane.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SimulationProvider(Protocol):
    """Coordinates simulation lifecycle hooks (future phase)."""

    def on_start(self, *, configuration: dict[str, Any]) -> None: ...

    def on_stop(self) -> None: ...

    def on_reset(self) -> None: ...


@runtime_checkable
class MessageBatchProvider(Protocol):
    """Supplies synthetic or replayed message batches (legacy Phase 1 stub)."""

    def next_batch(self, *, limit: int) -> list[dict[str, Any]]: ...


@runtime_checkable
class ScenarioProvider(Protocol):
    """Defines scripted simulation scenarios (future phase)."""

    def list_scenarios(self) -> list[dict[str, Any]]: ...

    def load_scenario(self, scenario_id: str) -> dict[str, Any]: ...


@runtime_checkable
class ConversationProvider(Protocol):
    """Generates multi-turn conversations (future phase)."""

    def generate_turn(self, *, context: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class PersonaProvider(Protocol):
    """Defines synthetic user personas (future phase)."""

    def get_persona(self, persona_id: str) -> dict[str, Any]: ...


@runtime_checkable
class SchedulerProvider(Protocol):
    """Schedules simulation events over time (future phase)."""

    def schedule(self, *, events: list[dict[str, Any]]) -> None: ...

    def cancel_all(self) -> None: ...
