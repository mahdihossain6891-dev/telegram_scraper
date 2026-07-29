"""ScenarioManager — facade for scenario registration, selection, and statistics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona
from simulator.scenario.config import ScenarioConfig
from simulator.scenario.engine import ScenarioContext, ScenarioEngine
from simulator.scenario.provider import ScenarioEngineProvider
from simulator.scenario.registry import ScenarioRegistry
from simulator.scenario.statistics import ScenarioHistory, ScenarioStatistics
from simulator.scenario.templates import ScenarioDefinition
from simulator.scenario.validator import validate_registry


class ScenarioManager:
    """Manages scenarios without generating conversations directly."""

    def __init__(
        self,
        config: ScenarioConfig | None = None,
        *,
        registry: ScenarioRegistry | None = None,
    ) -> None:
        self._config = config or ScenarioConfig()
        self._registry = registry or ScenarioRegistry.with_builtins()
        self._history = ScenarioHistory()
        self._apply_config_to_registry()
        self._engine = ScenarioEngine(self._registry, self._config, history=self._history)
        self._provider = ScenarioEngineProvider(self._engine)
        validate_registry(self._registry, self._config)

    def _apply_config_to_registry(self) -> None:
        if self._config.enabled_scenarios is not None:
            enabled = set(self._config.enabled_scenarios)
            for scenario in self._registry.all():
                if scenario.scenario_id in enabled:
                    self._registry.enable(scenario.scenario_id)
                else:
                    self._registry.disable(scenario.scenario_id)
        for scenario_id, weight in self._config.scenario_weights.items():
            try:
                self._registry.get(scenario_id)
            except Exception:
                continue
            self._registry.set_weight(scenario_id, weight)

    @property
    def config(self) -> ScenarioConfig:
        return self._config

    @property
    def registry(self) -> ScenarioRegistry:
        return self._registry

    @property
    def provider(self) -> ScenarioEngineProvider:
        """Return the ScenarioProvider for ConversationManager."""
        return self._provider

    def register(self, scenario: ScenarioDefinition) -> None:
        self._registry.register(scenario)

    def enable(self, scenario_id: str) -> None:
        self._registry.enable(scenario_id)

    def disable(self, scenario_id: str) -> None:
        self._registry.disable(scenario_id)

    def set_weight(self, scenario_id: str, weight: float) -> None:
        self._registry.set_weight(scenario_id, weight)

    def list_scenarios(self) -> list[ScenarioDefinition]:
        return self._registry.all()

    def build_context(
        self,
        *,
        group: Group,
        candidates: list[Persona],
        when: datetime | None = None,
    ) -> ScenarioContext:
        return self._engine.build_context(group=group, candidates=candidates, when=when)

    def get_ground_truth(self, scenario_id: str) -> dict[str, Any] | None:
        scenario = self._registry.get(scenario_id)
        if scenario.ground_truth is None:
            return None
        return scenario.ground_truth.to_dict()

    def get_statistics(self) -> ScenarioStatistics:
        return self._history.statistics()

    def get_history(self) -> list[dict[str, Any]]:
        return [run.to_dict() for run in self._history.runs]
