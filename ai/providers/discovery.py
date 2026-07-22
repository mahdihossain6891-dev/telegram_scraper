"""Model discovery service — queries providers and normalizes metadata.

Independent of chat completion paths. Never hardcodes model names.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ai.config import AISettings, get_ai_settings
from ai.providers.base import ChatModelProvider
from ai.providers.cache import ModelDiscoveryCache
from ai.providers.errors import ProviderError
from ai.providers.models import (
    KNOWN_PROVIDERS,
    DiscoveredModel,
    ModelCapabilities,
)

logger = logging.getLogger("ai.providers.discovery")

_ALIASES = {"local": "ollama"}


def _normalize_provider(name: str | None, settings: AISettings) -> str:
    raw = (name or settings.chat_provider or "none").strip().lower()
    return _ALIASES.get(raw, raw)


class ModelDiscoveryService:
    """Discover models from a provider via the ProviderFactory."""

    def __init__(
        self,
        *,
        settings: AISettings | None = None,
        cache: ModelDiscoveryCache | None = None,
        factory: Any | None = None,
    ) -> None:
        self.settings = settings or get_ai_settings()
        ttl = float(getattr(self.settings, "model_cache_ttl_seconds", 300.0) or 300.0)
        self.cache = cache or ModelDiscoveryCache(default_ttl_seconds=ttl)
        self._factory = factory

    def _factory_instance(self) -> Any:
        if self._factory is not None:
            return self._factory
        from ai.providers.factory import ProviderFactory

        return ProviderFactory(self.settings)

    def list_provider_catalog(self) -> list[dict[str, Any]]:
        """Return static provider catalog (no model names)."""
        configured = _normalize_provider(self.settings.chat_provider, self.settings)
        out: list[dict[str, Any]] = []
        for desc in KNOWN_PROVIDERS:
            if desc.id == "local":
                continue  # exposed as ollama; local remains a config alias
            row = desc.to_dict()
            row["configured"] = desc.id == configured or (
                configured == "ollama" and desc.id == "ollama"
            )
            row["selected"] = desc.id == configured
            out.append(row)
        return out

    def discover_models(
        self,
        provider: str | None = None,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        name = _normalize_provider(provider, self.settings)
        if name in {"none", ""}:
            return {
                "provider": name or "none",
                "models": [],
                "cached": False,
                "error": "No chat provider configured.",
                "count": 0,
            }

        if not refresh:
            cached = self.cache.get_models(name)
            if cached is not None:
                return {
                    "provider": name,
                    "models": cached,
                    "cached": True,
                    "error": None,
                    "count": len(cached),
                }

        started = time.perf_counter()
        error: str | None = None
        models: list[DiscoveredModel] = []
        try:
            chat = self._factory_instance().create_for_discovery(name)
            models = self._discover_from_provider(chat, name)
        except ProviderError as exc:
            error = str(exc)
            logger.warning(
                "model_discovery_failed",
                extra={"ai_provider": name, "ai_detail": error},
            )
        except Exception as exc:  # noqa: BLE001 — surface as soft error
            error = str(exc)
            logger.exception("model_discovery_unexpected", extra={"ai_provider": name})

        payload = [m.to_dict() for m in models]
        if error is None:
            self.cache.set_models(name, payload)

        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "provider": name,
            "models": payload,
            "cached": False,
            "error": error,
            "count": len(payload),
            "latency_ms": latency_ms,
        }

    def provider_health(
        self,
        provider: str | None = None,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        name = _normalize_provider(provider, self.settings)
        if name in {"none", ""}:
            return {
                "provider": "none",
                "ok": False,
                "status": "offline",
                "detail": "No chat provider configured.",
                "latency_ms": None,
                "models_available": 0,
                "cached": False,
            }

        if not refresh:
            cached = self.cache.get_health(name)
            if cached is not None:
                return {**cached, "cached": True}

        started = time.perf_counter()
        try:
            chat = self._factory_instance().create_for_discovery(name)
            health = chat.health_check()
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            status = self._status_from_health(health.ok, latency_ms)
            payload = {
                "provider": name,
                "ok": health.ok,
                "status": status,
                "detail": health.detail,
                "latency_ms": latency_ms,
                "models_available": health.models_available,
                "last_success_at": time.time() if health.ok else None,
                "last_failure_at": None if health.ok else time.time(),
                "cached": False,
            }
            self.cache.set_health(name, payload)
            return payload
        except Exception as exc:  # noqa: BLE001
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            payload = {
                "provider": name,
                "ok": False,
                "status": "offline",
                "detail": str(exc),
                "latency_ms": latency_ms,
                "models_available": 0,
                "last_success_at": None,
                "last_failure_at": time.time(),
                "cached": False,
            }
            self.cache.set_health(name, payload, ttl_seconds=30.0)
            return payload

    def catalog_with_health(self, *, refresh: bool = False) -> dict[str, Any]:
        providers = []
        for row in self.list_provider_catalog():
            health = self.provider_health(row["id"], refresh=refresh)
            providers.append(
                {
                    **row,
                    "health": {
                        "ok": health.get("ok"),
                        "status": health.get("status"),
                        "latency_ms": health.get("latency_ms"),
                        "models_available": health.get("models_available"),
                        "detail": health.get("detail"),
                    },
                }
            )
        return {
            "providers": providers,
            "selected_provider": _normalize_provider(self.settings.chat_provider, self.settings),
            "cache": self.cache.stats(),
        }

    def _discover_from_provider(
        self,
        chat: ChatModelProvider,
        provider: str,
    ) -> list[DiscoveredModel]:
        # Prefer rich discovery when available.
        discover = getattr(chat, "discover_models", None)
        if callable(discover):
            result = discover()
            if isinstance(result, list):
                return [m for m in result if isinstance(m, DiscoveredModel)]

        names = chat.list_models()
        return [
            DiscoveredModel(
                model_id=n,
                display_name=n,
                provider=provider,
                capabilities=ModelCapabilities(supports_streaming=True),
            )
            for n in names
            if isinstance(n, str) and n.strip()
        ]

    @staticmethod
    def _status_from_health(ok: bool, latency_ms: float) -> str:
        if not ok:
            return "offline"
        if latency_ms >= 2500:
            return "slow"
        return "healthy"
