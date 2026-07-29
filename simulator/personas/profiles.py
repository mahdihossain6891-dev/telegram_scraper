"""Fictional Telegram user persona model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

from simulator.personas.templates import (
    ActivityProfile,
    PersonalityType,
    RiskProfile,
    WritingStyle,
)


@dataclass(slots=True)
class Persona:
    """One fictional Telegram user with consistent personality metadata."""

    id: UUID
    telegram_id: int
    display_name: str
    username: str
    biography: str
    age_range: str
    language: str
    timezone: str
    country: str
    city: str
    profession: str
    education: str
    interests: list[str]
    favorite_topics: list[str]
    activity_level: str
    risk_profile: str
    writing_style: str
    emoji_frequency: float
    average_message_length: int
    average_messages_per_day: float
    average_replies: float
    average_forwards: float
    deletion_rate: float
    editing_rate: float
    online_hours: list[int]
    weekend_activity: float
    night_activity: float
    preferred_groups: list[str]
    relationship_capacity: int
    account_creation_date: date
    profile_photo_exists: bool
    verified: bool
    bot: bool
    personality_type: str
    gender: str | None = None
    group_memberships: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["id"] = str(self.id)
        data["account_creation_date"] = self.account_creation_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Persona:
        payload = dict(data)
        payload["id"] = UUID(str(payload["id"]))
        raw_date = payload["account_creation_date"]
        if isinstance(raw_date, str):
            payload["account_creation_date"] = date.fromisoformat(raw_date)
        return cls(**payload)

    @property
    def activity_profile(self) -> ActivityProfile:
        return ActivityProfile(self.activity_level)

    @property
    def personality(self) -> PersonalityType:
        return PersonalityType(self.personality_type)

    @property
    def risk(self) -> RiskProfile:
        return RiskProfile(self.risk_profile)

    @property
    def style(self) -> WritingStyle:
        return WritingStyle(self.writing_style)
