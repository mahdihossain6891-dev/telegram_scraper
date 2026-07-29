"""Calendar helpers for active windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona


@dataclass(frozen=True, slots=True)
class ActivityWindow:
    """A lightweight summary of why an entity is active."""

    entity_id: str
    window_type: str
    hour: int
    weekend: bool


def persona_window(persona: Persona, when: datetime) -> ActivityWindow:
    return ActivityWindow(
        entity_id=str(persona.id),
        window_type=persona.activity_level,
        hour=when.hour,
        weekend=when.weekday() >= 5,
    )


def group_window(group: Group, when: datetime) -> ActivityWindow:
    return ActivityWindow(
        entity_id=str(group.id),
        window_type=group.activity_level,
        hour=when.hour,
        weekend=when.weekday() >= 5,
    )
