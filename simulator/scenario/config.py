"""Scenario engine configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _default_scenario_weights() -> dict[str, float]:
    return {
        "technology": 0.25,
        "programming": 0.20,
        "university": 0.15,
        "marketplace": 0.10,
        "gaming": 0.10,
        "news": 0.10,
        "general_chat": 0.08,
        "synthetic_financial_fraud": 0.04,
        "synthetic_counterfeit_docs": 0.03,
        "synthetic_narcotics_indicator": 0.03,
    }


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    """Controls scenario selection and execution."""

    enabled_scenarios: frozenset[str] | None = None
    scenario_weights: dict[str, float] = field(default_factory=_default_scenario_weights)
    maximum_concurrent_scenarios: int = 6
    languages: tuple[str, ...] = ("english", "bengali", "hindi", "urdu", "arabic", "malay")
    average_duration_minutes: int = 30
    average_participants: int = 4
    random_seed: int | None = 42
    include_synthetic_threat_evaluation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled_scenarios": sorted(self.enabled_scenarios) if self.enabled_scenarios else None,
            "scenario_weights": dict(self.scenario_weights),
            "maximum_concurrent_scenarios": self.maximum_concurrent_scenarios,
            "languages": list(self.languages),
            "average_duration_minutes": self.average_duration_minutes,
            "average_participants": self.average_participants,
            "random_seed": self.random_seed,
            "include_synthetic_threat_evaluation": self.include_synthetic_threat_evaluation,
        }
