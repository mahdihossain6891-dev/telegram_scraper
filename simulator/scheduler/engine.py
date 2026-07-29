"""Deterministic activity scheduler."""

from __future__ import annotations

import random
from datetime import datetime

from simulator.generation_config import GenerationConfig
from simulator.groups.profiles import Group
from simulator.logger import get_prefixed_logger
from simulator.personas.profiles import Persona
from simulator.scheduler.activity import is_persona_active
from simulator.scheduler.timing import TimingPlanner

_log = get_prefixed_logger("scheduler", name="engine")


class SchedulerEngine:
    """Resolves who is available to speak and when."""

    def __init__(self, config: GenerationConfig) -> None:
        self._config = config
        self._rng = random.Random((config.random_seed or 0) + 40_000)
        self._timing = TimingPlanner(config, seed=(config.random_seed or 0) + 41_000)

    def active_users_for_group(
        self,
        personas: list[Persona],
        group: Group,
        when: datetime,
    ) -> list[Persona]:
        group_member_ids = set(group.member_ids)
        active = [
            persona
            for persona in personas
            if str(persona.id) in group_member_ids and is_persona_active(persona, when)
        ]
        active.sort(key=lambda persona: (persona.average_messages_per_day, str(persona.id)), reverse=True)
        if active:
            _log.info("Activated User set for %s: %d", group.name, len(active))
        return active

    def choose_participants(
        self,
        personas: list[Persona],
        group: Group,
        when: datetime,
        *,
        minimum: int = 2,
        maximum: int = 6,
    ) -> list[Persona]:
        active = self.active_users_for_group(personas, group, when)
        if len(active) <= minimum:
            return active
        target = min(len(active), self._rng.randint(minimum, maximum))
        pool = active[: max(target * 2, target)]
        chosen = self._rng.sample(pool, k=target)
        chosen.sort(key=lambda persona: str(persona.id))
        return chosen

    def next_delay_seconds(
        self,
        persona: Persona,
        group: Group,
        when: datetime,
        *,
        is_reply: bool,
        index: int,
    ) -> int:
        return self._timing.next_delay_seconds(
            persona,
            group,
            when=when,
            is_reply=is_reply,
            index=index + when.hour,
        )
