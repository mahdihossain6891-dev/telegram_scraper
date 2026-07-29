"""Tests for the Scenario Engine."""

from __future__ import annotations

import random
from collections import Counter

import pytest

from simulator.exceptions import SimulationError
from simulator.generation_config import GenerationConfig
from simulator.scenario.config import ScenarioConfig
from simulator.scenario.labels import ScenarioCategory
from simulator.scenario.manager import ScenarioManager
from simulator.scenario.registry import ScenarioRegistry
from simulator.scenario.selector import score_persona_for_scenario, select_participants
from simulator.scenario.validator import validate_registry
from simulator.scenario.weighting import normalize_weights, weighted_choice
from simulator.world_generator import WorldGenerator


class TestScenarioEngine:
    def test_builtin_registry_loads(self) -> None:
        registry = ScenarioRegistry.with_builtins()
        scenarios = registry.all()
        assert len(scenarios) >= 8
        assert any(s.category == ScenarioCategory.SYNTHETIC_THREAT_EVALUATION for s in scenarios)

    def test_weight_normalization(self) -> None:
        weights = normalize_weights({"a": 25, "b": 75})
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_weighted_selection_is_deterministic(self) -> None:
        registry = ScenarioRegistry.with_builtins()
        rng_a = random.Random(99)
        rng_b = random.Random(99)
        first = weighted_choice(registry, rng_a).scenario_id
        second = weighted_choice(registry, rng_b).scenario_id
        assert first == second

    def test_weight_distribution_skews_toward_heavier_scenarios(self) -> None:
        registry = ScenarioRegistry.with_builtins()
        for sid in registry.all():
            registry.disable(sid.scenario_id)
        registry.enable("technology")
        registry.enable("programming")
        rng = random.Random(7)
        picks = Counter(
            weighted_choice(
                registry,
                rng,
                configured_weights={"technology": 0.9, "programming": 0.1},
            ).scenario_id
            for _ in range(200)
        )
        assert picks["technology"] > picks["programming"]

    def test_participant_selection_prefers_matching_personalities(self) -> None:
        world = WorldGenerator(GenerationConfig(user_count=80, group_count=8, random_seed=3)).generate()
        manager = ScenarioManager()
        programming = manager.registry.get("programming")
        group = next(g for g in world.groups if g.category == "programming")
        candidates = [p for p in world.personas if str(p.id) in group.member_ids]
        selected = select_participants(programming, group, candidates, random.Random(5))
        assert len(selected) >= 2
        scores = [score_persona_for_scenario(persona, programming, group) for persona in selected]
        assert max(scores) >= 1.0

    def test_ground_truth_exists_for_synthetic_scenarios(self) -> None:
        manager = ScenarioManager()
        truth = manager.get_ground_truth("synthetic_financial_fraud")
        assert truth is not None
        assert truth["synthetic_evaluation"] is True
        assert truth["expected_alert"] is True
        assert len(truth["expected_keywords"]) > 0

    def test_scenario_context_metadata_only(self) -> None:
        world = WorldGenerator(GenerationConfig(user_count=60, group_count=6, random_seed=11)).generate()
        manager = ScenarioManager(ScenarioConfig(random_seed=11))
        group = next(g for g in world.groups if g.category == "programming")
        candidates = [p for p in world.personas if str(p.id) in group.member_ids]
        context = manager.build_context(group=group, candidates=candidates)
        metadata = context.to_metadata()
        assert metadata["scenario_id"]
        assert metadata["participant_count"] >= 2
        assert context.ground_truth is None or context.ground_truth.synthetic_evaluation is not None

    def test_scenario_statistics_track_runs(self) -> None:
        world = WorldGenerator(GenerationConfig(user_count=100, group_count=10, random_seed=21)).generate()
        manager = ScenarioManager(ScenarioConfig(random_seed=21))
        runs = 0
        for group in [g for g in world.groups if g.category == "programming"][:3]:
            candidates = [p for p in world.personas if str(p.id) in group.member_ids]
            if len(candidates) < 3:
                continue
            try:
                context = manager.build_context(group=group, candidates=candidates)
            except SimulationError:
                continue
            assert context.run_record is not None
            manager._engine.complete_context(
                context,
                message_count=8,
                reply_count=5,
                completed_at=context.run_record.started_at,
            )
            runs += 1
            if runs >= 2:
                break
        stats = manager.get_statistics()
        assert stats.total_runs >= 1

    def test_scenario_manager_validates_registry(self) -> None:
        registry = ScenarioRegistry.with_builtins()
        for scenario in registry.all():
            registry.disable(scenario.scenario_id)
        with pytest.raises(SimulationError):
            validate_registry(registry, ScenarioConfig())

    def test_scenario_manager_integrates_with_conversation_manager(self) -> None:
        from simulator.conversation.manager import ConversationManager

        cfg = GenerationConfig(user_count=50, group_count=5, random_seed=33)
        world = WorldGenerator(cfg).generate()
        scenario_manager = ScenarioManager(ScenarioConfig(random_seed=33))
        conversation_manager = ConversationManager(cfg, scenario_manager=scenario_manager)
        context = None
        for group in world.groups:
            context = conversation_manager.generate_conversation(world.personas, group)
            if context is not None:
                break
        assert context is not None
        assert len(context.thread.messages) >= 2
        assert scenario_manager.get_statistics().total_runs >= 1
