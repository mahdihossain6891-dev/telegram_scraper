"""Scenario validation rules."""

from __future__ import annotations

from simulator.exceptions import SimulationError
from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona
from simulator.scenario.config import ScenarioConfig
from simulator.scenario.registry import ScenarioRegistry
from simulator.scenario.selector import scenario_matches_group
from simulator.scenario.templates import ScenarioDefinition
from simulator.scenario.weighting import normalize_weights


def validate_weights(weights: dict[str, float]) -> None:
    if not weights:
        raise SimulationError("Scenario weights cannot be empty.")
    normalize_weights(weights)


def validate_scenario_definition(scenario: ScenarioDefinition) -> None:
    if scenario.weight < 0:
        raise SimulationError(f"Scenario {scenario.scenario_id} has negative weight.")
    low, high = scenario.expected_participants
    if low < 1 or high < low:
        raise SimulationError(f"Scenario {scenario.scenario_id} has invalid participant range.")


def validate_scenario_for_group(scenario: ScenarioDefinition, group: Group) -> None:
    if not scenario_matches_group(scenario, group):
        raise SimulationError(
            f"Scenario {scenario.scenario_id} is not compatible with group category {group.category}."
        )


def validate_participants(
    scenario: ScenarioDefinition,
    participants: list[Persona],
    *,
    config: ScenarioConfig,
) -> None:
    low, high = scenario.expected_participants
    if len(participants) < low:
        raise SimulationError(
            f"Scenario {scenario.scenario_id} requires at least {low} participants."
        )
    if len(participants) > max(high, config.average_participants + 2):
        raise SimulationError(
            f"Scenario {scenario.scenario_id} has too many participants selected."
        )
    languages = {persona.language for persona in participants}
    if not languages.intersection(set(scenario.languages)):
        raise SimulationError(
            f"Scenario {scenario.scenario_id} has no language-compatible participants."
        )


def validate_registry(registry: ScenarioRegistry, config: ScenarioConfig) -> None:
    enabled = registry.enabled()
    if not enabled:
        raise SimulationError("No scenarios are enabled.")
    if config.enabled_scenarios:
        missing = set(config.enabled_scenarios) - {scenario.scenario_id for scenario in registry.all()}
        if missing:
            raise SimulationError(f"Unknown enabled scenario IDs: {sorted(missing)}")
    weights = {
        scenario.scenario_id: registry.weight_for(scenario.scenario_id)
        for scenario in enabled
    }
    validate_weights(weights)
    for scenario in enabled:
        validate_scenario_definition(scenario)
