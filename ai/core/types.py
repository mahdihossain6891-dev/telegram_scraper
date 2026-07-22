"""Core AI platform types."""

from __future__ import annotations

from enum import Enum
from typing import Literal

AIEnvironment = Literal["live", "simulation"]


class PlatformEnvironment(str, Enum):
    """Runtime environment for AI data access — never mix LIVE and SIMULATION."""

    LIVE = "live"
    SIMULATION = "simulation"

    @classmethod
    def from_filters(cls, filters: dict | None) -> "PlatformEnvironment":
        raw = str((filters or {}).get("environment") or "live").lower()
        if raw in {"simulation", "sim", "test"}:
            return cls.SIMULATION
        return cls.LIVE

    def rag_filter(self) -> dict[str, str]:
        return {"environment": self.value}
