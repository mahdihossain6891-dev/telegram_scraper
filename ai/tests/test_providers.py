"""Tests for multi-provider factory — no network required."""

from __future__ import annotations

import pytest

from ai.config import AISettings, clear_ai_settings_cache
from ai.providers.base import ChatMessage, ProviderHealth
from ai.providers.errors import ProviderConfigurationError
from ai.providers.factory import ProviderFactory
from ai.providers.lmstudio import LMStudioChatProvider
from ai.providers.ollama import OllamaChatProvider
from ai.providers.openrouter import OpenRouterChatProvider


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
        prompts_dir=__import__("pathlib").Path("."),
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
    )
    base.update(overrides)
    return AISettings(**base)  # type: ignore[arg-type]


def test_factory_create_ollama() -> None:
    factory = ProviderFactory(_settings(chat_provider="ollama"))
    provider = factory.create("ollama")
    assert isinstance(provider, OllamaChatProvider)
    assert provider.name == "ollama"


def test_factory_local_alias_maps_to_ollama() -> None:
    factory = ProviderFactory(_settings(chat_provider="local"))
    provider = factory.create_chat_provider()
    assert isinstance(provider, OllamaChatProvider)


def test_factory_create_openrouter() -> None:
    factory = ProviderFactory(
        _settings(chat_provider="openrouter", api_key="sk-or-v1-test", api_base_url="")
    )
    provider = factory.create("openrouter")
    assert isinstance(provider, OpenRouterChatProvider)
    assert provider.name == "openrouter"


def test_factory_create_lmstudio() -> None:
    factory = ProviderFactory(_settings(chat_provider="lmstudio", api_base_url=""))
    provider = factory.create("lmstudio")
    assert isinstance(provider, LMStudioChatProvider)
    assert provider.name == "lmstudio"


def test_factory_openrouter_requires_api_key() -> None:
    factory = ProviderFactory(_settings(chat_provider="openrouter", api_key=""))
    with pytest.raises(ProviderConfigurationError):
        factory.create("openrouter")


def test_factory_openrouter_rejects_non_sk_or_key() -> None:
    factory = ProviderFactory(
        _settings(
            chat_provider="openrouter",
            api_key="126f9da908bc71de0b8857d20052e4b79991d723ddf0022bd9ff0613f7abc1c8",
        )
    )
    with pytest.raises(ProviderConfigurationError, match="sk-or-v1"):
        factory.create("openrouter")


def test_factory_requires_chat_model() -> None:
    factory = ProviderFactory(_settings(chat_provider="ollama", chat_model=""))
    with pytest.raises(ProviderConfigurationError):
        factory.create("ollama")


def test_disabled_provider_health() -> None:
    factory = ProviderFactory(_settings(enabled=False))
    provider = factory.create()
    health = provider.health_check()
    assert isinstance(health, ProviderHealth)
    assert health.ok is False
    assert provider.list_models() == []


def test_complete_aliases_chat() -> None:
    """LLMClient uses complete(); providers implement chat()."""
    factory = ProviderFactory(_settings(chat_provider="lmstudio"))
    provider = factory.create()
    # Instantiation ok; network call not asserted here.
    assert callable(provider.complete)
    assert callable(provider.chat)
    assert callable(provider.stream_chat)
    assert callable(provider.health_check)
    assert callable(provider.list_models)


def test_unsupported_provider_name() -> None:
    factory = ProviderFactory(_settings())
    with pytest.raises(ProviderConfigurationError):
        factory.create("unknown-vendor")


def teardown_module(_module) -> None:
    clear_ai_settings_cache()
