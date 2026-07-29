"""In-memory conversation state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ConversationMemory:
    """Temporary memory for one active conversation."""

    conversation_id: str
    group_id: str
    topic: str
    conversation_type: str
    participant_ids: list[str]
    started_at: datetime
    last_activity_at: datetime
    last_speaker_id: str | None = None
    recent_message_ids: list[int] = field(default_factory=list)
    recent_topics: list[str] = field(default_factory=list)
    open: bool = True

    def remember(self, message_id: int, topic_hint: str, speaker_id: str, at: datetime) -> None:
        self.last_speaker_id = speaker_id
        self.last_activity_at = at
        self.recent_message_ids.append(message_id)
        self.recent_message_ids = self.recent_message_ids[-12:]
        if topic_hint:
            self.recent_topics.append(topic_hint)
            self.recent_topics = self.recent_topics[-8:]

    def close(self, at: datetime) -> None:
        self.open = False
        self.last_activity_at = at
