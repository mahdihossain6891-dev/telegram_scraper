"""Dataset import, export, versioning — immutable once benchmarked."""

from __future__ import annotations

import json
from typing import Any

from evaluation.datasets.models import EvaluationDataset, new_dataset_id
from simulator.scenario.registry import ScenarioRegistry


class DatasetManager:
    def __init__(self) -> None:
        self._datasets: dict[str, EvaluationDataset] = {}
        self._seed_builtin()

    def _seed_builtin(self) -> None:
        registry = ScenarioRegistry.with_builtins()
        synthetic = [
            s.scenario_id
            for s in registry.all()
            if s.ground_truth and s.ground_truth.synthetic_evaluation
        ]
        normal = [
            s.scenario_id
            for s in registry.all()
            if s.ground_truth and not s.ground_truth.synthetic_evaluation
        ]
        ds = EvaluationDataset(
            dataset_id=new_dataset_id(),
            name="builtin-synthetic-threat",
            version="1.0.0",
            scenario_ids=synthetic,
            tags=["synthetic", "threat", "builtin"],
        )
        self._datasets[ds.dataset_id] = ds
        ds2 = EvaluationDataset(
            dataset_id=new_dataset_id(),
            name="builtin-normal-baseline",
            version="1.0.0",
            scenario_ids=normal[:5],
            tags=["normal", "baseline", "builtin"],
        )
        self._datasets[ds2.dataset_id] = ds2

    def list(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self._datasets.values()]

    def get(self, dataset_id: str) -> EvaluationDataset:
        ds = self._datasets.get(dataset_id)
        if ds is None:
            raise KeyError(f"Dataset {dataset_id} not found")
        return ds

    def import_dataset(
        self,
        *,
        name: str,
        scenario_ids: list[str],
        version: str = "1.0.0",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        ds = EvaluationDataset(
            dataset_id=new_dataset_id(),
            name=name,
            version=version,
            scenario_ids=scenario_ids,
            tags=tags or [],
        )
        self._datasets[ds.dataset_id] = ds
        return ds.to_dict()

    def export_dataset(self, dataset_id: str) -> str:
        return json.dumps(self.get(dataset_id).to_dict(), indent=2)

    def freeze(self, dataset_id: str) -> dict[str, Any]:
        ds = self.get(dataset_id)
        ds.frozen = True
        return ds.to_dict()

    def tag(self, dataset_id: str, tag: str) -> dict[str, Any]:
        ds = self.get(dataset_id)
        if tag not in ds.tags:
            ds.tags.append(tag)
        return ds.to_dict()

    def version_dataset(self, dataset_id: str, new_version: str) -> dict[str, Any]:
        src = self.get(dataset_id)
        if src.frozen:
            raise ValueError("Cannot version a frozen dataset — import a copy instead")
        src.version = new_version
        return src.to_dict()
