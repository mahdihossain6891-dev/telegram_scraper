"""Evaluation dataset models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class EvaluationDataset:
    dataset_id: str
    name: str
    version: str
    scenario_ids: list[str]
    tags: list[str] = field(default_factory=list)
    frozen: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "version": self.version,
            "scenario_ids": list(self.scenario_ids),
            "tags": list(self.tags),
            "frozen": self.frozen,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }


def new_dataset_id() -> str:
    return f"ds-{uuid4().hex[:12]}"
