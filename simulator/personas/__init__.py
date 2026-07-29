"""Persona engine — fictional Telegram users."""

from __future__ import annotations

from simulator.personas.profiles import Persona
from simulator.personas.templates import (
    ActivityProfile,
    PersonalityType,
    RiskProfile,
    WritingStyle,
)

__all__ = [
    "ActivityProfile",
    "Persona",
    "PersonalityType",
    "RiskProfile",
    "WritingStyle",
]


def __getattr__(name: str):
    if name == "PersonaManager":
        from simulator.personas.manager import PersonaManager

        return PersonaManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
