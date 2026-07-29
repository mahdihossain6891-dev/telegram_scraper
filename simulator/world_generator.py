"""World generator — orchestrates persona, group, and membership creation."""

from __future__ import annotations

from dataclasses import dataclass

from simulator.generation_config import GenerationConfig
from simulator.groups.manager import GroupManager
from simulator.logger import get_prefixed_logger
from simulator.personas.manager import PersonaManager
from simulator.statistics import WorldStatistics, compute_world_statistics

_log = get_prefixed_logger("generator", name="world")


@dataclass(slots=True)
class GeneratedWorld:
    """Container for a fully generated simulation population."""

    personas: list
    groups: list
    memberships: dict[str, list[str]]
    statistics: WorldStatistics


class WorldGenerator:
    """High-level orchestrator for Phase 3 world building."""

    def __init__(self, config: GenerationConfig | None = None) -> None:
        self._config = config or GenerationConfig()
        self._persona_manager = PersonaManager(self._config)
        self._group_manager = GroupManager(self._config)

    @property
    def persona_manager(self) -> PersonaManager:
        return self._persona_manager

    @property
    def group_manager(self) -> GroupManager:
        return self._group_manager

    def generate(self) -> GeneratedWorld:
        _log.info(
            "Starting generation: %d users, %d groups (seed=%s)",
            self._config.user_count,
            self._config.group_count,
            self._config.random_seed,
        )
        personas = self._persona_manager.generate()
        groups = self._group_manager.generate()
        memberships = self._group_manager.assign_members(personas)
        stats = compute_world_statistics(personas, groups)
        _log.info(
            "Finished Generation: %d users, %d groups, %d memberships",
            stats.total_users,
            stats.total_groups,
            stats.total_memberships,
        )
        return GeneratedWorld(
            personas=personas,
            groups=groups,
            memberships=memberships,
            statistics=stats,
        )
