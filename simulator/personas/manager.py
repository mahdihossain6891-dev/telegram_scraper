"""PersonaManager — generate, load, validate, export, and search fictional users."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from simulator.export_io import export_records_csv, export_records_json, load_records_json
from simulator.generation_config import GenerationConfig
from simulator.logger import get_prefixed_logger
from simulator.personas.generator import PersonaGenerator
from simulator.personas.profiles import Persona
from simulator.personas.validators import validate_persona, validate_unique_personas

_log = get_prefixed_logger("persona", name="manager")


class PersonaManager:
    """Manages the fictional user population (no message generation)."""

    def __init__(self, config: GenerationConfig | None = None) -> None:
        self._config = config or GenerationConfig()
        self._personas: dict[UUID, Persona] = {}

    @property
    def config(self) -> GenerationConfig:
        return self._config

    @property
    def personas(self) -> list[Persona]:
        return list(self._personas.values())

    def generate(self, count: int | None = None) -> list[Persona]:
        """Generate ``count`` personas (defaults to config user_count)."""
        total = self._config.user_count if count is None else count
        generator = PersonaGenerator(self._config)
        created = generator.generate(total)
        validate_unique_personas(created)
        for persona in created:
            self._personas[persona.id] = persona
        return created

    def generate_multiple(self, count: int) -> list[Persona]:
        return self.generate(count)

    def generate_one(self, index: int | None = None) -> Persona:
        idx = len(self._personas) if index is None else index
        generator = PersonaGenerator(self._config)
        persona = generator.generate_one(idx)
        validate_persona(persona)
        if any(p.username.lower() == persona.username.lower() for p in self._personas.values()):
            raise ValueError(f"username collision: {persona.username}")
        self._personas[persona.id] = persona
        _log.info("Generated User %s (@%s)", persona.display_name, persona.username)
        return persona

    def load(self, path: str | Path) -> list[Persona]:
        records = load_records_json(path)
        loaded = [Persona.from_dict(record) for record in records]
        validate_unique_personas(loaded)
        for persona in loaded:
            self._personas[persona.id] = persona
        _log.info("Loaded %d personas from %s", len(loaded), path)
        return loaded

    def validate(self, persona: Persona) -> None:
        validate_persona(persona)

    def validate_all(self) -> None:
        validate_unique_personas(self._personas.values())

    def get_by_id(self, persona_id: UUID | str) -> Persona | None:
        key = UUID(str(persona_id))
        return self._personas.get(key)

    def filter(self, **criteria: Any) -> list[Persona]:
        results: list[Persona] = []
        for persona in self._personas.values():
            if all(getattr(persona, key, None) == value for key, value in criteria.items()):
                results.append(persona)
        return results

    def search(self, query: str) -> list[Persona]:
        needle = query.strip().lower()
        if not needle:
            return []
        matches: list[Persona] = []
        for persona in self._personas.values():
            haystack = " ".join(
                [
                    persona.display_name,
                    persona.username,
                    persona.biography,
                    persona.city,
                    persona.country,
                    persona.profession,
                    " ".join(persona.interests),
                ]
            ).lower()
            if needle in haystack:
                matches.append(persona)
        return matches

    def export(self, path: str | Path, *, format: str = "json") -> Path:
        records = [p.to_dict() for p in self._personas.values()]
        target = Path(path)
        if format.lower() == "csv":
            return export_records_csv(records, target)
        if format.lower() == "json":
            return export_records_json(records, target)
        raise ValueError(f"Unsupported export format: {format}")

    def clear(self) -> None:
        self._personas.clear()

    def register(self, personas: Iterable[Persona]) -> None:
        for persona in personas:
            validate_persona(persona)
            self._personas[persona.id] = persona

    def update_memberships(self, persona_id: UUID, group_ids: list[str]) -> None:
        persona = self.get_by_id(persona_id)
        if persona is None:
            return
        persona.group_memberships = list(group_ids)
        persona.preferred_groups = list(group_ids)
