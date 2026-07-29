"""Conversation context and statistics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from simulator.conversation.thread import ConversationThread
from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona
from simulator.state.history import ConversationHistory
from simulator.state.memory import ConversationMemory


@dataclass(slots=True)
class ConversationContext:
    """All state required to generate one thread."""

    thread: ConversationThread
    memory: ConversationMemory
    history: ConversationHistory
    group: Group
    participants: list[Persona]


@dataclass(frozen=True, slots=True)
class ConversationStatistics:
    """Aggregated metrics for generated conversations."""

    messages_created: int
    replies: int
    threads: int
    conversation_count: int
    average_length: float
    average_response_time: float
    most_active_user: str | None
    most_active_group: str | None
    average_users_per_conversation: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages_created": self.messages_created,
            "replies": self.replies,
            "threads": self.threads,
            "conversation_count": self.conversation_count,
            "average_length": self.average_length,
            "average_response_time": self.average_response_time,
            "most_active_user": self.most_active_user,
            "most_active_group": self.most_active_group,
            "average_users_per_conversation": self.average_users_per_conversation,
        }


def compute_conversation_statistics(threads: list[ConversationThread]) -> ConversationStatistics:
    """Build aggregate stats from completed conversation threads."""
    if not threads:
        return ConversationStatistics(0, 0, 0, 0, 0.0, 0.0, None, None, 0.0)

    user_counts: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    total_messages = 0
    total_replies = 0
    total_response_time = 0.0
    total_participants = 0

    for thread in threads:
        total_messages += len(thread.messages)
        total_participants += len(thread.participant_ids)
        group_counts[thread.chat_id] += len(thread.messages)
        previous = None
        for message in thread.messages:
            user_counts[message.sender_id] += 1
            if message.reply_to_message_id is not None:
                total_replies += 1
            if previous is not None:
                total_response_time += (message.timestamp - previous.timestamp).total_seconds()
            previous = message

    response_events = max(total_messages - len(threads), 1)
    return ConversationStatistics(
        messages_created=total_messages,
        replies=total_replies,
        threads=len(threads),
        conversation_count=len(threads),
        average_length=round(total_messages / len(threads), 2),
        average_response_time=round(total_response_time / response_events, 2),
        most_active_user=user_counts.most_common(1)[0][0] if user_counts else None,
        most_active_group=group_counts.most_common(1)[0][0] if group_counts else None,
        average_users_per_conversation=round(total_participants / len(threads), 2),
    )
