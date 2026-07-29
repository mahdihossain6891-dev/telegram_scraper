"""Tests for the conversation engine and manager."""

from __future__ import annotations

import random

from simulator.conversation.manager import ConversationManager
from simulator.conversation.templates import (
    ConversationLength,
    ConversationScenario,
    ConversationType,
    DefaultScenarioProvider,
    ScenarioSeed,
)
from simulator.generation_config import GenerationConfig
from simulator.world_generator import WorldGenerator


class FixedScenarioProvider(DefaultScenarioProvider):
    def next_scenario(self, *, group, participants, rng: random.Random) -> ConversationScenario:
        return ScenarioSeed(
            conversation=ConversationScenario(
                topic="docker",
                conversation_type=ConversationType.QUESTION,
                opener="Anyone using Docker Desktop lately?",
                keywords=("docker", "containers"),
                desired_length=ConversationLength.MEDIUM,
            ),
            scenario_id="programming",
        )


def _first_context(manager: ConversationManager, personas, groups):
    for group in groups:
        context = manager.generate_conversation(personas, group)
        if context is not None:
            return context
    return None


class TestConversationManager:
    def test_conversation_continuity_and_reply_chain(self) -> None:
        cfg = GenerationConfig(
            user_count=60,
            group_count=6,
            random_seed=9,
            average_conversation_length=10,
            max_thread_messages=20,
        )
        world = WorldGenerator(cfg).generate()
        manager = ConversationManager(cfg, scenario_provider=FixedScenarioProvider())
        context = _first_context(manager, world.personas, world.groups)
        assert context is not None
        assert len(context.thread.messages) >= 2
        assert all(message.conversation_id == context.thread.id for message in context.thread.messages)
        assert any(message.reply_to_message_id is not None for message in context.thread.messages[1:])
        assert "docker" in " ".join(message.message_text.lower() for message in context.thread.messages)
        assert context.memory.topic == context.thread.topic

    def test_active_and_closed_conversation_tracking(self) -> None:
        cfg = GenerationConfig(user_count=50, group_count=5, random_seed=15)
        world = WorldGenerator(cfg).generate()
        manager = ConversationManager(cfg)
        context = _first_context(manager, world.personas, world.groups)
        assert context is not None
        assert len(manager.active_conversations) == 1
        assert context.memory.open is True
        manager.close_inactive_conversations(force=True)
        assert len(manager.active_conversations) == 0
        assert len(manager.closed_conversations) == 1
        assert context.memory.open is False

    def test_seed_consistency(self) -> None:
        cfg = GenerationConfig(user_count=70, group_count=7, random_seed=101, max_thread_messages=18)
        world_a = WorldGenerator(cfg).generate()
        world_b = WorldGenerator(cfg).generate()
        manager_a = ConversationManager(cfg)
        manager_b = ConversationManager(cfg)
        context_a = _first_context(manager_a, world_a.personas, world_a.groups)
        context_b = _first_context(manager_b, world_b.personas, world_b.groups)
        assert context_a is not None and context_b is not None
        assert [message.to_dict() for message in context_a.thread.messages] == [
            message.to_dict() for message in context_b.thread.messages
        ]

    def test_statistics_generation(self) -> None:
        cfg = GenerationConfig(user_count=80, group_count=8, random_seed=19)
        world = WorldGenerator(cfg).generate()
        manager = ConversationManager(cfg)
        batch = manager.generate_conversations(world.personas, world.groups[:3])
        assert batch.statistics.messages_created > 0
        assert batch.statistics.conversation_count > 0
        assert batch.statistics.average_users_per_conversation >= 2

    def test_custom_scenario_provider_is_injectable(self) -> None:
        cfg = GenerationConfig(user_count=40, group_count=4, random_seed=55)
        world = WorldGenerator(cfg).generate()
        manager = ConversationManager(cfg, scenario_provider=FixedScenarioProvider())
        context = _first_context(manager, world.personas, world.groups)
        assert context is not None
        assert context.thread.topic == "docker"
        assert "docker" in context.thread.messages[0].message_text.lower()
