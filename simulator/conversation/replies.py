"""Reply planning and participant selection."""

from __future__ import annotations

import random

from simulator.conversation.context import ConversationContext
from simulator.generation_config import GenerationConfig
from simulator.logger import get_prefixed_logger
from simulator.personas.profiles import Persona

_log = get_prefixed_logger("reply", name="planner")


class ReplyPlanner:
    """Chooses who replies and whether a thread continues."""

    def __init__(self, config: GenerationConfig, seed: int | None = None) -> None:
        self._config = config
        self._rng = random.Random((seed or config.random_seed or 0) + 50_000)

    def should_continue(self, context: ConversationContext, target_length: int) -> bool:
        if len(context.thread.messages) >= target_length:
            return False
        if len(context.thread.messages) >= self._config.max_thread_messages:
            return False
        average_reply_bias = min(0.2, self._config.average_replies * 0.15)
        probability = max(
            0.18,
            self._config.reply_probability + average_reply_bias - (len(context.thread.messages) * 0.015),
        )
        return self._rng.random() <= probability or len(context.thread.messages) < 3

    def choose_responder(self, context: ConversationContext, topic: str) -> Persona | None:
        candidates = [p for p in context.participants if str(p.id) != context.memory.last_speaker_id]
        if not candidates:
            return None
        weighted: list[tuple[Persona, float]] = []
        for persona in candidates:
            score = 1.0
            if topic in persona.interests or topic in persona.favorite_topics:
                score += 1.5
            if context.group.category in persona.interests:
                score += 0.8
            if str(context.group.id) in persona.group_memberships:
                score += 0.4
            score += min(persona.average_replies, 1.0)
            weighted.append((persona, score))
        population = [persona for persona, _ in weighted]
        weights = [score for _, score in weighted]
        responder = self._rng.choices(population, weights=weights, k=1)[0]
        _log.info("Generated Reply candidate %s for topic %s", responder.username, topic)
        return responder
