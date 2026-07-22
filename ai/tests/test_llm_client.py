"""Tests for runtime LLM client resolution (OpenRouter / Control Center overrides)."""

from __future__ import annotations

from ai.config import AISettings
from ai.llm.client import create_llm_client
from ai.providers.ollama import OllamaChatProvider
from ai.providers.openrouter import OpenRouterChatProvider


def _settings(**overrides: object) -> AISettings:
    base = dict(
        enabled=True,
        chat_provider="ollama",
        chat_model="llama3.2",
        embedding_provider="local",
        embedding_model="nomic-embed-text",
        api_base_url="http://127.0.0.1:11434",
        api_key="sk-test",
        vector_backend="none",
        vector_collection="ai_embeddings",
        vector_url="",
        request_timeout_seconds=30.0,
        retry_max_attempts=1,
        retry_backoff_seconds=0.1,
        max_tokens=2048,
        daily_token_budget=0,
        default_top_k=8,
        prompts_dir=__import__("pathlib").Path("."),
        embed_batch_size=32,
        chunk_max_chars=1200,
        chunk_overlap_chars=150,
        index_message_batch_size=100,
        rag_top_k=8,
        rag_max_evidence_items=8,
        rag_max_context_chars=12000,
        rag_context_token_budget=3000,
        rag_min_score=0.0,
        entity_min_confidence=0.4,
        entity_batch_size=50,
        assistant_name="Sébastien",
        assistant_history_turns=8,
        assistant_session_collection="ai_sessions",
        report_collection="ai_reports",
        model_cache_ttl_seconds=300.0,
    )
    base.update(overrides)
    return AISettings(**base)  # type: ignore[arg-type]


def test_create_llm_client_default_uses_env_provider() -> None:
    client = create_llm_client(_settings())
    assert isinstance(client.provider, OllamaChatProvider)


def test_create_llm_client_openrouter_override() -> None:
    client = create_llm_client(
        _settings(api_key="sk-or-test"),
        provider="openrouter",
        model="openai/gpt-4o-mini",
    )
    assert isinstance(client.provider, OpenRouterChatProvider)
    assert client.default_model == "openai/gpt-4o-mini"
