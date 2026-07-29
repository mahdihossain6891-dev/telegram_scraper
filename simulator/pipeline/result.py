"""Pipeline processing result."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.pipeline.context import ProcessingContext


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Outcome of processing one MessageEvent."""

    context: ProcessingContext
    success: bool
    failed_stages: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "failed_stages": list(self.failed_stages),
            "context": self.context.to_dict(),
            "metadata": dict(self.metadata),
        }
