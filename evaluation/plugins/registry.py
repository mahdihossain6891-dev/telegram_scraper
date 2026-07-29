"""Plugin registry for evaluators."""

from __future__ import annotations

from evaluation.validators.alert import AlertEvaluator
from evaluation.validators.base import BaseEvaluator
from evaluation.validators.behavior import BehaviorEvaluator
from evaluation.validators.keyword import KeywordEvaluator
from evaluation.validators.pipeline import PipelineValidator
from evaluation.validators.relationship import RelationshipEvaluator
from evaluation.validators.risk import RiskEvaluator
from evaluation.validators.sebastian import SebastianEvaluator


def default_evaluators() -> list[BaseEvaluator]:
    return [
        KeywordEvaluator(),
        RiskEvaluator(),
        BehaviorEvaluator(),
        RelationshipEvaluator(),
        AlertEvaluator(),
        PipelineValidator(),
        SebastianEvaluator(),
    ]


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, BaseEvaluator] = {}

    @classmethod
    def with_defaults(cls) -> "EvaluatorRegistry":
        reg = cls()
        for ev in default_evaluators():
            reg.register(ev)
        return reg

    def register(self, evaluator: BaseEvaluator) -> None:
        self._evaluators[evaluator.name] = evaluator

    def get(self, name: str) -> BaseEvaluator | None:
        return self._evaluators.get(name)

    def all(self) -> list[BaseEvaluator]:
        return list(self._evaluators.values())

    def names(self) -> list[str]:
        return list(self._evaluators.keys())
