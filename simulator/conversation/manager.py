"""Conversation manager for simulator-generated threads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from simulator.conversation.context import (
    ConversationContext,
    ConversationStatistics,
    compute_conversation_statistics,
)
from simulator.conversation.engine import ConversationEngine
from simulator.conversation.templates import ScenarioProvider
from simulator.generation_config import GenerationConfig
from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona


@dataclass(slots=True)
class ConversationBatch:
    """Result of generating one or more conversation threads."""

    contexts: list[ConversationContext]
    statistics: ConversationStatistics


class ConversationManager:
    """Generates and tracks active simulator conversation threads."""

    def __init__(
        self,
        config: GenerationConfig | None = None,
        *,
        scenario_provider: ScenarioProvider | None = None,
        scenario_manager: object | None = None,
    ) -> None:
        self._config = config or GenerationConfig()
        provider = scenario_provider
        if provider is None and scenario_manager is not None:
            provider = scenario_manager.provider
        self._engine = ConversationEngine(
            self._config,
            scenario_provider=provider,
        )
        self._active: dict[str, ConversationContext] = {}
        self._closed: list[ConversationContext] = []

    @property
    def active_conversations(self) -> list[ConversationContext]:
        return list(self._active.values())

    @property
    def closed_conversations(self) -> list[ConversationContext]:
        return list(self._closed)

    def generate_conversation(self, personas: list[Persona], group: Group) -> ConversationContext | None:
        if len(self._active) >= self._config.maximum_concurrent_conversations:
            self.close_inactive_conversations()
        context = self._engine.generate_thread(personas, group)
        if context is None:
            return None
        self._active[context.thread.id] = context
        return context

    def generate_conversations(self, personas: list[Persona], groups: list[Group]) -> ConversationBatch:
        contexts: list[ConversationContext] = []
        for group in groups[: self._config.maximum_concurrent_conversations]:
            context = self.generate_conversation(personas, group)
            if context is not None:
                contexts.append(context)
        self.close_inactive_conversations(force=True)
        stats = compute_conversation_statistics([ctx.thread for ctx in self._closed])
        return ConversationBatch(contexts=contexts, statistics=stats)

    def close_inactive_conversations(
        self,
        *,
        force: bool = False,
        inactivity_threshold: timedelta = timedelta(minutes=20),
    ) -> None:
        now = max(
            (ctx.thread.last_activity_at for ctx in self._active.values()),
            default=datetime(2026, 1, 1, 0, 0, 0),
        )
        to_close = []
        for thread_id, context in self._active.items():
            inactive = force or (now - context.thread.last_activity_at) >= inactivity_threshold
            if inactive:
                context.thread.close()
                context.memory.close(context.thread.last_activity_at)
                to_close.append(thread_id)
        for thread_id in to_close:
            self._closed.append(self._active.pop(thread_id))

    def get_statistics(self) -> ConversationStatistics:
        threads = [ctx.thread for ctx in self._closed] + [ctx.thread for ctx in self._active.values()]
        return compute_conversation_statistics(threads)
