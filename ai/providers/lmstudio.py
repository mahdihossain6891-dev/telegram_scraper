"""LM Studio provider — OpenAI-compatible local server."""

from __future__ import annotations

from ai.providers.openai_compatible import (
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
)

_DEFAULT_BASE = "http://127.0.0.1:1234/v1"


class LMStudioChatProvider(OpenAICompatibleChatProvider):
    """Chat provider for LM Studio's local OpenAI-compatible server."""

    name = "lmstudio"

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
    ) -> None:
        super().__init__(
            api_base_url=api_base_url,
            api_key=api_key or "lm-studio",
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            default_max_tokens=default_max_tokens,
            default_base_url=_DEFAULT_BASE,
            provider_name="lmstudio",
        )


class LMStudioEmbeddingProvider(OpenAICompatibleEmbeddingProvider):
    """Embedding provider for LM Studio's local OpenAI-compatible server."""

    name = "lmstudio"

    def __init__(
        self,
        *,
        api_base_url: str = "",
        api_key: str = "",
        default_model: str = "",
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        super().__init__(
            api_base_url=api_base_url,
            api_key=api_key or "lm-studio",
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            default_base_url=_DEFAULT_BASE,
            provider_name="lmstudio",
        )
