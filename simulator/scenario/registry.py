"""Scenario registry — register and lookup scenario definitions."""

from __future__ import annotations

from simulator.exceptions import SimulationError
from simulator.scenario.templates import ScenarioDefinition, builtin_scenario_templates


class ScenarioRegistry:
    """Stores scenario definitions and enabled/weight overrides."""

    def __init__(self) -> None:
        self._scenarios: dict[str, ScenarioDefinition] = {}
        self._enabled: set[str] = set()
        self._weight_overrides: dict[str, float] = {}

    def register(self, scenario: ScenarioDefinition) -> None:
        if scenario.scenario_id in self._scenarios:
            raise SimulationError(f"Scenario already registered: {scenario.scenario_id}")
        self._scenarios[scenario.scenario_id] = scenario
        if scenario.enabled:
            self._enabled.add(scenario.scenario_id)

    def register_many(self, scenarios: list[ScenarioDefinition]) -> None:
        for scenario in scenarios:
            self.register(scenario)

    def get(self, scenario_id: str) -> ScenarioDefinition:
        if scenario_id not in self._scenarios:
            raise SimulationError(f"Unknown scenario: {scenario_id}")
        return self._scenarios[scenario_id]

    def all(self) -> list[ScenarioDefinition]:
        return list(self._scenarios.values())

    def enabled(self) -> list[ScenarioDefinition]:
        return [self._scenarios[sid] for sid in self._enabled if sid in self._scenarios]

    def is_enabled(self, scenario_id: str) -> bool:
        return scenario_id in self._enabled

    def enable(self, scenario_id: str) -> None:
        self.get(scenario_id)
        self._enabled.add(scenario_id)

    def disable(self, scenario_id: str) -> None:
        self.get(scenario_id)
        self._enabled.discard(scenario_id)

    def set_weight(self, scenario_id: str, weight: float) -> None:
        self.get(scenario_id)
        self._weight_overrides[scenario_id] = weight

    def weight_for(self, scenario_id: str) -> float:
        if scenario_id in self._weight_overrides:
            return self._weight_overrides[scenario_id]
        return self.get(scenario_id).weight

    @classmethod
    def with_builtins(cls) -> ScenarioRegistry:
        registry = cls()
        registry.register_many(builtin_scenario_templates())
        return registry
