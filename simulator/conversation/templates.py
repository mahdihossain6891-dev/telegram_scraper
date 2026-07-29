"""Conversation templates and scenario provider abstractions."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona


class ConversationLength(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    VERY_LONG = "very_long"


class ConversationType(str, Enum):
    QUESTION = "question"
    DISCUSSION = "discussion"
    DEBATE = "debate"
    ANNOUNCEMENT = "announcement"
    MARKETPLACE_LISTING = "marketplace_listing"
    NEWS_SHARING = "news_sharing"
    TUTORIAL = "tutorial"
    HELP_REQUEST = "help_request"
    PROBLEM_SOLVING = "problem_solving"
    CASUAL_CHAT = "casual_chat"


@dataclass(frozen=True, slots=True)
class ConversationScenario:
    """One conversation seed returned by a scenario provider."""

    topic: str
    conversation_type: ConversationType
    opener: str
    keywords: tuple[str, ...]
    desired_length: ConversationLength
    scenario_id: str = ""
    vocabulary_terms: tuple[str, ...] = ()
    conversation_style: str = ""
    behavior_pattern: str = ""


@dataclass(frozen=True, slots=True)
class ScenarioSeed:
    """Rich scenario output for the Conversation Engine."""

    conversation: ConversationScenario
    participants: list[Persona] | None = None
    scenario_id: str = ""


class ScenarioProvider(Protocol):
    """Supplies topic seeds without coupling the engine to scenario details."""

    def next_scenario(
        self,
        *,
        group: Group,
        participants: list[Persona],
        rng: random.Random,
    ) -> ScenarioSeed: ...


class DefaultScenarioProvider:
    """Legacy scenario provider based on group categories and persona interests."""

    _TYPE_BY_GROUP: dict[str, tuple[ConversationType, ...]] = {
        "programming": (
            ConversationType.QUESTION,
            ConversationType.HELP_REQUEST,
            ConversationType.PROBLEM_SOLVING,
            ConversationType.TUTORIAL,
        ),
        "cybersecurity": (
            ConversationType.DISCUSSION,
            ConversationType.DEBATE,
            ConversationType.NEWS_SHARING,
        ),
        "marketplace": (
            ConversationType.MARKETPLACE_LISTING,
            ConversationType.ANNOUNCEMENT,
            ConversationType.CASUAL_CHAT,
        ),
        "news": (ConversationType.NEWS_SHARING, ConversationType.DISCUSSION),
        "gaming": (ConversationType.CASUAL_CHAT, ConversationType.DISCUSSION, ConversationType.DEBATE),
    }

    def next_scenario(
        self,
        *,
        group: Group,
        participants: list[Persona],
        rng: random.Random,
    ) -> ScenarioSeed:
        topic_pool = list(group.topic_tags)
        for persona in participants[:4]:
            topic_pool.extend(persona.favorite_topics[:2])
            topic_pool.extend(persona.interests[:2])
        topic = rng.choice(topic_pool or [group.category])
        conversation_type = rng.choice(
            self._TYPE_BY_GROUP.get(
                group.category,
                (
                    ConversationType.QUESTION,
                    ConversationType.DISCUSSION,
                    ConversationType.CASUAL_CHAT,
                ),
            )
        )
        opener_map = {
            ConversationType.QUESTION: f"Anyone here working with {topic} lately?",
            ConversationType.HELP_REQUEST: f"Need some help with {topic}. Any tips?",
            ConversationType.PROBLEM_SOLVING: f"I hit an issue around {topic}. Curious how others handle it.",
            ConversationType.DEBATE: f"Hot take: {topic} is getting overrated. Agree or disagree?",
            ConversationType.ANNOUNCEMENT: f"Quick update for the group about {topic}.",
            ConversationType.MARKETPLACE_LISTING: f"Listing update: {topic} available today.",
            ConversationType.NEWS_SHARING: f"Saw an interesting update about {topic} this morning.",
            ConversationType.TUTORIAL: f"Sharing a small walkthrough on {topic}.",
            ConversationType.CASUAL_CHAT: f"Random thought about {topic} today.",
            ConversationType.DISCUSSION: f"What are people here doing around {topic} right now?",
        }
        length = rng.choices(
            population=[
                ConversationLength.SHORT,
                ConversationLength.MEDIUM,
                ConversationLength.LONG,
                ConversationLength.VERY_LONG,
            ],
            weights=[0.25, 0.45, 0.22, 0.08],
            k=1,
        )[0]
        conversation = ConversationScenario(
            topic=topic,
            conversation_type=conversation_type,
            opener=opener_map[conversation_type],
            keywords=tuple(sorted(set(topic_pool[:6]))),
            desired_length=length,
        )
        return ScenarioSeed(conversation=conversation)
