"""Tests for Phase 2 dynamic model discovery (no hardcoded model names)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai.config import AISettings, clear_ai_settings_cache
from ai.providers.base import ProviderHealth
from ai.providers.cache import ModelDiscoveryCache
from ai.providers.discovery import ModelDiscoveryService
from ai.providers.errors import ProviderConfigurationError
from ai.providers.factory import ProviderFactory
from ai.providers.models import DiscoveredModel, ModelCapabilities
from ai.providers.registry import ModelRegistry, reset_model_registry


def _settings(**overrides) -> AISettings:
    base = dict(
        enabled=True,
        chat_provider="ollama",
        chat_model="test-chat",
        embedding_provider="ollama",
        embedding_model="test-embed",
        api_base_url="http://127.0.0.1:11434",
        api_key="",
        vector_backend="none",
        vector_collection="ai_embeddings",
        vector_url="",
        request_timeout_seconds=5.0,
        retry_max_attempts=1,
        retry_backoff_seconds=0.1,
        max_tokens=256,
        daily_token_budget=0,
        default_top_k=8,
        prompts_dir=Path("."),
        embed_batch_size=8,
        chunk_max_chars=500,
        chunk_overlap_chars=50,
        index_message_batch_size=10,
        rag_top_k=4,
        rag_max_evidence_items=4,
        rag_max_context_chars=4000,
        rag_context_token_budget=1000,
        rag_min_score=0.0,
        entity_min_confidence=0.4,
        entity_batch_size=10,
        assistant_name="Sébastien",
        assistant_history_turns=4,
        assistant_session_collection="ai_sessions",
        report_collection="ai_reports",
        model_cache_ttl_seconds=60.0,
    )
    base.update(overrides)
    return AISettings(**base)  # type: ignore[arg-type]


def test_cache_ttl_and_invalidate() -> None:
    cache = ModelDiscoveryCache(default_ttl_seconds=60.0)
    cache.set_models("ollama", [{"model_id": "a"}])
    assert cache.get_models("ollama") == [{"model_id": "a"}]
    cache.invalidate("ollama")
    assert cache.get_models("ollama") is None


def test_factory_discovery_without_chat_model() -> None:
    factory = ProviderFactory(_settings(chat_model=""))
    with pytest.raises(ProviderConfigurationError):
        factory.create("ollama")
    provider = factory.create_for_discovery("ollama")
    assert provider.name == "ollama"
    assert callable(provider.list_models)
    assert callable(provider.health_check)


def test_factory_transparent_list_models(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = ProviderFactory(_settings(chat_model=""))
    fake = MagicMock()
    fake.list_models.return_value = ["dyn-a", "dyn-b"]
    monkeypatch.setattr(factory, "create_for_discovery", lambda *_a, **_k: fake)
    assert factory.list_models("ollama") == ["dyn-a", "dyn-b"]


def test_discovery_uses_cache() -> None:
    fake_provider = MagicMock()
    fake_provider.discover_models.return_value = [
        DiscoveredModel(
            model_id="dyn-1",
            display_name="Dyn 1",
            provider="ollama",
            capabilities=ModelCapabilities(),
        )
    ]
    fake_factory = MagicMock()
    fake_factory.create_for_discovery.return_value = fake_provider

    cache = ModelDiscoveryCache(default_ttl_seconds=300.0)
    svc = ModelDiscoveryService(
        settings=_settings(),
        cache=cache,
        factory=fake_factory,
    )
    first = svc.discover_models("ollama")
    second = svc.discover_models("ollama")
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["count"] == 1
    assert fake_factory.create_for_discovery.call_count == 1


def test_discovery_refresh_bypasses_cache() -> None:
    fake_provider = MagicMock()
    fake_provider.discover_models.return_value = [
        DiscoveredModel(
            model_id="dyn-1",
            display_name="Dyn 1",
            provider="ollama",
            capabilities=ModelCapabilities(),
        )
    ]
    fake_factory = MagicMock()
    fake_factory.create_for_discovery.return_value = fake_provider
    svc = ModelDiscoveryService(
        settings=_settings(),
        cache=ModelDiscoveryCache(default_ttl_seconds=300.0),
        factory=fake_factory,
    )
    svc.discover_models("ollama")
    refreshed = svc.discover_models("ollama", refresh=True)
    assert refreshed["cached"] is False
    assert fake_factory.create_for_discovery.call_count == 2


def test_discovery_offline_provider() -> None:
    fake_factory = MagicMock()
    fake_factory.create_for_discovery.side_effect = ProviderConfigurationError(
        "offline",
        provider="ollama",
        operation="factory",
    )
    svc = ModelDiscoveryService(
        settings=_settings(),
        cache=ModelDiscoveryCache(default_ttl_seconds=300.0),
        factory=fake_factory,
    )
    result = svc.discover_models("ollama", refresh=True)
    assert result["models"] == []
    assert result["error"]
    assert result["count"] == 0


def test_provider_health_status_mapping() -> None:
    fake_provider = MagicMock()
    fake_provider.health_check.return_value = ProviderHealth(
        ok=True,
        provider="ollama",
        detail="reachable",
        models_available=2,
    )
    fake_factory = MagicMock()
    fake_factory.create_for_discovery.return_value = fake_provider
    svc = ModelDiscoveryService(
        settings=_settings(),
        cache=ModelDiscoveryCache(default_ttl_seconds=300.0),
        factory=fake_factory,
    )
    health = svc.provider_health("ollama", refresh=True)
    assert health["ok"] is True
    assert health["status"] in {"healthy", "slow"}
    assert health["models_available"] == 2


def test_registry_refresh() -> None:
    reset_model_registry()
    fake_provider = MagicMock()
    fake_provider.discover_models.return_value = [
        DiscoveredModel(
            model_id="x",
            display_name="X",
            provider="lmstudio",
            capabilities=ModelCapabilities(),
        )
    ]
    fake_factory = MagicMock()
    fake_factory.create_for_discovery.return_value = fake_provider
    cache = ModelDiscoveryCache(default_ttl_seconds=300.0)
    discovery = ModelDiscoveryService(
        settings=_settings(chat_provider="lmstudio"),
        cache=cache,
        factory=fake_factory,
    )
    registry = ModelRegistry(
        settings=_settings(chat_provider="lmstudio"),
        discovery=discovery,
        cache=cache,
    )
    registry.available_models("lmstudio")
    registry.refresh("lmstudio")
    assert fake_factory.create_for_discovery.call_count == 2


def test_catalog_has_no_hardcoded_model_names() -> None:
    svc = ModelDiscoveryService(settings=_settings())
    catalog = svc.list_provider_catalog()
    ids = {row["id"] for row in catalog}
    assert "ollama" in ids
    assert "openrouter" in ids
    assert "lmstudio" in ids
    # Catalog entries are providers only — never a model id list.
    for row in catalog:
        assert "models" not in row


def teardown_module(_module) -> None:
    clear_ai_settings_cache()
    reset_model_registry()
