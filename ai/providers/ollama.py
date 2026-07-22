"""Ollama provider — native Ollama HTTP API.

Request/response details stay inside this module. Consumers only see
``ChatModelProvider`` / ``EmbeddingProvider`` surfaces from ``ai.providers.base``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from typing import Any
from urllib.parse import urlparse

from ai.providers.base import (
    ChatCompletion,
    ChatMessage,
    ChatModelProvider,
    EmbeddingProvider,
    EmbeddingResult,
    ProviderHealth,
)
from ai.providers.errors import ProviderConfigurationError, ProviderResponseError
from ai.providers.retry import call_with_retry
from ai.providers.transport import get_json, iter_sse_json_lines, join_url, post_json

logger = logging.getLogger("ai.providers.ollama")

_PROVIDER_NAME = "ollama"
_DEFAULT_HOST = "http://127.0.0.1:11434"


def normalize_ollama_base_url(url: str | None) -> str:
    """Normalize a configured base URL to an Ollama host root (no ``/api``)."""
    raw = (url or "").strip() or _DEFAULT_HOST
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ProviderConfigurationError(
            f"Invalid Ollama base URL: {url!r}",
            provider=_PROVIDER_NAME,
            operation="config",
        )
    return f"{parsed.scheme}://{parsed.netloc}"


class OllamaProvider:
    """Ollama runtime shared by chat and embedding adapters."""

    name = _PROVIDER_NAME

    def __init__(
        self,
        *,
        base_url: str = "",
        chat_model: str = "",
        embedding_model: str = "",
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        default_max_tokens: int | None = None,
    ) -> None:
        self.base_url = normalize_ollama_base_url(base_url)
        self.chat_model = (chat_model or "").strip()
        self.embedding_model = (embedding_model or "").strip()
        self.timeout_seconds = float(timeout_seconds)
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_seconds = float(backoff_seconds)
        self.default_max_tokens = default_max_tokens

    def _resolve_chat_model(self, model: str | None) -> str:
        resolved = (model or self.chat_model or "").strip()
        if not resolved:
            raise ProviderConfigurationError(
                "Chat model is not configured. Set AI_CHAT_MODEL or pass model=.",
                provider=self.name,
                operation="chat",
            )
        return resolved

    def _resolve_embedding_model(self, model: str | None) -> str:
        resolved = (model or self.embedding_model or "").strip()
        if not resolved:
            raise ProviderConfigurationError(
                "Embedding model is not configured. "
                "Set AI_EMBEDDING_MODEL or pass model=.",
                provider=self.name,
                operation="embed",
            )
        return resolved

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        if not messages:
            raise ProviderConfigurationError(
                "messages must not be empty",
                provider=self.name,
                operation="chat",
            )

        resolved_model = self._resolve_chat_model(model)
        options: dict[str, Any] = {}
        token_limit = max_tokens if max_tokens is not None else self.default_max_tokens
        if token_limit is not None:
            options["num_predict"] = int(token_limit)
        if temperature is not None:
            options["temperature"] = float(temperature)

        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        if options:
            payload["options"] = options
        if extra:
            for key, value in extra.items():
                if key in {"model", "messages", "stream"}:
                    continue
                if key == "options" and isinstance(value, dict):
                    merged = dict(payload.get("options") or {})
                    merged.update(value)
                    payload["options"] = merged
                else:
                    payload[key] = value

        url = join_url(self.base_url, "/api/chat")

        def _once() -> dict[str, Any]:
            return post_json(
                url,
                payload,
                timeout_seconds=self.timeout_seconds,
                provider=self.name,
                operation="chat",
            )

        data = call_with_retry(
            "chat",
            _once,
            max_attempts=self.max_attempts,
            backoff_seconds=self.backoff_seconds,
            provider=self.name,
        )

        message = data.get("message")
        if not isinstance(message, dict):
            raise ProviderResponseError(
                "Chat response missing message object",
                provider=self.name,
                operation="chat",
                details={"keys": list(data.keys())},
            )
        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderResponseError(
                "Chat response missing message.content string",
                provider=self.name,
                operation="chat",
            )

        usage = {
            "prompt_tokens": data.get("prompt_eval_count"),
            "completion_tokens": data.get("eval_count"),
            "total_duration_ns": data.get("total_duration"),
            "load_duration_ns": data.get("load_duration"),
        }
        used_model = str(data.get("model") or resolved_model)
        return ChatCompletion(
            content=content,
            model=used_model,
            usage={k: v for k, v in usage.items() if v is not None},
            raw=data,
        )

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        """Compatibility alias for callers that used ``LocalProvider.complete``."""
        return self.chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            extra=extra,
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        if not messages:
            raise ProviderConfigurationError(
                "messages must not be empty",
                provider=self.name,
                operation="stream_chat",
            )
        resolved_model = self._resolve_chat_model(model)
        options: dict[str, Any] = {}
        token_limit = max_tokens if max_tokens is not None else self.default_max_tokens
        if token_limit is not None:
            options["num_predict"] = int(token_limit)
        if temperature is not None:
            options["temperature"] = float(temperature)

        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        if options:
            payload["options"] = options
        if extra:
            for key, value in extra.items():
                if key in {"model", "messages", "stream"}:
                    continue
                payload[key] = value

        url = join_url(self.base_url, "/api/chat")
        for event in iter_sse_json_lines(
            url,
            payload,
            timeout_seconds=self.timeout_seconds,
            provider=self.name,
            operation="stream_chat",
        ):
            message = event.get("message")
            if isinstance(message, dict):
                chunk = message.get("content")
                if isinstance(chunk, str) and chunk:
                    yield chunk
            if event.get("done") is True:
                break

    def health_check(self) -> ProviderHealth:
        try:
            data = get_json(
                join_url(self.base_url, "/api/tags"),
                timeout_seconds=min(self.timeout_seconds, 10.0),
                provider=self.name,
                operation="health_check",
            )
            models = data.get("models") if isinstance(data.get("models"), list) else []
            return ProviderHealth(
                ok=True,
                provider=self.name,
                detail="reachable",
                models_available=len(models),
                raw={"base_url": self.base_url},
            )
        except Exception as exc:  # noqa: BLE001 — health never raises
            return ProviderHealth(
                ok=False,
                provider=self.name,
                detail=str(exc),
                raw={"base_url": self.base_url},
            )

    def list_models(self) -> list[str]:
        return [m.model_id for m in self.discover_models()]

    def discover_models(self) -> list:
        """Return rich metadata for installed Ollama models (no hardcoding)."""
        from ai.providers.models import DiscoveredModel, ModelCapabilities

        data = get_json(
            join_url(self.base_url, "/api/tags"),
            timeout_seconds=self.timeout_seconds,
            provider=self.name,
            operation="list_models",
        )
        models = data.get("models")
        if not isinstance(models, list):
            return []
        out: list[DiscoveredModel] = []
        for row in models:
            if not isinstance(row, dict):
                continue
            name = row.get("name") or row.get("model")
            if not isinstance(name, str) or not name.strip():
                continue
            details = row.get("details") if isinstance(row.get("details"), dict) else {}
            size = row.get("size")
            modified = row.get("modified_at") or row.get("modified")
            family = details.get("family") if isinstance(details.get("family"), str) else None
            quant = details.get("quantization_level")
            if not isinstance(quant, str):
                quant = None
            ctx = details.get("context_length") or row.get("context_length")
            context_window = int(ctx) if isinstance(ctx, (int, float)) else None
            out.append(
                DiscoveredModel(
                    model_id=name.strip(),
                    display_name=name.strip(),
                    provider=self.name,
                    context_window=context_window,
                    size_bytes=int(size) if isinstance(size, (int, float)) else None,
                    family=family,
                    quantization=quant,
                    modified_at=str(modified) if modified else None,
                    estimated_speed="local",
                    status="available",
                    capabilities=ModelCapabilities(
                        supports_streaming=True,
                        supports_json_output=True,
                        supports_vision="vision" in name.lower()
                        or (family or "").lower() in {"llava", "bakllava", "minicpm-v"},
                    ),
                    raw=dict(row),
                )
            )
        return out

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> EmbeddingResult:
        values = [t for t in texts if isinstance(t, str)]
        if not values:
            raise ProviderConfigurationError(
                "texts must contain at least one string",
                provider=self.name,
                operation="embed",
            )

        resolved_model = self._resolve_embedding_model(model)
        payload: dict[str, Any] = {
            "model": resolved_model,
            "input": values if len(values) > 1 else values[0],
        }
        if extra:
            for key, value in extra.items():
                if key in {"model", "input", "prompt"}:
                    continue
                payload[key] = value

        url = join_url(self.base_url, "/api/embed")

        def _once() -> dict[str, Any]:
            return post_json(
                url,
                payload,
                timeout_seconds=self.timeout_seconds,
                provider=self.name,
                operation="embed",
            )

        data = call_with_retry(
            "embed",
            _once,
            max_attempts=self.max_attempts,
            backoff_seconds=self.backoff_seconds,
            provider=self.name,
        )

        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or not vectors:
            legacy = data.get("embedding")
            if isinstance(legacy, list) and legacy and isinstance(legacy[0], (int, float)):
                vectors = [legacy]
            else:
                raise ProviderResponseError(
                    "Embed response missing embeddings array",
                    provider=self.name,
                    operation="embed",
                    details={"keys": list(data.keys())},
                )

        normalized: list[list[float]] = []
        for row in vectors:
            if not isinstance(row, list):
                raise ProviderResponseError(
                    "Embedding row is not a list",
                    provider=self.name,
                    operation="embed",
                )
            normalized.append([float(x) for x in row])

        if len(normalized) != len(values):
            raise ProviderResponseError(
                f"Expected {len(values)} embeddings, got {len(normalized)}",
                provider=self.name,
                operation="embed",
            )

        used_model = str(data.get("model") or resolved_model)
        usage = {
            "prompt_tokens": data.get("prompt_eval_count"),
            "total_duration_ns": data.get("total_duration"),
            "load_duration_ns": data.get("load_duration"),
        }
        return EmbeddingResult(
            vectors=normalized,
            model=used_model,
            usage={k: v for k, v in usage.items() if v is not None},
            raw=data,
        )


class OllamaChatProvider(ChatModelProvider):
    """``ChatModelProvider`` adapter over ``OllamaProvider``."""

    name = _PROVIDER_NAME

    def __init__(self, runtime: OllamaProvider) -> None:
        self._runtime = runtime

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        return self._runtime.chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            extra=extra,
        )

    def health_check(self) -> ProviderHealth:
        return self._runtime.health_check()

    def list_models(self) -> list[str]:
        return self._runtime.list_models()

    def discover_models(self):
        return self._runtime.discover_models()

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        return self._runtime.stream_chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            extra=extra,
        )


class OllamaEmbeddingProvider(EmbeddingProvider):
    """``EmbeddingProvider`` adapter over ``OllamaProvider``."""

    name = _PROVIDER_NAME

    def __init__(self, runtime: OllamaProvider) -> None:
        self._runtime = runtime

    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> EmbeddingResult:
        return self._runtime.embed(texts, model=model, extra=extra)
