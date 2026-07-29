"""Simulation tick system."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from simulator.execution.config import ExecutionConfig
from simulator.execution.labels import TickInterval


@dataclass(frozen=True, slots=True)
class SimulationTick:
    """One unit of simulated time advancement."""

    number: int
    interval: TickInterval
    simulated_time: datetime
    elapsed_simulated_seconds: int

    @classmethod
    def first(cls, start_time: datetime, config: ExecutionConfig) -> SimulationTick:
        return cls(
            number=1,
            interval=config.tick_interval,
            simulated_time=start_time,
            elapsed_simulated_seconds=0,
        )

    def advance(self, config: ExecutionConfig) -> SimulationTick:
        delta = self.interval.seconds()
        accelerated = max(1, int(delta * config.simulation_speed / 720.0))
        return SimulationTick(
            number=self.number + 1,
            interval=self.interval,
            simulated_time=self.simulated_time + timedelta(seconds=accelerated),
            elapsed_simulated_seconds=self.elapsed_simulated_seconds + accelerated,
        )
