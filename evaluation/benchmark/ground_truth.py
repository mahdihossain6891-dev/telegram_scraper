"""Ground truth resolution — evaluation only, never during simulation display."""

from __future__ import annotations

from typing import Any

from simulator.scenario.labels import ExpectedRiskLevel, InvestigationOutcome
from simulator.scenario.registry import ScenarioRegistry
from simulator.scenario.templates import GroundTruth


def _baseline_ground_truth() -> dict[str, Any]:
    return GroundTruth(
        expected_risk_level=ExpectedRiskLevel.NORMAL,
        expected_alert=False,
        expected_keywords=(),
        expected_entities=(),
        expected_relationships=(),
        expected_behavioral_score=0.1,
        expected_investigation_outcome=InvestigationOutcome.NO_ACTION,
        expected_confidence=0.2,
    ).to_dict()


def resolve_ground_truth(
    *,
    scenario_id: str | None = None,
    normalized_text: str = "",
    keywords: list[str] | None = None,
    has_alert: bool = False,
    registry: ScenarioRegistry | None = None,
) -> dict[str, Any]:
    """Resolve hidden ground truth for evaluation samples."""
    reg = registry or ScenarioRegistry.with_builtins()
    if scenario_id:
        scenario = reg.get(scenario_id)
        if scenario and scenario.ground_truth:
            return scenario.ground_truth.to_dict()
    keywords = keywords or []
    haystack = normalized_text.lower()
    for scenario in reg.all():
        gt = scenario.ground_truth
        if gt is None or not gt.synthetic_evaluation:
            continue
        gt_dict = gt.to_dict()
        expected_kws = gt_dict.get("expected_keywords") or []
        if any(kw in haystack or kw in keywords for kw in expected_kws):
            return gt_dict
        if gt_dict.get("expected_alert") and has_alert:
            return gt_dict
    scenario = reg.get("general_chat")
    if scenario and scenario.ground_truth:
        return scenario.ground_truth.to_dict()
    return _baseline_ground_truth()
