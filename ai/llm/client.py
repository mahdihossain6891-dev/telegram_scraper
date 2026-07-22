"""Thin LLM client over ``ChatModelProvider`` with token budget enforcement."""

from __future__ import annotations

import logging
from typing import Any, Sequence

from ai.config import AISettings, get_ai_settings
from ai.providers.base import ChatCompletion, ChatMessage, ChatModelProvider
from ai.providers.errors import ProviderConfigurationError
from ai.providers.factory import ProviderFactory

logger = logging.getLogger("ai.llm.client")


class LLMClient:
    """Orchestrates chat completions with configurable max tokens."""

    def __init__(
        self,
        provider: ChatModelProvider,
        *,
        default_model: str = "",
        default_max_tokens: int | None = None,
        default_temperature: float | None = 0.1,
    ) -> None:
        self.provider = provider
        self.default_model = default_model.strip()
        self.default_max_tokens = default_max_tokens
        self.default_temperature = default_temperature

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        """Execute a chat completion via the configured provider."""
        if not messages:
            raise ProviderConfigurationError(
                "messages must not be empty",
                provider=getattr(self.provider, "name", None),
                operation="chat",
            )
        resolved_model = (model or self.default_model or "").strip() or None
        token_budget = max_tokens if max_tokens is not None else self.default_max_tokens
        temp = temperature if temperature is not None else self.default_temperature

        logger.info(
            "llm_complete_start",
            extra={
                "ai_provider": getattr(self.provider, "name", None),
                "ai_model": resolved_model,
                "ai_max_tokens": token_budget,
                "ai_message_count": len(messages),
            },
        )
        result = self.provider.complete(
            messages,
            model=resolved_model,
            max_tokens=token_budget,
            temperature=temp,
            extra=extra,
        )
        logger.info(
            "llm_complete_ok",
            extra={
                "ai_provider": getattr(self.provider, "name", None),
                "ai_model": result.model,
                "ai_completion_chars": len(result.content or ""),
            },
        )
        return result


def create_llm_client(
    settings: AISettings | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> LLMClient:
    """Build an LLM client, optionally overriding env provider/model (Control Center)."""
    cfg = settings or get_ai_settings()
    if not cfg.enabled:
        raise ProviderConfigurationError(
            "AI is disabled. Set AI_ENABLED=true.",
            operation="llm",
        )

    factory = ProviderFactory(cfg)
    configured = (cfg.chat_provider or "none").strip().lower()
    requested = (provider or configured or "none").strip().lower()
    override = bool(provider or model)

    if override:
        chat = factory.create_for_discovery(requested)
        resolved_model = (model or cfg.chat_model or "").strip()
        if not resolved_model:
            raise ProviderConfigurationError(
                f"Model is required for provider {requested!r}. "
                "Set AI_CHAT_MODEL or pass model in the request.",
                provider=requested,
                operation="llm",
            )
    else:
        chat = factory.create_chat_provider()
        resolved_model = (cfg.chat_model or "").strip()

    token_budget = (
        max_tokens
        if max_tokens is not None
        else (cfg.max_tokens if cfg.max_tokens > 0 else None)
    )
    temp = temperature if temperature is not None else 0.1

    return LLMClient(
        chat,
        default_model=resolved_model,
        default_max_tokens=token_budget,
        default_temperature=temp,
    )
