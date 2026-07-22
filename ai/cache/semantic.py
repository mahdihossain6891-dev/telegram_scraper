"""Semantic cache for embeddings, responses, and retrieved context."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CacheEntry:
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 3600.0
    tags: list[str] = field(default_factory=list)

    def expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


class SemanticCache:
    """In-memory semantic cache with tag-based invalidation."""

    def __init__(self, *, default_ttl: float = 3600.0) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    @staticmethod
    def make_key(*parts: Any) -> str:
        payload = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None or entry.expired():
            self._misses += 1
            if entry is not None:
                del self._entries[key]
            return None
        self._hits += 1
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        *,
        ttl_seconds: float | None = None,
        tags: list[str] | None = None,
    ) -> None:
        self._entries[key] = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds or self._default_ttl,
            tags=list(tags or []),
        )

    def invalidate(self, *, tag: str | None = None, key: str | None = None) -> int:
        removed = 0
        if key and key in self._entries:
            del self._entries[key]
            return 1
        if tag:
            to_delete = [k for k, e in self._entries.items() if tag in e.tags]
            for k in to_delete:
                del self._entries[k]
                removed += 1
        return removed

    def stats(self) -> dict[str, int]:
        return {
            "entries": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
        }
