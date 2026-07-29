"""Message and context models for the traffic simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from simulator.enums import EnvironmentType, SimulationSpeed, SimulationState


@dataclass(frozen=True, slots=True)
class MessageEvent:
    """One Telegram-like event emitted by any ``MessageSource``.

    Downstream intelligence modules consume this shape only — never raw Telethon
    objects or simulator internals.
    """

    message_id: int
    chat_id: int
    sender_id: int
    timestamp: datetime
    text: str = ""
    reply_to_message_id: int | None = None
    media_metadata: dict[str, Any] = field(default_factory=dict)
    is_forward: bool = False
    is_edited: bool = False
    is_deleted: bool = False
    language: str | None = None
    environment: EnvironmentType = EnvironmentType.LIVE
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp.isoformat(),
            "text": self.text,
            "reply_to_message_id": self.reply_to_message_id,
            "media_metadata": dict(self.media_metadata),
            "is_forward": self.is_forward,
            "is_edited": self.is_edited,
            "is_deleted": self.is_deleted,
            "language": self.language,
            "environment": self.environment.value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class SimulationConfiguration:
    """Serializable simulator configuration snapshot."""

    enabled: bool
    environment: EnvironmentType
    speed: SimulationSpeed
    user_count: int
    group_count: int
    database_name: str
    export_path: str
    live_database_name: str = ""
    random_seed: int | None = None
    strict_isolation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "environment": self.environment.value,
            "speed": self.speed.value,
            "user_count": self.user_count,
            "group_count": self.group_count,
            "database_name": self.database_name,
            "live_database_name": self.live_database_name,
            "export_path": self.export_path,
            "random_seed": self.random_seed,
            "strict_isolation": self.strict_isolation,
        }


@dataclass(frozen=True, slots=True)
class SimulationStatus:
    """Current simulator lifecycle and configuration metadata."""

    state: SimulationState
    enabled: bool
    configuration: SimulationConfiguration
    active_environment: EnvironmentType
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "enabled": self.enabled,
            "active_environment": self.active_environment.value,
            "configuration": self.configuration.to_dict(),
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class EnvironmentInformation:
    """Describes an active or selectable runtime environment."""

    environment: EnvironmentType
    active: bool
    selectable: bool
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment.value,
            "active": self.active,
            "selectable": self.selectable,
            "description": self.description,
            "metadata": dict(self.metadata),
        }
