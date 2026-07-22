"""Central Model Registry — stores discovered models and refresh state.

Never contains hardcoded model names. Populated only via ModelDiscoveryService.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from ai.config import AISettings, get_ai_settings
from ai.providers.cache import ModelDiscoveryCache
from ai.providers.discovery import ModelDiscoveryService


class ModelRegistry:
    """In-process registry of discovered models per provider."""

    def __init__(
        self,
        *,
        settings: AISettings | None = None,
        discovery: ModelDiscoveryService | None = None,
        cache: ModelDiscoveryCache | None = None,
    ) -> None:
        self.settings = settings or get_ai_settings()
        self.cache = cache or ModelDiscoveryCache(
            default_ttl_seconds=float(
                getattr(self.settings, "model_cache_ttl_seconds", 300.0) or 300.0
            )
        )
        self.discovery = discovery or ModelDiscoveryService(
            settings=self.settings,
            cache=self.cache,
        )
        self._lock = threading.RLock()
        self._last_refresh: dict[str, float] = {}

    def available_models(
        self,
        provider: str | None = None,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        result = self.discovery.discover_models(provider, refresh=refresh)
        with self._lock:
            if not result.get("cached"):
                self._last_refresh[result.get("provider") or ""] = time.time()
        result["last_refresh_at"] = self._last_refresh.get(result.get("provider") or "")
        return result

    def refresh(self, provider: str | None = None) -> dict[str, Any]:
        if provider:
            self.cache.invalidate(provider)
        else:
            self.cache.invalidate()
        return self.available_models(provider, refresh=True)

    def providers(self, *, refresh_health: bool = False) -> dict[str, Any]:
        return self.discovery.catalog_with_health(refresh=refresh_health)

    def provider_health(
        self,
        provider: str | None = None,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        return self.discovery.provider_health(provider, refresh=refresh)


_REGISTRY: ModelRegistry | None = None
_REGISTRY_LOCK = threading.Lock()


def get_model_registry(settings: AISettings | None = None) -> ModelRegistry:
    """Process-wide ModelRegistry singleton."""
    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is None or (settings is not None and settings is not _REGISTRY.settings):
            _REGISTRY = ModelRegistry(settings=settings)
        return _REGISTRY


def reset_model_registry() -> None:
    """Drop the singleton (tests)."""
    global _REGISTRY
    with _REGISTRY_LOCK:
        _REGISTRY = None
