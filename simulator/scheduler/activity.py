"""Activity profile rules for personas and groups."""

from __future__ import annotations

from datetime import datetime

from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona
from simulator.personas.templates import ActivityProfile


def is_persona_active(persona: Persona, when: datetime) -> bool:
    """Return whether a persona is plausibly active at ``when``."""
    profile = persona.activity_profile
    hour = when.hour
    weekday = when.weekday()
    weekend = weekday >= 5

    if profile == ActivityProfile.INACTIVE:
        return False
    if profile == ActivityProfile.ALWAYS_ONLINE:
        return True
    if profile == ActivityProfile.WEEKEND_ONLY and not weekend:
        return False
    if profile == ActivityProfile.MORNING_USER:
        return 6 <= hour <= 11
    if profile == ActivityProfile.NIGHT_OWL:
        return hour >= 20 or hour <= 3
    if profile == ActivityProfile.OFFICE_HOURS:
        return 9 <= hour <= 17 and not weekend
    if profile == ActivityProfile.HIGHLY_ACTIVE:
        return 8 <= hour <= 23
    if profile == ActivityProfile.LURKER:
        return hour in persona.online_hours[:1]
    if profile == ActivityProfile.OCCASIONAL_USER:
        return hour in persona.online_hours
    return hour in persona.online_hours


def group_activity_multiplier(group: Group, when: datetime) -> float:
    """Return a category-aware activity multiplier."""
    hour = when.hour
    weekend = when.weekday() >= 5
    category = group.category

    if category in {"programming", "technology", "artificial_intelligence"}:
        return 1.35 if not weekend and 9 <= hour <= 18 else 0.9
    if category == "gaming":
        return 1.5 if 18 <= hour <= 23 else 0.75
    if category == "marketplace":
        return 1.45 if weekend else 0.95
    if category == "crypto":
        return 1.55
    if category == "news":
        return 1.25 if 7 <= hour <= 22 else 0.9
    return 1.0
