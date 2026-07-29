"""AI / RAG context — isolated index namespace per environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from simulator.enums import EnvironmentType


@dataclass(frozen=True, slots=True)
class AIContext:
    """Metadata for AI sessions, embeddings, and vector indexes."""

    environment: EnvironmentType
    vector_namespace: str
    session_collection: str
    report_collection: str
    embedding_model_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment.value,
            "vector_namespace": self.vector_namespace,
            "session_collection": self.session_collection,
            "report_collection": self.report_collection,
            "embedding_model_hint": self.embedding_model_hint,
        }
