"""Simulation clock and delay planning."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from simulator.generation_config import GenerationConfig
from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona
from simulator.scheduler.activity import group_activity_multiplier


@dataclass(slots=True)
class SimulationClock:
    """Tracks simulated time independently from wall clock time."""

    current_time: datetime
    speed_multiplier: float

    def advance_seconds(self, seconds: int) -> datetime:
        self.current_time = self.current_time + timedelta(seconds=seconds)
        return self.current_time


class TimingPlanner:
    """Produces deterministic message delays."""

    def __init__(self, config: GenerationConfig, seed: int | None = None) -> None:
        self._config = config
        self._rng = random.Random((seed or config.random_seed or 0) + 30_000)

    def next_delay_seconds(
        self,
        persona: Persona,
        group: Group,
        *,
        when: datetime,
        is_reply: bool,
        index: int,
    ) -> int:
        baseline = max(5, int(self._config.average_delay_seconds))
        persona_bias = max(0.35, 1.4 - min(persona.average_messages_per_day / 120.0, 0.9))
        group_bias = 1.0 / max(0.55, group_activity_multiplier(group, when))
        reply_bias = 0.7 if is_reply else 1.15
        jitter = self._rng.uniform(0.45, 1.85)
        burst = 0.7 if index < 3 else 1.0
        return max(4, int(baseline * persona_bias * group_bias * reply_bias * jitter * burst))
