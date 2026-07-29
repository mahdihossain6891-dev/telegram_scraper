"""Backward-compatible re-export — prefer ``simulator.environment.manager``."""

from __future__ import annotations

from simulator.environment.manager import EnvironmentManager

__all__ = ["EnvironmentManager"]
