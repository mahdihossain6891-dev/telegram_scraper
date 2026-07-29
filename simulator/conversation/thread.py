"""Conversation thread models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from simulator.models import GeneratedMessage


@dataclass(slots=True)
class ConversationThread:
    """One active or completed simulated conversation."""

    id: str
    chat_id: str
    topic: str
    conversation_type: str
    participant_ids: list[str]
    started_at: datetime
    last_activity_at: datetime
    status: str = "active"
    messages: list[GeneratedMessage] = field(default_factory=list)

    def add_message(self, message: GeneratedMessage) -> None:
        self.messages.append(message)
        self.last_activity_at = message.timestamp

    def close(self) -> None:
        self.status = "closed"
