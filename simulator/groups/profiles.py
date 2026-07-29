"""Fictional Telegram group model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class Group:
    """One fictional Telegram group / supergroup."""

    id: UUID
    telegram_chat_id: int
    name: str
    description: str
    category: str
    language: str
    region: str
    privacy: str
    maximum_members: int
    current_members: int
    creation_date: date
    owner_id: str
    moderator_ids: list[str]
    activity_level: str
    average_daily_messages: float
    topic_tags: list[str]
    member_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["id"] = str(self.id)
        data["creation_date"] = self.creation_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Group:
        payload = dict(data)
        payload["id"] = UUID(str(payload["id"]))
        raw_date = payload["creation_date"]
        if isinstance(raw_date, str):
            payload["creation_date"] = date.fromisoformat(raw_date)
        return cls(**payload)
