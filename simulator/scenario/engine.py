"""Scenario engine — produces structured context for the Conversation Engine."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from simulator.conversation.templates import ConversationLength, ConversationType
from simulator.groups.profiles import Group
from simulator.logger import get_prefixed_logger
from simulator.personas.profiles import Persona
from simulator.scenario.config import ScenarioConfig
from simulator.scenario.labels import EvolutionPhase, ScenarioEventType
from simulator.scenario.registry import ScenarioRegistry
from simulator.scenario.selector import scenario_matches_group, select_participants
from simulator.scenario.statistics import ScenarioHistory, ScenarioRunRecord
from simulator.scenario.templates import GroundTruth, ScenarioDefinition, VocabularyProfile
from simulator.scenario.validator import validate_participants, validate_scenario_for_group
from simulator.scenario.weighting import normalize_weights

_log = get_prefixed_logger("scenario", name="engine")

_EVOLUTION_FLOW: dict[EvolutionPhase, tuple[ConversationType, ...]] = {
    EvolutionPhase.MORNING: (ConversationType.CASUAL_CHAT, ConversationType.ANNOUNCEMENT),
    EvolutionPhase.AFTERNOON: (ConversationType.PROBLEM_SOLVING, ConversationType.HELP_REQUEST),
    EvolutionPhase.EVENING: (ConversationType.DISCUSSION, ConversationType.DEBATE),
    EvolutionPhase.NIGHT: (ConversationType.CASUAL_CHAT, ConversationType.DISCUSSION),
}


@dataclass(slots=True)
class ScenarioEvent:
    """Injected scenario event metadata (not a message)."""

    event_type: ScenarioEventType
    description: str
    at_phase: EvolutionPhase


@dataclass(slots=True)
class ScenarioContext:
    """Structured scenario output consumed by the Conversation Engine."""

    scenario: ScenarioDefinition
    topic: str
    conversation_type: ConversationType
    opener: str
    keywords: tuple[str, ...]
    desired_length: ConversationLength
    participants: list[Persona]
    vocabulary: VocabularyProfile
    evolution_phase: EvolutionPhase
    events: list[ScenarioEvent] = field(default_factory=list)
    ground_truth: GroundTruth | None = None
    run_record: ScenarioRunRecord | None = None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario.scenario_id,
            "scenario_name": self.scenario.name,
            "category": self.scenario.category.value,
            "topic": self.topic,
            "conversation_type": self.conversation_type.value,
            "evolution_phase": self.evolution_phase.value,
            "participant_count": len(self.participants),
            "events": [event.event_type.value for event in self.events],
        }


class ScenarioEngine:
    """Selects scenarios and builds conversation context — never generates messages."""

    def __init__(
        self,
        registry: ScenarioRegistry,
        config: ScenarioConfig | None = None,
        *,
        history: ScenarioHistory | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or ScenarioConfig()
        self._history = history or ScenarioHistory()
        self._rng = random.Random((self._config.random_seed or 0) + 70_000)

    @property
    def history(self) -> ScenarioHistory:
        return self._history

    def build_context(
        self,
        *,
        group: Group,
        candidates: list[Persona],
        when: datetime | None = None,
    ) -> ScenarioContext:
        moment = when or datetime(2026, 1, 1, 10, 0, 0)
        scenario = self._select_scenario(group)
        validate_scenario_for_group(scenario, group)
        participants = select_participants(scenario, group, candidates, self._rng)
        validate_participants(scenario, participants, config=self._config)

        phase = self._evolution_phase(moment)
        topic = self._choose_topic(scenario, group)
        conversation_type = self._choose_conversation_type(scenario, phase)
        opener = self._build_opener(scenario, topic, conversation_type)
        events = self._inject_events(scenario, phase)
        length = self._vary_length(scenario.expected_conversation_length)

        synthetic = bool(
            scenario.ground_truth and scenario.ground_truth.synthetic_evaluation
        )
        log_name = scenario.name
        if synthetic:
            _log.info("Started Synthetic Threat Evaluation: %s", log_name)
        else:
            _log.info("Started %s Scenario", log_name)

        run_record = self._history.start_run(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            category=scenario.category.value,
            participant_ids=[str(persona.id) for persona in participants],
            started_at=moment,
            synthetic_evaluation=synthetic,
        )

        return ScenarioContext(
            scenario=scenario,
            topic=topic,
            conversation_type=conversation_type,
            opener=opener,
            keywords=tuple(sorted(set(scenario.vocabulary.topic_keywords + (topic,)))),
            desired_length=length,
            participants=participants,
            vocabulary=scenario.vocabulary,
            evolution_phase=phase,
            events=events,
            ground_truth=scenario.ground_truth,
            run_record=run_record,
        )

    def complete_context(
        self,
        context: ScenarioContext,
        *,
        message_count: int,
        reply_count: int,
        completed_at: datetime,
    ) -> None:
        if context.run_record is None:
            return
        self._history.complete_run(
            context.run_record,
            message_count=message_count,
            reply_count=reply_count,
            completed_at=completed_at,
            success=message_count >= 2,
        )
        _log.info("Completed scenario %s", context.scenario.scenario_id)

    def _select_scenario(self, group: Group) -> ScenarioDefinition:
        compatible = [
            scenario
            for scenario in self._registry.enabled()
            if scenario_matches_group(scenario, group)
        ]
        if not compatible:
            compatible = list(self._registry.enabled())
        weights: dict[str, float] = {}
        configured = self._config.scenario_weights or {}
        for scenario in compatible:
            weights[scenario.scenario_id] = configured.get(
                scenario.scenario_id,
                self._registry.weight_for(scenario.scenario_id),
            )
        normalized = normalize_weights(weights)
        scenario_ids = list(normalized.keys())
        values = [normalized[sid] for sid in scenario_ids]
        chosen_id = self._rng.choices(scenario_ids, weights=values, k=1)[0]
        return self._registry.get(chosen_id)

    def _evolution_phase(self, when: datetime) -> EvolutionPhase:
        hour = when.hour
        if 5 <= hour < 12:
            return EvolutionPhase.MORNING
        if 12 <= hour < 17:
            return EvolutionPhase.AFTERNOON
        if 17 <= hour < 22:
            return EvolutionPhase.EVENING
        return EvolutionPhase.NIGHT

    def _choose_topic(self, scenario: ScenarioDefinition, group: Group) -> str:
        pool = list(scenario.typical_topics) + list(group.topic_tags)
        return self._rng.choice(pool or [scenario.name])

    def _choose_conversation_type(
        self, scenario: ScenarioDefinition, phase: EvolutionPhase
    ) -> ConversationType:
        phase_types = _EVOLUTION_FLOW.get(phase, scenario.conversation_types)
        compatible = [ctype for ctype in scenario.conversation_types if ctype in phase_types]
        return self._rng.choice(compatible or list(scenario.conversation_types))

    def _build_opener(
        self,
        scenario: ScenarioDefinition,
        topic: str,
        conversation_type: ConversationType,
    ) -> str:
        if scenario.opener_templates:
            base = self._rng.choice(scenario.opener_templates)
        else:
            base = f"Let's talk about {topic}."
        term = self._rng.choice(scenario.vocabulary.common_terms) if scenario.vocabulary.common_terms else topic
        if conversation_type == ConversationType.QUESTION:
            return base if "?" in base else f"Anyone here working with {topic}?"
        if conversation_type == ConversationType.MARKETPLACE_LISTING:
            return f"{base} ({term})"
        return base.replace("{topic}", topic) if "{topic}" in base else base

    def _inject_events(self, scenario: ScenarioDefinition, phase: EvolutionPhase) -> list[ScenarioEvent]:
        events: list[ScenarioEvent] = []
        if self._rng.random() < 0.15:
            events.append(
                ScenarioEvent(
                    event_type=ScenarioEventType.NEW_MEMBER,
                    description="A new member joined the group.",
                    at_phase=phase,
                )
            )
        if scenario.category.value == "marketplace" and self._rng.random() < 0.25:
            events.append(
                ScenarioEvent(
                    event_type=ScenarioEventType.MARKETPLACE_LISTING,
                    description="A new listing was posted.",
                    at_phase=phase,
                )
            )
        if scenario.category.value == "news" and phase == EvolutionPhase.MORNING:
            events.append(
                ScenarioEvent(
                    event_type=ScenarioEventType.BREAKING_NEWS,
                    description="Breaking headline shared in channel.",
                    at_phase=phase,
                )
            )
        if self._rng.random() < 0.1:
            events.append(
                ScenarioEvent(
                    event_type=ScenarioEventType.TOPIC_CHANGE,
                    description="Conversation topic shifted naturally.",
                    at_phase=phase,
                )
            )
        return events

    def _vary_length(self, base: ConversationLength) -> ConversationLength:
        if self._rng.random() < 0.7:
            return base
        return self._rng.choice(list(ConversationLength))
