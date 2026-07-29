"""Execution engine enumerations."""

from __future__ import annotations

from enum import Enum


class SessionStatus(str, Enum):
    """Lifecycle state of a simulation session."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TickInterval(str, Enum):
    """Supported simulated time increments per tick."""

    ONE_SECOND = "1s"
    TEN_SECONDS = "10s"
    THIRTY_SECONDS = "30s"
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"

    def seconds(self) -> int:
        mapping = {
            TickInterval.ONE_SECOND: 1,
            TickInterval.TEN_SECONDS: 10,
            TickInterval.THIRTY_SECONDS: 30,
            TickInterval.ONE_MINUTE: 60,
            TickInterval.FIVE_MINUTES: 300,
            TickInterval.FIFTEEN_MINUTES: 900,
            TickInterval.ONE_HOUR: 3600,
        }
        return mapping[self]
