"""Thread-safe in-memory scrape job state."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from scrape_jobs.models import ScrapeJobSnapshot, ScrapeJobStatus


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ScrapeJobStore:
    """Tracks the latest scrape job for dashboard polling."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = ScrapeJobSnapshot()

    def snapshot(self) -> ScrapeJobSnapshot:
        with self._lock:
            return ScrapeJobSnapshot(**self._state.to_dict())

    def to_dict(self) -> dict:
        with self._lock:
            return self._state.to_dict()

    def is_running(self) -> bool:
        with self._lock:
            return self._state.status == "running"

    def try_begin(self) -> bool:
        """Reserve the job slot before background work starts."""
        with self._lock:
            if self._state.status == "running":
                # Reclaim stuck jobs (e.g. crash before complete/fail).
                started = self._state.started_at
                if started:
                    try:
                        started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                        age = (datetime.now(timezone.utc) - started_dt).total_seconds()
                        if age < 90:
                            return False
                    except ValueError:
                        return False
                else:
                    return False
            now = _utc_iso()
            self._state = ScrapeJobSnapshot(
                status="running",
                started_at=now,
                last_run_at=self._state.last_run_at,
            )
            return True

    def set_plan(
        self,
        *,
        channels_total: int,
        scope: str,
        limit_per_chat: int,
    ) -> None:
        with self._lock:
            self._state.channels_total = channels_total
            self._state.scope = scope
            self._state.limit_per_chat = limit_per_chat

    def start(
        self,
        *,
        channels_total: int,
        scope: str,
        limit_per_chat: int,
    ) -> bool:
        with self._lock:
            if self._state.status == "running" and self._state.channels_total > 0:
                return False
            now = _utc_iso()
            self._state = ScrapeJobSnapshot(
                status="running",
                channels_total=channels_total,
                channels_scanned=0,
                messages_analyzed=0,
                threats_detected=0,
                current_channel=None,
                started_at=self._state.started_at or now,
                finished_at=None,
                last_run_at=self._state.last_run_at,
                error=None,
                scope=scope,
                limit_per_chat=limit_per_chat,
            )
            return True

    def update_progress(
        self,
        *,
        channels_scanned: int,
        messages_analyzed: int,
        threats_detected: int,
        current_channel: str | None,
    ) -> None:
        with self._lock:
            if self._state.status != "running":
                return
            self._state.channels_scanned = channels_scanned
            self._state.messages_analyzed = messages_analyzed
            self._state.threats_detected = threats_detected
            self._state.current_channel = current_channel

    def complete(self, *, messages_analyzed: int, threats_detected: int) -> None:
        with self._lock:
            now = _utc_iso()
            self._state.status = "completed"
            self._state.channels_scanned = self._state.channels_total
            self._state.messages_analyzed = messages_analyzed
            self._state.threats_detected = threats_detected
            self._state.current_channel = None
            self._state.finished_at = now
            self._state.last_run_at = now
            self._state.error = None

    def fail(self, message: str) -> None:
        with self._lock:
            now = _utc_iso()
            self._state.status = "failed"
            self._state.finished_at = now
            self._state.last_run_at = now
            self._state.current_channel = None
            self._state.error = message


_STORE: ScrapeJobStore | None = None
_STORE_LOCK = threading.Lock()


def get_scrape_job_store() -> ScrapeJobStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = ScrapeJobStore()
        return _STORE


def reset_scrape_job_store() -> None:
    """Reset singleton (tests)."""
    global _STORE
    with _STORE_LOCK:
        _STORE = None
