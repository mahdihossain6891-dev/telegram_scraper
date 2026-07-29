"""Simulator enumerations — extend here as new phases add capabilities."""

from __future__ import annotations

from enum import Enum


class EnvironmentType(str, Enum):
    """Runtime environment selector for the intelligence platform."""

    LIVE = "live"
    SIMULATION = "simulation"
    # Reserved for future phases — not selectable until implemented.
    PLAYBACK = "playback"
    OFFLINE_IMPORT = "offline_import"

    @classmethod
    def active_types(cls) -> tuple["EnvironmentType", ...]:
        """Environments that may be selected in Phase 2."""
        return (cls.LIVE, cls.SIMULATION)


class SimulationState(str, Enum):
    """Lifecycle state of the simulator control plane (Phase 2)."""

    INITIALIZED = "initialized"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class SimulationSpeed(str, Enum):
    """Playback speed presets for future traffic generation."""

    REALTIME = "realtime"
    FAST = "fast"
    TURBO = "turbo"
    INSTANT = "instant"


class MessageSourceKind(str, Enum):
    """Origin of message events consumed by the intelligence pipeline."""

    TELETHON = "telethon"
    SIMULATION = "simulation"
    PLAYBACK = "playback"
    OFFLINE_IMPORT = "offline_import"
