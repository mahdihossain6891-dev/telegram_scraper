"""GroupManager — generate, load, search, export, and assign members."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from simulator.export_io import export_records_csv, export_records_json, load_records_json
from simulator.generation_config import GenerationConfig
from simulator.groups.generator import GroupGenerator
from simulator.groups.membership import MembershipEngine
from simulator.groups.profiles import Group
from simulator.groups.validators import (
    validate_group,
    validate_membership_integrity,
    validate_unique_groups,
)
from simulator.logger import get_prefixed_logger
from simulator.personas.profiles import Persona

_log = get_prefixed_logger("group", name="manager")


class GroupManager:
    """Manages fictional Telegram groups and memberships."""

    def __init__(self, config: GenerationConfig | None = None) -> None:
        self._config = config or GenerationConfig()
        self._groups: dict[UUID, Group] = {}

    @property
    def config(self) -> GenerationConfig:
        return self._config

    @property
    def groups(self) -> list[Group]:
        return list(self._groups.values())

    def generate(self, count: int | None = None) -> list[Group]:
        total = self._config.group_count if count is None else count
        generator = GroupGenerator(self._config)
        created = generator.generate(total)
        validate_unique_groups(created)
        for group in created:
            self._groups[group.id] = group
        return created

    def generate_one(self, index: int | None = None) -> Group:
        idx = len(self._groups) if index is None else index
        generator = GroupGenerator(self._config)
        group = generator.generate_one(idx)
        validate_group(group)
        self._groups[group.id] = group
        _log.info("Created Group %s", group.name)
        return group

    def load(self, path: str | Path) -> list[Group]:
        records = load_records_json(path)
        loaded = [Group.from_dict(record) for record in records]
        validate_unique_groups(loaded)
        for group in loaded:
            self._groups[group.id] = group
        _log.info("Loaded %d groups from %s", len(loaded), path)
        return loaded

    def validate(self, group: Group) -> None:
        validate_group(group)

    def validate_all(self, personas: Iterable[Persona] | None = None) -> None:
        validate_unique_groups(self._groups.values())
        if personas is not None:
            known = {str(p.id) for p in personas}
            validate_membership_integrity(self._groups.values(), known_persona_ids=known)

    def get_by_id(self, group_id: UUID | str) -> Group | None:
        return self._groups.get(UUID(str(group_id)))

    def search(self, query: str) -> list[Group]:
        needle = query.strip().lower()
        if not needle:
            return []
        matches: list[Group] = []
        for group in self._groups.values():
            haystack = " ".join(
                [group.name, group.description, group.category, group.region]
                + group.topic_tags
            ).lower()
            if needle in haystack:
                matches.append(group)
        return matches

    def assign_members(self, personas: list[Persona]) -> dict[str, list[str]]:
        """Assign personas to groups and populate rosters."""
        engine = MembershipEngine(self._config)
        memberships = engine.assign(personas, self.groups)
        known = {str(p.id) for p in personas}
        validate_membership_integrity(self._groups.values(), known_persona_ids=known)
        return memberships

    def export(self, path: str | Path, *, format: str = "json") -> Path:
        records = [g.to_dict() for g in self._groups.values()]
        target = Path(path)
        if format.lower() == "csv":
            return export_records_csv(records, target)
        if format.lower() == "json":
            return export_records_json(records, target)
        raise ValueError(f"Unsupported export format: {format}")

    def clear(self) -> None:
        self._groups.clear()

    def register(self, groups: Iterable[Group]) -> None:
        for group in groups:
            validate_group(group)
            self._groups[group.id] = group
