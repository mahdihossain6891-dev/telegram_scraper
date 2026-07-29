"""Conversation message models for simulator-only generated traffic."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from simulator.enums import EnvironmentType


class GeneratedMessageType(str, Enum):
    NORMAL = "normal"
    REPLY = "reply"
    MENTION = "mention"
    FORWARD = "forward"
    EDITED = "edited"
    DELETED = "deleted"
    MEDIA = "media"
    PHOTO = "photo"
    VIDEO = "video"
    VOICE_NOTE = "voice_note"
    STICKER = "sticker"
    GIF = "gif"
    DOCUMENT = "document"
    POLL = "poll"
    LOCATION = "location"
    PINNED = "pinned"
    REACTION = "reaction"


@dataclass(slots=True)
class GeneratedMessage:
    """One simulator-generated Telegram-like message."""

    id: UUID
    message_id: int
    sender_id: str
    chat_id: str
    timestamp: datetime
    reply_to_message_id: int | None
    message_type: str
    message_text: str
    media_metadata: dict[str, Any]
    forward_source: str | None
    edited: bool
    deleted: bool
    language: str
    conversation_id: str
    environment: EnvironmentType
    mentions: list[str] = field(default_factory=list)
    reactions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["id"] = str(self.id)
        data["timestamp"] = self.timestamp.isoformat()
        data["environment"] = self.environment.value
        return data
