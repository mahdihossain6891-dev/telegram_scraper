"""ScenarioProvider adapter — bridges Scenario Engine to Conversation Engine."""

from __future__ import annotations

import random
from datetime import datetime

from simulator.conversation.templates import ConversationScenario, ScenarioSeed
from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona
from simulator.scenario.engine import ScenarioEngine


class ScenarioEngineProvider:
    """Implements the conversation-layer ScenarioProvider protocol."""

    def __init__(self, engine: ScenarioEngine) -> None:
        self._engine = engine
        self._last_context = None

    @property
    def last_context(self):
        return self._last_context

    def next_scenario(
        self,
        *,
        group: Group,
        participants: list[Persona],
        rng: random.Random,
        when: datetime | None = None,
    ) -> ScenarioSeed:
        context = self._engine.build_context(
            group=group,
            candidates=participants,
            when=when,
        )
        self._last_context = context
        gt_keywords: tuple[str, ...] = ()
        if context.ground_truth and context.ground_truth.expected_keywords:
            gt_keywords = tuple(context.ground_truth.expected_keywords)
        conversation = ConversationScenario(
            topic=context.topic,
            conversation_type=context.conversation_type,
            opener=context.opener,
            keywords=context.keywords,
            desired_length=context.desired_length,
            scenario_id=context.scenario.scenario_id,
            vocabulary_terms=context.vocabulary.common_terms
            + context.vocabulary.topic_keywords
            + gt_keywords,
            conversation_style=context.scenario.conversation_style,
            behavior_pattern=context.scenario.behavior_pattern,
        )
        return ScenarioSeed(
            conversation=conversation,
            participants=context.participants,
            scenario_id=context.scenario.scenario_id,
        )

    def complete_last(self, *, message_count: int, reply_count: int, completed_at: datetime) -> None:
        if self._last_context is not None:
            self._engine.complete_context(
                self._last_context,
                message_count=message_count,
                reply_count=reply_count,
                completed_at=completed_at,
            )
