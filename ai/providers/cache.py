"""TTL cache for discovered model lists and provider health snapshots."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class CacheEntry(Generic[T]):
    value: T
    created_at: float
    ttl_seconds: float

    def expired(self, now: float | None = None) -> bool:
        ts = now if now is not None else time.monotonic()
        return (ts - self.created_at) >= self.ttl_seconds


class ModelDiscoveryCache:
    """Thread-safe in-memory cache for discovery responses."""

    def __init__(self, *, default_ttl_seconds: float = 300.0) -> None:
        self._default_ttl = max(5.0, float(default_ttl_seconds))
        self._models: dict[str, CacheEntry[list[dict[str, Any]]]] = {}
        self._health: dict[str, CacheEntry[dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def get_models(self, provider: str) -> list[dict[str, Any]] | None:
        with self._lock:
            entry = self._models.get(provider)
            if entry is None or entry.expired():
                return None
            return list(entry.value)

    def set_models(
        self,
        provider: str,
        models: list[dict[str, Any]],
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        with self._lock:
            self._models[provider] = CacheEntry(
                value=list(models),
                created_at=time.monotonic(),
                ttl_seconds=ttl_seconds if ttl_seconds is not None else self._default_ttl,
            )

    def get_health(self, provider: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._health.get(provider)
            if entry is None or entry.expired():
                return None
            return dict(entry.value)

    def set_health(
        self,
        provider: str,
        health: dict[str, Any],
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        with self._lock:
            self._health[provider] = CacheEntry(
                value=dict(health),
                created_at=time.monotonic(),
                ttl_seconds=ttl_seconds if ttl_seconds is not None else min(60.0, self._default_ttl),
            )

    def invalidate(self, provider: str | None = None) -> None:
        with self._lock:
            if provider is None:
                self._models.clear()
                self._health.clear()
                return
            self._models.pop(provider, None)
            self._health.pop(provider, None)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "model_cache_keys": sorted(self._models.keys()),
                "health_cache_keys": sorted(self._health.keys()),
                "default_ttl_seconds": self._default_ttl,
            }
