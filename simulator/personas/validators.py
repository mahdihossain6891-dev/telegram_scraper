"""Persona validation rules."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from simulator.exceptions import PersonaValidationError
from simulator.personas.profiles import Persona
from simulator.personas.templates import SUPPORTED_LANGUAGES, VALID_ACTIVITY_PROFILES, VALID_RISK_PROFILES


def validate_persona(persona: Persona) -> None:
    """Raise ``PersonaValidationError`` when a persona is invalid."""
    errors: list[str] = []

    if not isinstance(persona.id, UUID):
        errors.append("id must be a UUID")
    if persona.telegram_id <= 0:
        errors.append("telegram_id must be positive")
    if not persona.username or not persona.username.replace("_", "").isalnum():
        errors.append("username must be alphanumeric with optional underscores")
    if persona.language not in SUPPORTED_LANGUAGES:
        errors.append(f"unsupported language: {persona.language}")
    if persona.activity_level not in VALID_ACTIVITY_PROFILES:
        errors.append(f"invalid activity_level: {persona.activity_level}")
    if persona.risk_profile not in VALID_RISK_PROFILES:
        errors.append(f"invalid risk_profile: {persona.risk_profile}")
    if not 0.0 <= persona.emoji_frequency <= 1.0:
        errors.append("emoji_frequency must be between 0 and 1")
    if persona.average_message_length < 1:
        errors.append("average_message_length must be positive")
    if persona.relationship_capacity < 0:
        errors.append("relationship_capacity must be non-negative")

    if errors:
        raise PersonaValidationError("; ".join(errors))


def validate_unique_personas(personas: Iterable[Persona]) -> None:
    """Ensure UUIDs, Telegram IDs, and usernames are unique within a batch."""
    uuids: set[str] = set()
    telegram_ids: set[int] = set()
    usernames: set[str] = set()
    for persona in personas:
        uid = str(persona.id)
        if uid in uuids:
            raise PersonaValidationError(f"duplicate persona UUID: {uid}")
        uuids.add(uid)
        if persona.telegram_id in telegram_ids:
            raise PersonaValidationError(f"duplicate telegram_id: {persona.telegram_id}")
        telegram_ids.add(persona.telegram_id)
        key = persona.username.lower()
        if key in usernames:
            raise PersonaValidationError(f"duplicate username: {persona.username}")
        usernames.add(key)
        validate_persona(persona)
