"""OpenAI-compatible HTTP provider (shared by OpenRouter, LM Studio, generic).

Talks to ``/v1/chat/completions``, ``/v1/models``, and ``/v1/embeddings``.
Base URL and API key come from configuration — never hardcoded.
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

logger = logging.getLogger("ai.providers.openai_compatible")


def normalize_openai_base_url(url: str | None, *, default: str, provider: str) -> str:
    """Normalize to an OpenAI-compatible API root (ending without trailing slash)."""
    raw = (url or "").strip() or default
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ProviderConfigurationError(
            f"Invalid API base URL: {url!r}",
            provider=provider,
            operation="config",
        )
    path = (parsed.path or "").rstrip("/")
    # Accept bare host or host/v1
    if not path:
        return f"{parsed.scheme}://{parsed.netloc}/v1"
    if path.endswith("/v1"):
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


class OpenAICompatibleChatProvider(ChatModelProvider):
    """Chat backend for any OpenAI-compatible HTTP API."""

    name = "openai_compatible"

    def __init__(
        self,
        *,
        api_base_url: str = "",
        api_key: str = "",
        default_model: str = "",
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        default_max_tokens: int | None = None,
        default_base_url: str = "http://127.0.0.1:1234/v1",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
    ) -> None:
        if provider_name:
            self.name = provider_name
        self.api_base_url = normalize_openai_base_url(
            api_base_url,
            default=default_base_url,
            provider=self.name,
        )
        self.api_key = (api_key or "").strip()
        self.default_model = (default_model or "").strip()
        self.timeout_seconds = float(timeout_seconds)
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_seconds = float(backoff_seconds)
        self.default_max_tokens = default_max_tokens
        self.extra_headers = dict(extra_headers or {})

    def _headers(self) -> dict[str, str]:
        headers = dict(self.extra_headers)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _resolve_model(self, model: str | None) -> str:
        resolved = (model or self.default_model or "").strip()
        if not resolved:
            raise ProviderConfigurationError(
                "Chat model is not configured. Set AI_CHAT_MODEL or pass model=.",
                provider=self.name,
                operation="chat",
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
        resolved_model = self._resolve_model(model)
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        token_limit = max_tokens if max_tokens is not None else self.default_max_tokens
        if token_limit is not None:
            payload["max_tokens"] = int(token_limit)
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if extra:
            for key, value in extra.items():
                if key in {"model", "messages", "stream"}:
                    continue
                payload[key] = value

        url = join_url(self.api_base_url, "/chat/completions")

        def _once() -> dict[str, Any]:
            return post_json(
                url,
                payload,
                timeout_seconds=self.timeout_seconds,
                headers=self._headers(),
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

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderResponseError(
                "Chat response missing choices",
                provider=self.name,
                operation="chat",
                details={"keys": list(data.keys())},
            )
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else None
        content = ""
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            content = message["content"]
        elif isinstance(first.get("text"), str):
            content = first["text"]
        else:
            raise ProviderResponseError(
                "Chat response missing message content",
                provider=self.name,
                operation="chat",
            )

        usage_raw = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens"),
            "completion_tokens": usage_raw.get("completion_tokens"),
            "total_tokens": usage_raw.get("total_tokens"),
        }
        used_model = str(data.get("model") or resolved_model)
        return ChatCompletion(
            content=content,
            model=used_model,
            usage={k: v for k, v in usage.items() if v is not None},
            raw=data,
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
        resolved_model = self._resolve_model(model)
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        token_limit = max_tokens if max_tokens is not None else self.default_max_tokens
        if token_limit is not None:
            payload["max_tokens"] = int(token_limit)
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if extra:
            for key, value in extra.items():
                if key in {"model", "messages", "stream"}:
                    continue
                payload[key] = value

        url = join_url(self.api_base_url, "/chat/completions")
        for event in iter_sse_json_lines(
            url,
            payload,
            timeout_seconds=self.timeout_seconds,
            headers=self._headers(),
            provider=self.name,
            operation="stream_chat",
        ):
            choices = event.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            first = choices[0] if isinstance(choices[0], dict) else {}
            delta = first.get("delta") if isinstance(first, dict) else None
            if isinstance(delta, dict):
                chunk = delta.get("content")
                if isinstance(chunk, str) and chunk:
                    yield chunk

    def health_check(self) -> ProviderHealth:
        try:
            data = get_json(
                join_url(self.api_base_url, "/models"),
                timeout_seconds=min(self.timeout_seconds, 10.0),
                headers=self._headers(),
                provider=self.name,
                operation="health_check",
            )
            rows = data.get("data") if isinstance(data.get("data"), list) else []
            return ProviderHealth(
                ok=True,
                provider=self.name,
                detail="reachable",
                models_available=len(rows),
                raw={"base_url": self.api_base_url},
            )
        except Exception as exc:  # noqa: BLE001 — health never raises
            return ProviderHealth(
                ok=False,
                provider=self.name,
                detail=str(exc),
                raw={"base_url": self.api_base_url},
            )

    def list_models(self) -> list[str]:
        return [m.model_id for m in self.discover_models()]

    def discover_models(self) -> list:
        """Discover models from ``GET /models`` — provider-agnostic metadata."""
        from ai.providers.models import DiscoveredModel, ModelCapabilities

        data = get_json(
            join_url(self.api_base_url, "/models"),
            timeout_seconds=self.timeout_seconds,
            headers=self._headers(),
            provider=self.name,
            operation="list_models",
        )
        rows = data.get("data")
        if not isinstance(rows, list):
            return []
        out: list[DiscoveredModel] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            mid = row.get("id") or row.get("name")
            if not isinstance(mid, str) or not mid.strip():
                continue
            display = row.get("name") or row.get("display_name") or mid
            if not isinstance(display, str):
                display = mid
            ctx = (
                row.get("context_length")
                or row.get("context_window")
                or row.get("max_model_len")
                or row.get("max_context_length")
            )
            context_window = int(ctx) if isinstance(ctx, (int, float)) else None
            max_out = row.get("max_completion_tokens") or row.get("max_tokens")
            max_tokens = int(max_out) if isinstance(max_out, (int, float)) else None
            out.append(
                DiscoveredModel(
                    model_id=mid.strip(),
                    display_name=display.strip(),
                    provider=self.name,
                    context_window=context_window,
                    max_tokens=max_tokens,
                    status="available",
                    estimated_speed="local" if self.name in {"lmstudio"} else None,
                    capabilities=ModelCapabilities(
                        supports_streaming=True,
                        supports_json_output=True,
                        supports_vision=False,
                        supports_reasoning=False,
                        supports_tool_calling=False,
                    ),
                    raw=dict(row),
                )
            )
        return out


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Embedding backend for OpenAI-compatible ``/embeddings`` endpoints."""

    name = "openai_compatible"

    def __init__(
        self,
        *,
        api_base_url: str = "",
        api_key: str = "",
        default_model: str = "",
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        default_base_url: str = "http://127.0.0.1:1234/v1",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
    ) -> None:
        if provider_name:
            self.name = provider_name
        self.api_base_url = normalize_openai_base_url(
            api_base_url,
            default=default_base_url,
            provider=self.name,
        )
        self.api_key = (api_key or "").strip()
        self.default_model = (default_model or "").strip()
        self.timeout_seconds = float(timeout_seconds)
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_seconds = float(backoff_seconds)
        self.extra_headers = dict(extra_headers or {})

    def _headers(self) -> dict[str, str]:
        headers = dict(self.extra_headers)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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
        resolved = (model or self.default_model or "").strip()
        if not resolved:
            raise ProviderConfigurationError(
                "Embedding model is not configured. "
                "Set AI_EMBEDDING_MODEL or pass model=.",
                provider=self.name,
                operation="embed",
            )
        payload: dict[str, Any] = {"model": resolved, "input": values}
        if extra:
            for key, value in extra.items():
                if key in {"model", "input"}:
                    continue
                payload[key] = value

        url = join_url(self.api_base_url, "/embeddings")

        def _once() -> dict[str, Any]:
            return post_json(
                url,
                payload,
                timeout_seconds=self.timeout_seconds,
                headers=self._headers(),
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
        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            raise ProviderResponseError(
                "Embed response missing data array",
                provider=self.name,
                operation="embed",
                details={"keys": list(data.keys())},
            )
        # OpenAI returns objects with index + embedding; sort by index.
        ordered = sorted(
            (r for r in rows if isinstance(r, dict)),
            key=lambda r: int(r.get("index") or 0),
        )
        vectors: list[list[float]] = []
        for row in ordered:
            emb = row.get("embedding")
            if not isinstance(emb, list):
                raise ProviderResponseError(
                    "Embedding row missing embedding list",
                    provider=self.name,
                    operation="embed",
                )
            vectors.append([float(x) for x in emb])
        if len(vectors) != len(values):
            raise ProviderResponseError(
                f"Expected {len(values)} embeddings, got {len(vectors)}",
                provider=self.name,
                operation="embed",
            )
        usage_raw = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        usage = {
            "prompt_tokens": usage_raw.get("prompt_tokens"),
            "total_tokens": usage_raw.get("total_tokens"),
        }
        return EmbeddingResult(
            vectors=vectors,
            model=str(data.get("model") or resolved),
            usage={k: v for k, v in usage.items() if v is not None},
            raw=data,
        )
