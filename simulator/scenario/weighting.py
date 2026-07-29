"""Scenario weight normalization and selection."""

from __future__ import annotations

import random

from simulator.scenario.labels import ScenarioCategory
from simulator.scenario.registry import ScenarioRegistry
from simulator.scenario.templates import ScenarioDefinition


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in weights.values())
    if total <= 0:
        raise ValueError("Scenario weights must sum to a positive value.")
    return {key: max(0.0, value) / total for key, value in weights.items()}


def build_weight_map(
    registry: ScenarioRegistry,
    *,
    configured_weights: dict[str, float] | None = None,
    include_synthetic: bool = True,
) -> dict[str, float]:
    enabled = registry.enabled()
    if not include_synthetic:
        enabled = [
            scenario
            for scenario in enabled
            if scenario.category != ScenarioCategory.SYNTHETIC_THREAT_EVALUATION
        ]
    weights: dict[str, float] = {}
    for scenario in enabled:
        if configured_weights and scenario.scenario_id in configured_weights:
            weights[scenario.scenario_id] = configured_weights[scenario.scenario_id]
        else:
            weights[scenario.scenario_id] = registry.weight_for(scenario.scenario_id)
    return normalize_weights(weights)


def weighted_choice(
    registry: ScenarioRegistry,
    rng: random.Random,
    *,
    configured_weights: dict[str, float] | None = None,
    include_synthetic: bool = True,
) -> ScenarioDefinition:
    weights = build_weight_map(
        registry,
        configured_weights=configured_weights,
        include_synthetic=include_synthetic,
    )
    scenario_ids = list(weights.keys())
    values = [weights[sid] for sid in scenario_ids]
    chosen_id = rng.choices(scenario_ids, weights=values, k=1)[0]
    return registry.get(chosen_id)
