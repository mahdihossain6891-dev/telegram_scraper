"""Convert simulator-generated messages to MessageEvent."""

from __future__ import annotations

from simulator.enums import EnvironmentType
from simulator.groups.profiles import Group
from simulator.models import GeneratedMessage, MessageEvent
from simulator.personas.profiles import Persona


class MessageEventConverter:
    """Maps GeneratedMessage UUID references to Telegram-like IDs."""

    def __init__(self, personas: list[Persona], groups: list[Group]) -> None:
        self._personas = {str(persona.id): persona for persona in personas}
        self._groups = {str(group.id): group for group in groups}

    def convert(self, message: GeneratedMessage) -> MessageEvent:
        persona = self._personas.get(message.sender_id)
        group = self._groups.get(message.chat_id)
        sender_id = persona.telegram_id if persona else abs(hash(message.sender_id)) % 10_000_000_000
        chat_id = group.telegram_chat_id if group else -abs(hash(message.chat_id)) % 1_000_000_000_000
        return MessageEvent(
            message_id=message.message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            timestamp=message.timestamp,
            text=message.message_text,
            reply_to_message_id=message.reply_to_message_id,
            media_metadata=dict(message.media_metadata),
            is_forward=message.forward_source is not None,
            is_edited=message.edited,
            is_deleted=message.deleted,
            language=message.language,
            environment=message.environment,
            metadata={
                "conversation_id": message.conversation_id,
                "message_type": message.message_type,
                "mentions": list(message.mentions),
                "persona_id": message.sender_id,
                "group_id": message.chat_id,
            },
        )


def generated_message_to_event(message: GeneratedMessage) -> MessageEvent:
    """Bridge without lookup — uses hash fallback for IDs."""
    return MessageEvent(
        message_id=message.message_id,
        chat_id=-abs(hash(message.chat_id)) % 1_000_000_000_000,
        sender_id=abs(hash(message.sender_id)) % 10_000_000_000,
        timestamp=message.timestamp,
        text=message.message_text,
        reply_to_message_id=message.reply_to_message_id,
        media_metadata=dict(message.media_metadata),
        is_forward=message.forward_source is not None,
        is_edited=message.edited,
        is_deleted=message.deleted,
        language=message.language,
        environment=message.environment or EnvironmentType.SIMULATION,
        metadata={
            "conversation_id": message.conversation_id,
            "message_type": message.message_type,
        },
    )
