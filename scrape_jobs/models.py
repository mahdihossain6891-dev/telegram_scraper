"""Scrape job status models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

ScrapeJobStatus = Literal["idle", "running", "completed", "failed"]


@dataclass
class ScrapeJobSnapshot:
    """Point-in-time scrape job state for the dashboard API."""

    status: ScrapeJobStatus = "idle"
    channels_total: int = 0
    channels_scanned: int = 0
    messages_analyzed: int = 0
    threats_detected: int = 0
    current_channel: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    last_run_at: str | None = None
    error: str | None = None
    scope: str | None = None
    limit_per_chat: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
