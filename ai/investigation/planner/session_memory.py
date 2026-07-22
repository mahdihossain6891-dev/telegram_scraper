"""Session-scoped tool result cache for the Investigation Planner.

Avoids re-running expensive tools for the same target within a session
unless the caller forces a refresh.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CachedToolResult:
    tool: str
    cache_key: str
    summary: str
    data: dict[str, Any]
    ok: bool
    error: str | None
    stored_at: float = field(default_factory=time.time)
    confidence: float | None = None
    freshness: float | None = None
    completeness: float | None = None


class PlannerSessionMemory:
    """In-process cache keyed by session + target + tool."""

    def __init__(self, *, ttl_seconds: float = 900.0) -> None:
        self.ttl_seconds = max(30.0, float(ttl_seconds))
        self._entries: dict[str, CachedToolResult] = {}
        self._pinned: dict[str, list[dict[str, Any]]] = {}
        self._targets: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def make_key(
        session_id: str,
        tool: str,
        target: dict[str, Any] | None,
        question_hint: str = "",
    ) -> str:
        subject_bits = {
            k: (target or {}).get(k)
            for k in ("user_id", "chat_id", "alert_id", "case_id", "username")
            if (target or {}).get(k) is not None
        }
        raw = json.dumps(
            {"s": session_id, "t": tool, "sub": subject_bits, "q": question_hint[:120]},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def get(self, cache_key: str) -> CachedToolResult | None:
        with self._lock:
            entry = self._entries.get(cache_key)
            if entry is None:
                return None
            if (time.time() - entry.stored_at) > self.ttl_seconds:
                self._entries.pop(cache_key, None)
                return None
            return entry

    def put(self, entry: CachedToolResult) -> None:
        with self._lock:
            self._entries[entry.cache_key] = entry

    def remember_target(self, session_id: str, target: dict[str, Any]) -> None:
        with self._lock:
            self._targets[session_id] = dict(target or {})

    def current_target(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._targets.get(session_id) or {})

    def pin_evidence(self, session_id: str, items: list[dict[str, Any]]) -> None:
        with self._lock:
            bucket = self._pinned.setdefault(session_id, [])
            seen = {(i.get("label"), i.get("source_id")) for i in bucket}
            for item in items:
                key = (item.get("label"), item.get("source_id"))
                if key not in seen:
                    bucket.append(dict(item))
                    seen.add(key)

    def pinned_evidence(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(i) for i in self._pinned.get(session_id, [])]

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._targets.pop(session_id, None)
            self._pinned.pop(session_id, None)
            drop = [
                k
                for k, v in self._entries.items()
                if k.startswith(session_id) or session_id in (v.cache_key,)
            ]
            # Keys are hashes — drop by scanning stored target sessions via prefix in data.
            drop = [k for k, v in list(self._entries.items()) if session_id in k]
            for k in drop:
                self._entries.pop(k, None)


_MEMORY: PlannerSessionMemory | None = None
_MEMORY_LOCK = threading.Lock()


def get_planner_memory() -> PlannerSessionMemory:
    global _MEMORY
    with _MEMORY_LOCK:
        if _MEMORY is None:
            _MEMORY = PlannerSessionMemory()
        return _MEMORY
