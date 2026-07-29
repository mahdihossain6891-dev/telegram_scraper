"""Scheduler manager facade."""

from __future__ import annotations

from datetime import datetime

from simulator.generation_config import GenerationConfig
from simulator.groups.profiles import Group
from simulator.scheduler.engine import SchedulerEngine
from simulator.scheduler.timing import SimulationClock
from simulator.personas.profiles import Persona


class SchedulerManager:
    """High-level scheduler facade for conversation generation."""

    def __init__(
        self,
        config: GenerationConfig | None = None,
        *,
        start_time: datetime | None = None,
    ) -> None:
        self._config = config or GenerationConfig()
        self._engine = SchedulerEngine(self._config)
        self._clock = SimulationClock(
            current_time=start_time or datetime(2026, 1, 1, 9, 0, 0),
            speed_multiplier=self._config.simulation_speed_multiplier,
        )

    @property
    def current_time(self) -> datetime:
        return self._clock.current_time

    def active_users_for_group(self, personas: list[Persona], group: Group) -> list[Persona]:
        return self._engine.active_users_for_group(personas, group, self._clock.current_time)

    def choose_participants(self, personas: list[Persona], group: Group) -> list[Persona]:
        return self._engine.choose_participants(personas, group, self._clock.current_time)

    def advance_for_message(
        self,
        persona: Persona,
        group: Group,
        *,
        is_reply: bool,
        index: int,
    ) -> datetime:
        delay = self._engine.next_delay_seconds(
            persona,
            group,
            self._clock.current_time,
            is_reply=is_reply,
            index=index,
        )
        return self._clock.advance_seconds(delay)
