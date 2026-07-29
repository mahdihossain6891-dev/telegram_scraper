"""Relationship graph context — isolated graph namespace per environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from simulator.enums import EnvironmentType


@dataclass(frozen=True, slots=True)
class GraphContext:
    """Metadata for relationship graph storage and exports."""

    environment: EnvironmentType
    graph_namespace: str
    export_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment.value,
            "graph_namespace": self.graph_namespace,
            "export_path": self.export_path,
        }
