"""Thread-local message history."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from simulator.models import GeneratedMessage


@dataclass(slots=True)
class ConversationHistory:
    """Ordered message history for a generated conversation."""

    messages: list[GeneratedMessage] = field(default_factory=list)

    def append(self, message: GeneratedMessage) -> None:
        self.messages.append(message)

    def last(self) -> GeneratedMessage | None:
        return self.messages[-1] if self.messages else None

    def reply_count(self) -> int:
        return sum(1 for message in self.messages if message.reply_to_message_id is not None)

    def average_response_seconds(self) -> float:
        if len(self.messages) < 2:
            return 0.0
        deltas = []
        previous = self.messages[0]
        for current in self.messages[1:]:
            deltas.append((current.timestamp - previous.timestamp).total_seconds())
            previous = current
        return round(mean(deltas), 2) if deltas else 0.0
