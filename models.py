"""Document models for MongoDB-backed Telegram data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Chat:
    """A Telegram chat, channel, or group."""

    id: int
    title: str | None = None
    username: str | None = None
    chat_type: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    risk_score: int = 0
    risk_level: str = "Low"
    risk_factors: list[str] = field(default_factory=list)

    def to_doc(self) -> dict[str, Any]:
        return {
            "_id": self.id,
            "title": self.title,
            "username": self.username,
            "chat_type": self.chat_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "risk_factors": list(self.risk_factors),
        }

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> Chat:
        return cls(
            id=int(doc["_id"]),
            title=doc.get("title"),
            username=doc.get("username"),
            chat_type=doc.get("chat_type"),
            created_at=doc.get("created_at") or utcnow(),
            updated_at=doc.get("updated_at") or utcnow(),
            risk_score=int(doc.get("risk_score") or 0),
            risk_level=str(doc.get("risk_level") or "Low"),
            risk_factors=[str(x) for x in (doc.get("risk_factors") or [])],
        )


@dataclass
class User:
    """A Telegram user observed as a message sender."""

    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_doc(self) -> dict[str, Any]:
        return {
            "_id": self.id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> User:
        return cls(
            id=int(doc["_id"]),
            username=doc.get("username"),
            first_name=doc.get("first_name"),
            last_name=doc.get("last_name"),
            created_at=doc.get("created_at") or utcnow(),
            updated_at=doc.get("updated_at") or utcnow(),
        )


@dataclass
class Message:
    """A single Telegram message stored for analysis."""

    message_id: int
    chat_id: int
    id: int | None = None
    sender_id: int | None = None
    timestamp: datetime | None = None
    text: str | None = None
    media_type: str | None = None
    reply_to_message_id: int | None = None
    forward_from_chat_id: int | None = None
    forward_from_message_id: int | None = None
    views: int | None = None
    scraped_at: datetime = field(default_factory=utcnow)
    risk_score: int = 0
    risk_level: str = "Low"
    risk_factors: list[str] = field(default_factory=list)

    def to_doc(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "text": self.text,
            "media_type": self.media_type,
            "reply_to_message_id": self.reply_to_message_id,
            "forward_from_chat_id": self.forward_from_chat_id,
            "forward_from_message_id": self.forward_from_message_id,
            "views": self.views,
            "scraped_at": self.scraped_at,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "risk_factors": list(self.risk_factors),
        }
        if self.id is not None:
            doc["_id"] = self.id
        return doc

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> Message:
        return cls(
            id=int(doc["_id"]),
            message_id=int(doc["message_id"]),
            chat_id=int(doc["chat_id"]),
            sender_id=doc.get("sender_id"),
            timestamp=doc.get("timestamp"),
            text=doc.get("text"),
            media_type=doc.get("media_type"),
            reply_to_message_id=doc.get("reply_to_message_id"),
            forward_from_chat_id=doc.get("forward_from_chat_id"),
            forward_from_message_id=doc.get("forward_from_message_id"),
            views=doc.get("views"),
            scraped_at=doc.get("scraped_at") or utcnow(),
            risk_score=int(doc.get("risk_score") or 0),
            risk_level=str(doc.get("risk_level") or "Low"),
            risk_factors=[str(x) for x in (doc.get("risk_factors") or [])],
        )


@dataclass
class ExtractedEntity:
    """An entity (URL, hashtag, etc.) extracted from a message."""

    message_row_id: int
    entity_type: str
    entity_value: str
    id: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    created_at: datetime = field(default_factory=utcnow)

    def to_doc(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "message_row_id": self.message_row_id,
            "entity_type": self.entity_type,
            "entity_value": self.entity_value,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "created_at": self.created_at,
        }
        if self.id is not None:
            doc["_id"] = self.id
        return doc

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> ExtractedEntity:
        return cls(
            id=int(doc["_id"]),
            message_row_id=int(doc["message_row_id"]),
            entity_type=str(doc["entity_type"]),
            entity_value=str(doc["entity_value"]),
            start_offset=doc.get("start_offset"),
            end_offset=doc.get("end_offset"),
            created_at=doc.get("created_at") or utcnow(),
        )


KEYWORD_CATEGORIES = frozenset({"narcotics", "human_trafficking", "firearms"})


@dataclass
class UserActivity:
    """Incremental per-user activity rollup across monitored chats."""

    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    message_count: int = 0
    suspicious_count: int = 0
    keywords: dict[str, int] = field(default_factory=dict)
    categories: dict[str, int] = field(default_factory=dict)
    chat_ids: list[int] = field(default_factory=list)
    by_chat: dict[str, dict[str, Any]] = field(default_factory=dict)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    risk_score: int = 0
    risk_level: str = "Low"
    risk_factors: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def display_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        if parts:
            return " ".join(parts)
        if self.username:
            return f"@{self.username}"
        return f"User {self.id}"

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> UserActivity:
        return cls(
            id=int(doc["_id"]),
            username=doc.get("username"),
            first_name=doc.get("first_name"),
            last_name=doc.get("last_name"),
            message_count=int(doc.get("message_count") or 0),
            suspicious_count=int(doc.get("suspicious_count") or 0),
            keywords={str(k): int(v) for k, v in (doc.get("keywords") or {}).items()},
            categories={str(k): int(v) for k, v in (doc.get("categories") or {}).items()},
            chat_ids=[int(x) for x in (doc.get("chat_ids") or [])],
            by_chat=dict(doc.get("by_chat") or {}),
            first_seen=doc.get("first_seen"),
            last_seen=doc.get("last_seen"),
            risk_score=int(doc.get("risk_score") or 0),
            risk_level=str(doc.get("risk_level") or "Low"),
            risk_factors=[str(x) for x in (doc.get("risk_factors") or [])],
            created_at=doc.get("created_at") or utcnow(),
            updated_at=doc.get("updated_at") or utcnow(),
        )
