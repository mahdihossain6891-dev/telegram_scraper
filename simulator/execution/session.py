"""SimulationSession model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from simulator.enums import EnvironmentType
from simulator.execution.labels import SessionStatus


@dataclass(slots=True)
class SimulationSession:
    """One complete simulation run."""

    session_id: UUID
    simulation_name: str
    creation_time: datetime
    environment: EnvironmentType
    random_seed: int | None
    scenario_configuration: dict[str, Any]
    user_count: int
    group_count: int
    scenario_distribution: dict[str, float]
    simulation_speed: float
    status: SessionStatus = SessionStatus.INITIALIZING
    start_time: datetime | None = None
    end_time: datetime | None = None
    current_tick: int = 0
    elapsed_simulated_seconds: int = 0
    statistics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": str(self.session_id),
            "simulation_name": self.simulation_name,
            "creation_time": self.creation_time.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value,
            "environment": self.environment.value,
            "random_seed": self.random_seed,
            "scenario_configuration": dict(self.scenario_configuration),
            "user_count": self.user_count,
            "group_count": self.group_count,
            "scenario_distribution": dict(self.scenario_distribution),
            "simulation_speed": self.simulation_speed,
            "current_tick": self.current_tick,
            "elapsed_simulated_seconds": self.elapsed_simulated_seconds,
            "statistics": dict(self.statistics),
            "metadata": dict(self.metadata),
        }

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.CANCELLED,
        }
