"""Unit tests for Phase 2 provider abstraction (ai package only)."""

from __future__ import annotations

import json
from dataclasses import replace
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from ai.config import AISettings, clear_ai_settings_cache
from ai.providers import (
    ChatMessage,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderFactory,
    ProviderHTTPError,
    create_chat_provider,
)
from ai.providers.local import LocalProvider, normalize_ollama_base_url
from ai.providers.retry import call_with_retry
from ai.providers.transport import post_json


def _settings(**kwargs) -> AISettings:
    clear_ai_settings_cache()
    from dataclasses import replace
    from pathlib import Path

    base = AISettings(
        enabled=True,
        chat_provider="local",
        chat_model="test-chat",
        embedding_provider="local",
        embedding_model="test-embed",
        api_base_url="http://127.0.0.1:11434",
        api_key="",
        vector_backend="none",
        vector_collection="ai_embeddings",
        vector_url="",
        request_timeout_seconds=5.0,
        retry_max_attempts=3,
        retry_backoff_seconds=0.01,
        max_tokens=128,
        daily_token_budget=0,
        default_top_k=8,
        prompts_dir=Path("."),
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
        entity_batch_size=20,
        assistant_name='Investigation Assistant',
        assistant_history_turns=8,
        assistant_session_collection='ai_sessions',
        report_collection='ai_reports',
    )
    return replace(base, **kwargs) if kwargs else base


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._raw = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None


def test_normalize_ollama_base_url_strips_paths() -> None:
    assert normalize_ollama_base_url("http://127.0.0.1:11434/v1") == "http://127.0.0.1:11434"
    assert normalize_ollama_base_url("http://localhost:11434/api/") == "http://localhost:11434"


def test_factory_requires_chat_model_for_local() -> None:
    settings = _settings(chat_model="")
    with pytest.raises(ProviderConfigurationError):
        ProviderFactory(settings).create_chat_provider()


def test_factory_disabled_when_ai_off() -> None:
    settings = _settings(enabled=False)
    provider = ProviderFactory(settings).create_chat_provider()
    assert provider.name == "none"
    with pytest.raises(ProviderConfigurationError):
        provider.complete([ChatMessage(role="user", content="hi")])


def test_local_chat_complete_parses_ollama_response() -> None:
    settings = _settings()
    chat = ProviderFactory(settings).create_chat_provider()
    payload = {
        "model": "test-chat",
        "message": {"role": "assistant", "content": "hello"},
        "prompt_eval_count": 3,
        "eval_count": 1,
    }

    with patch("ai.providers.transport.urllib.request.urlopen", return_value=_FakeResponse(payload)):
        result = chat.complete([ChatMessage(role="user", content="ping")])

    assert result.content == "hello"
    assert result.model == "test-chat"
    assert result.usage["prompt_tokens"] == 3


def test_local_embed_parses_ollama_response() -> None:
    settings = _settings()
    emb = ProviderFactory(settings).create_embedding_provider()
    payload = {
        "model": "test-embed",
        "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
    }

    with patch("ai.providers.transport.urllib.request.urlopen", return_value=_FakeResponse(payload)):
        result = emb.embed(["a", "b"])

    assert len(result.vectors) == 2
    assert result.vectors[0] == [0.1, 0.2, 0.3]


def test_local_rejects_missing_model_at_call_time() -> None:
    runtime = LocalProvider(chat_model="", embedding_model="")
    with pytest.raises(ProviderConfigurationError):
        runtime.complete([ChatMessage(role="user", content="x")])


def test_retry_on_connection_error() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ProviderConnectionError("boom", provider="local", operation="chat")
        return "ok"

    assert call_with_retry("chat", flaky, max_attempts=3, backoff_seconds=0.001, provider="local") == "ok"
    assert calls["n"] == 3


def test_http_error_mapped() -> None:
    err = HTTPError("http://x", 503, "unavailable", hdrs=None, fp=BytesIO(b"down"))
    with patch("ai.providers.transport.urllib.request.urlopen", side_effect=err):
        with pytest.raises(ProviderHTTPError) as exc:
            post_json("http://x/api/chat", {}, timeout_seconds=1, provider="local", operation="chat")
    assert exc.value.status_code == 503


def test_connection_error_mapped() -> None:
    with patch(
        "ai.providers.transport.urllib.request.urlopen",
        side_effect=URLError("refused"),
    ):
        with pytest.raises(ProviderConnectionError):
            post_json("http://x/api/chat", {}, timeout_seconds=1, provider="local", operation="chat")


def test_create_chat_provider_helper() -> None:
    settings = _settings(enabled=False)
    assert create_chat_provider(settings).name == "none"
