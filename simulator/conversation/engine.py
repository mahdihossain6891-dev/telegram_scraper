"""Conversation engine for simulator-generated group discussions."""

from __future__ import annotations

import random
from datetime import datetime
from uuid import UUID, uuid5

from simulator.conversation.context import ConversationContext
from simulator.conversation.formatter import format_message_text
from simulator.keywords import enrich_text_with_keyword, keywords_for_category
from simulator.conversation.replies import ReplyPlanner
from simulator.conversation.templates import (
    ConversationLength,
    DefaultScenarioProvider,
    ScenarioProvider,
    ScenarioSeed,
)
from simulator.conversation.thread import ConversationThread
from simulator.enums import EnvironmentType
from simulator.generation_config import GenerationConfig
from simulator.groups.profiles import Group
from simulator.logger import get_prefixed_logger
from simulator.models import GeneratedMessage, GeneratedMessageType
from simulator.personas.profiles import Persona
from simulator.scheduler.manager import SchedulerManager
from simulator.state.history import ConversationHistory
from simulator.state.memory import ConversationMemory

_log = get_prefixed_logger("conversation", name="engine")

_NS_THREAD = UUID("c1d2e3f4-5555-4666-8777-88889999aaaa")
_NS_MESSAGE = UUID("d2e3f4a5-6666-4777-9888-9999aaaabbbb")


class ConversationEngine:
    """Generates coherent simulator-only conversation threads."""

    def __init__(
        self,
        config: GenerationConfig,
        *,
        scenario_provider: ScenarioProvider | None = None,
        scheduler: SchedulerManager | None = None,
    ) -> None:
        self._config = config
        self._scheduler = scheduler or SchedulerManager(config)
        self._scenario_provider = scenario_provider or DefaultScenarioProvider()
        self._reply_planner = ReplyPlanner(config)
        self._rng = random.Random((config.random_seed or 0) + 60_000)
        self._next_message_id = 1

    def generate_thread(self, personas: list[Persona], group: Group) -> ConversationContext | None:
        candidates = self._scheduler.choose_participants(personas, group)
        if len(candidates) < 2:
            candidates = personas
        if len(candidates) < 2:
            return None

        seed = self._scenario_provider.next_scenario(
            group=group,
            participants=candidates,
            rng=self._rng,
        )
        scenario = seed.conversation
        participants = seed.participants or candidates
        if len(participants) < 2:
            return None

        vocabulary_terms = scenario.vocabulary_terms
        conversation_id = str(uuid5(_NS_THREAD, f"{group.id}:{self._next_message_id}:{scenario.topic}"))
        started_at = self._scheduler.current_time
        thread = ConversationThread(
            id=conversation_id,
            chat_id=str(group.id),
            topic=scenario.topic,
            conversation_type=scenario.conversation_type.value,
            participant_ids=[str(persona.id) for persona in participants],
            started_at=started_at,
            last_activity_at=started_at,
        )
        memory = ConversationMemory(
            conversation_id=conversation_id,
            group_id=str(group.id),
            topic=scenario.topic,
            conversation_type=scenario.conversation_type.value,
            participant_ids=thread.participant_ids,
            started_at=started_at,
            last_activity_at=started_at,
        )
        context = ConversationContext(
            thread=thread,
            memory=memory,
            history=ConversationHistory(),
            group=group,
            participants=participants,
        )
        target_length = self._resolve_target_length(scenario.desired_length)
        self._append_opener(context, participants[0], scenario.opener, vocabulary_terms)

        while self._reply_planner.should_continue(context, target_length):
            responder = self._reply_planner.choose_responder(context, scenario.topic)
            if responder is None:
                break
            self._append_reply(context, responder, scenario.topic, vocabulary_terms)

        if hasattr(self._scenario_provider, "complete_last"):
            reply_count = sum(
                1 for message in context.thread.messages if message.reply_to_message_id is not None
            )
            self._scenario_provider.complete_last(
                message_count=len(context.thread.messages),
                reply_count=reply_count,
                completed_at=context.thread.last_activity_at,
            )

        _log.info("Started Thread %s with %d messages", context.thread.id, len(context.thread.messages))
        return context

    def _append_opener(
        self,
        context: ConversationContext,
        persona: Persona,
        opener: str,
        vocabulary_terms: tuple[str, ...] = (),
    ) -> None:
        timestamp = self._scheduler.advance_for_message(
            persona,
            context.group,
            is_reply=False,
            index=0,
        )
        body = format_message_text(
            persona,
            opener,
            topic=context.thread.topic,
            rng=self._rng,
            length_multiplier=self._config.message_length_multiplier,
            vocabulary_terms=vocabulary_terms,
        )
        body = self._enrich_with_osint_keywords(body, vocabulary_terms)
        message = self._build_message(
            persona=persona,
            group=context.group,
            conversation_id=context.thread.id,
            timestamp=timestamp,
            text=body,
            reply_to_message_id=None,
            participants=context.participants,
            index=0,
        )
        self._record_message(context, message, topic_hint=context.thread.topic)

    def _append_reply(
        self,
        context: ConversationContext,
        persona: Persona,
        topic: str,
        vocabulary_terms: tuple[str, ...] = (),
    ) -> None:
        last_message = context.history.last()
        if last_message is None:
            return
        active_topic = self._evolve_topic(context, persona, topic)
        timestamp = self._scheduler.advance_for_message(
            persona,
            context.group,
            is_reply=True,
            index=len(context.thread.messages),
        )
        base = self._reply_text(persona, active_topic, context)
        body = format_message_text(
            persona,
            base,
            topic=active_topic,
            rng=self._rng,
            length_multiplier=self._config.message_length_multiplier,
            vocabulary_terms=vocabulary_terms,
        )
        body = self._enrich_with_osint_keywords(body, vocabulary_terms)
        message = self._build_message(
            persona=persona,
            group=context.group,
            conversation_id=context.thread.id,
            timestamp=timestamp,
            text=body,
            reply_to_message_id=last_message.message_id,
            participants=context.participants,
            index=len(context.thread.messages),
        )
        self._record_message(context, message, topic_hint=active_topic)

    def _enrich_with_osint_keywords(
        self,
        text: str,
        vocabulary_terms: tuple[str, ...],
    ) -> str:
        pool = list(vocabulary_terms)
        category = self._config.keyword_category
        if category:
            pool.extend(keywords_for_category(category, self._rng))
        unique = tuple(dict.fromkeys(term for term in pool if term))
        return enrich_text_with_keyword(text, unique, self._rng)

    def _record_message(self, context: ConversationContext, message: GeneratedMessage, *, topic_hint: str) -> None:
        context.thread.add_message(message)
        context.history.append(message)
        context.memory.remember(message.message_id, topic_hint, message.sender_id, message.timestamp)

    def _build_message(
        self,
        *,
        persona: Persona,
        group: Group,
        conversation_id: str,
        timestamp: datetime,
        text: str,
        reply_to_message_id: int | None,
        participants: list[Persona],
        index: int,
    ) -> GeneratedMessage:
        message_id = self._next_message_id
        self._next_message_id += 1
        message_type = self._choose_message_type(reply_to_message_id)
        mentioned = []
        if message_type == GeneratedMessageType.MENTION.value and len(participants) > 1:
            other = next(p for p in participants if str(p.id) != str(persona.id))
            mentioned = [str(other.id)]
            text = f"@{other.username} {text}"
        media_metadata = self._media_metadata(message_type, group.category)
        edited = self._rng.random() < self._config.edit_probability
        deleted = self._rng.random() < self._config.delete_probability
        return GeneratedMessage(
            id=uuid5(_NS_MESSAGE, f"{conversation_id}:{message_id}:{persona.id}"),
            message_id=message_id,
            sender_id=str(persona.id),
            chat_id=str(group.id),
            timestamp=timestamp,
            reply_to_message_id=reply_to_message_id,
            message_type=message_type,
            message_text=text,
            media_metadata=media_metadata,
            forward_source=group.name if message_type == GeneratedMessageType.FORWARD.value else None,
            edited=edited,
            deleted=deleted,
            language=persona.language,
            conversation_id=conversation_id,
            environment=EnvironmentType.SIMULATION,
            mentions=mentioned,
            reactions=self._reaction_metadata(),
        )

    def _choose_message_type(self, reply_to_message_id: int | None) -> str:
        if reply_to_message_id is None:
            return GeneratedMessageType.NORMAL.value
        roll = self._rng.random()
        if roll < self._config.media_probability:
            return self._rng.choice(
                [
                    GeneratedMessageType.PHOTO.value,
                    GeneratedMessageType.GIF.value,
                    GeneratedMessageType.DOCUMENT.value,
                    GeneratedMessageType.VOICE_NOTE.value,
                ]
            )
        if roll < self._config.media_probability + self._config.forward_probability:
            return GeneratedMessageType.FORWARD.value
        if roll < self._config.media_probability + self._config.forward_probability + 0.08:
            return GeneratedMessageType.MENTION.value
        return GeneratedMessageType.REPLY.value

    def _media_metadata(self, message_type: str, category: str) -> dict[str, str]:
        if message_type in {
            GeneratedMessageType.PHOTO.value,
            GeneratedMessageType.GIF.value,
            GeneratedMessageType.DOCUMENT.value,
            GeneratedMessageType.VOICE_NOTE.value,
        }:
            return {"placeholder": "true", "category": category, "type": message_type}
        return {}

    def _reaction_metadata(self) -> list[str]:
        if self._rng.random() > self._config.reaction_probability:
            return []
        return [self._rng.choice(["👍", "🔥", "😂", "❤️", "👀"])]

    def _reply_text(self, persona: Persona, topic: str, context: ConversationContext) -> str:
        kind = context.thread.conversation_type
        if kind == "help_request":
            return f"I'd check the basics first for {topic}."
        if kind == "problem_solving":
            return f"One workaround for {topic} is to simplify the setup."
        if kind == "debate":
            return f"I don't fully agree on {topic}, but I get the point."
        if kind == "marketplace_listing":
            return f"Is there more detail available for {topic}?"
        if kind == "news_sharing":
            return f"That update on {topic} changed expectations a bit."
        if kind == "tutorial":
            return f"Nice walkthrough. I'd add one more note on {topic}."
        if persona.bot:
            return f"Automated note: {topic} appears active."
        return f"I've seen something similar with {topic}."

    def _evolve_topic(self, context: ConversationContext, persona: Persona, topic: str) -> str:
        if len(context.thread.messages) < 6:
            return topic
        if self._rng.random() > 0.18:
            return topic
        candidate_pool = [
            item
            for item in persona.favorite_topics + persona.interests + context.group.topic_tags
            if item != topic
        ]
        return self._rng.choice(candidate_pool) if candidate_pool else topic

    def _resolve_target_length(self, length: ConversationLength) -> int:
        baseline = max(2, self._config.average_conversation_length)
        mapping = {
            ConversationLength.SHORT: (2, max(3, baseline // 2)),
            ConversationLength.MEDIUM: (max(4, baseline - 3), baseline + 3),
            ConversationLength.LONG: (baseline + 4, min(self._config.max_thread_messages, baseline * 2)),
            ConversationLength.VERY_LONG: (
                max(baseline * 2, baseline + 8),
                min(self._config.max_thread_messages, baseline * 4),
            ),
        }
        low, high = mapping[length]
        if high < low:
            high = low
        return min(self._config.max_thread_messages, self._rng.randint(low, high))
