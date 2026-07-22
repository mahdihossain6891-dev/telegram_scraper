"""Abstract provider interfaces for chat and embeddings.

Concrete adapters return normalized ``ChatCompletion`` / ``EmbeddingResult``
values. Application code must depend on these interfaces (via
``ProviderFactory``), never on a specific runtime such as Ollama.

Sebastian and the rest of the ``ai`` package call providers only through
``ProviderFactory`` — they never know which backend is active.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChatMessage:
    """Single chat turn."""

    role: str
    content: str


@dataclass(slots=True)
class ChatCompletion:
    """Normalized chat completion result."""

    content: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingResult:
    """Normalized embedding batch result."""

    vectors: list[list[float]]
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProviderHealth:
    """Normalized provider health payload."""

    ok: bool
    provider: str
    detail: str = ""
    models_available: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "detail": self.detail,
            "models_available": self.models_available,
            "raw": dict(self.raw),
        }


class ChatModelProvider(ABC):
    """Interface for chat / completion backends.

    Required surface for multi-provider support:
    ``chat``, ``health_check``, ``list_models``, ``stream_chat``.

    ``complete`` remains as a compatibility alias used by ``LLMClient``.
    """

    name: str = "base"

    @abstractmethod
    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        """Return a non-streaming chat completion."""

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        """Compatibility alias — delegates to ``chat``.

        Existing callers (LLMClient, RAG, reports) keep working unchanged.
        """
        return self.chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            extra=extra,
        )

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Probe upstream availability without generating tokens."""

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return available model identifiers from the upstream."""

    @abstractmethod
    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        """Yield incremental content chunks from a streaming chat request."""


class EmbeddingProvider(ABC):
    """Interface for text embedding backends."""

    name: str = "base"

    @abstractmethod
    def embed(
        self,
        texts: Sequence[str],
        *,
        model: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> EmbeddingResult:
        """Embed ``texts`` into vectors.

        ``model`` overrides the provider default when provided. Providers must
        not invent a hardcoded model name when neither argument nor config
        supplies one.
        """
