"""Provider factory — selects implementations from ``AI_*`` settings.

Sebastian and application code should obtain providers only through
``ProviderFactory``. Do not import Ollama / OpenRouter / LM Studio clients
outside this package.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from typing import Any

from ai.config import AISettings, get_ai_settings
from ai.providers.base import (
    ChatCompletion,
    ChatMessage,
    ChatModelProvider,
    EmbeddingProvider,
    ProviderHealth,
)
from ai.providers.errors import ProviderConfigurationError, ProviderError
from ai.providers.lmstudio import LMStudioChatProvider, LMStudioEmbeddingProvider
from ai.providers.ollama import (
    OllamaChatProvider,
    OllamaEmbeddingProvider,
    OllamaProvider,
)
from ai.providers.openai_compatible import (
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
)
from ai.providers.openrouter import OpenRouterChatProvider, OpenRouterEmbeddingProvider

logger = logging.getLogger("ai.providers.factory")

# ``local`` remains an alias for Ollama for existing deployments.
_CHAT_ALIASES = {"local": "ollama"}
_EMBED_ALIASES = {"local": "ollama"}


class DisabledChatProvider(ChatModelProvider):
    """Raised when chat is disabled or unset."""

    name = "none"

    def chat(self, messages, *, model=None, max_tokens=None, temperature=None, extra=None):
        raise ProviderConfigurationError(
            "Chat provider is disabled (AI_CHAT_PROVIDER=none or AI_ENABLED=false).",
            provider=self.name,
            operation="chat",
        )

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(ok=False, provider=self.name, detail="disabled")

    def list_models(self) -> list[str]:
        return []

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        raise ProviderConfigurationError(
            "Chat provider is disabled (AI_CHAT_PROVIDER=none or AI_ENABLED=false).",
            provider=self.name,
            operation="stream_chat",
        )


class DisabledEmbeddingProvider(EmbeddingProvider):
    """Raised when embeddings are disabled or unset."""

    name = "none"

    def embed(self, texts, *, model=None, extra=None):
        raise ProviderConfigurationError(
            "Embedding provider is disabled "
            "(AI_EMBEDDING_PROVIDER=none or AI_ENABLED=false).",
            provider=self.name,
            operation="embed",
        )


class ProviderFactory:
    """Build chat/embedding providers from ``AISettings``.

    Primary entry points:
    - ``create(provider_name)`` — chat provider by name
    - ``create_chat_provider()`` — chat provider from ``AI_CHAT_PROVIDER``
    - ``create_embedding_provider()`` — embedding provider from settings
    """

    def __init__(self, settings: AISettings | None = None) -> None:
        self.settings = settings or get_ai_settings()
        self._ollama_runtime: OllamaProvider | None = None

    def create(self, provider_name: str | None = None) -> ChatModelProvider:
        """Return a chat provider instance for ``provider_name``.

        When ``provider_name`` is omitted, uses ``AI_CHAT_PROVIDER``.
        Sebastian should only call this factory — never construct providers.
        """
        return self._build_chat(provider_name, require_model=True)

    def create_for_discovery(self, provider_name: str | None = None) -> ChatModelProvider:
        """Return a chat provider for listing models / health checks.

        Does **not** require ``AI_CHAT_MODEL``. Uses the configured base URL
        only when discovering the currently selected provider; otherwise
        provider defaults apply so catalogs stay independent.
        """
        return self._build_chat(provider_name, require_model=False)

    def list_models(self, provider_name: str | None = None) -> list[str]:
        """Transparent ``list_models`` via the discovery-capable provider."""
        return self.create_for_discovery(provider_name).list_models()

    def health_check(self, provider_name: str | None = None) -> ProviderHealth:
        """Transparent ``health_check`` via the discovery-capable provider."""
        return self.create_for_discovery(provider_name).health_check()

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra: dict[str, Any] | None = None,
        provider_name: str | None = None,
    ) -> ChatCompletion:
        """Transparent ``chat`` via the configured (or named) provider."""
        return self.create(provider_name).chat(
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
        provider_name: str | None = None,
    ) -> Iterator[str]:
        """Transparent ``stream_chat`` via the configured (or named) provider."""
        return self.create(provider_name).stream_chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            extra=extra,
        )

    def create_chat_provider(self) -> ChatModelProvider:
        """Return the configured chat provider interface."""
        return self.create(self.settings.chat_provider)

    def _build_chat(
        self,
        provider_name: str | None,
        *,
        require_model: bool,
    ) -> ChatModelProvider:
        cfg = self.settings
        name = (provider_name or cfg.chat_provider or "none").strip().lower()
        name = _CHAT_ALIASES.get(name, name)

        if not cfg.enabled or name == "none":
            logger.info(
                "chat_provider_disabled",
                extra={"ai_provider": "none", "ai_enabled": cfg.enabled},
            )
            return DisabledChatProvider()

        if require_model:
            self._require_chat_model(name)

        base_url = self._discovery_base_url(name)

        if name == "ollama":
            return self._create_ollama_chat(base_url=base_url, require_model=require_model)
        if name == "openrouter":
            return self._create_openrouter_chat(
                base_url=base_url, require_model=require_model
            )
        if name == "lmstudio":
            return self._create_lmstudio_chat(
                base_url=base_url, require_model=require_model
            )
        if name == "openai_compatible":
            return self._create_openai_compatible_chat(
                base_url=base_url, require_model=require_model
            )

        raise ProviderConfigurationError(
            f"Unsupported AI_CHAT_PROVIDER: {provider_name or cfg.chat_provider!r}. "
            "Expected one of: ollama, openrouter, lmstudio, openai_compatible, local, none.",
            provider=name,
            operation="factory",
        )

    def _configured_chat_name(self) -> str:
        raw = (self.settings.chat_provider or "none").strip().lower()
        return _CHAT_ALIASES.get(raw, raw)

    def _discovery_base_url(self, name: str) -> str:
        """Use configured base URL only for the selected provider."""
        cfg = self.settings
        if name == self._configured_chat_name() and cfg.api_base_url.strip():
            return cfg.api_base_url.strip()
        return ""

    def create_embedding_provider(self) -> EmbeddingProvider:
        """Return the configured embedding provider interface."""
        cfg = self.settings
        name = (cfg.embedding_provider or "none").strip().lower()
        name = _EMBED_ALIASES.get(name, name)

        if not cfg.enabled or name == "none":
            logger.info(
                "embedding_provider_disabled",
                extra={"ai_provider": "none", "ai_enabled": cfg.enabled},
            )
            return DisabledEmbeddingProvider()

        if name == "ollama":
            return self._create_ollama_embedding()
        if name == "openrouter":
            return self._create_openrouter_embedding()
        if name == "lmstudio":
            return self._create_lmstudio_embedding()
        if name == "openai_compatible":
            return self._create_openai_compatible_embedding()

        raise ProviderConfigurationError(
            f"Unsupported AI_EMBEDDING_PROVIDER: {cfg.embedding_provider!r}. "
            "Expected one of: ollama, openrouter, lmstudio, openai_compatible, local, none.",
            provider=name,
            operation="factory",
        )

    def _require_chat_model(self, provider: str) -> None:
        if not self.settings.chat_model.strip():
            raise ProviderConfigurationError(
                f"AI_CHAT_PROVIDER={provider} requires AI_CHAT_MODEL to be set.",
                provider=provider,
                operation="factory",
            )

    def _require_embedding_model(self, provider: str) -> None:
        if not self.settings.embedding_model.strip():
            raise ProviderConfigurationError(
                f"AI_EMBEDDING_PROVIDER={provider} requires AI_EMBEDDING_MODEL to be set.",
                provider=provider,
                operation="factory",
            )

    def _ollama(self) -> OllamaProvider:
        if self._ollama_runtime is None:
            cfg = self.settings
            self._ollama_runtime = OllamaProvider(
                base_url=cfg.ollama_base_url or cfg.api_base_url,
                chat_model=cfg.chat_model,
                embedding_model=cfg.embedding_model,
                timeout_seconds=cfg.request_timeout_seconds,
                max_attempts=cfg.retry_max_attempts,
                backoff_seconds=cfg.retry_backoff_seconds,
                default_max_tokens=cfg.max_tokens if cfg.max_tokens > 0 else None,
            )
            logger.info(
                "ollama_provider_created",
                extra={
                    "ai_provider": "ollama",
                    "ai_base_url": self._ollama_runtime.base_url,
                    "ai_timeout_seconds": cfg.request_timeout_seconds,
                },
            )
        return self._ollama_runtime

    def _create_ollama_chat(
        self,
        *,
        base_url: str = "",
        require_model: bool = True,
    ) -> ChatModelProvider:
        if require_model:
            self._require_chat_model("ollama")
        logger.info("chat_provider_selected", extra={"ai_provider": "ollama"})
        if not require_model:
            cfg = self.settings
            runtime = OllamaProvider(
                base_url=base_url,
                chat_model="",
                embedding_model=cfg.embedding_model,
                timeout_seconds=cfg.request_timeout_seconds,
                max_attempts=cfg.retry_max_attempts,
                backoff_seconds=cfg.retry_backoff_seconds,
                default_max_tokens=cfg.max_tokens if cfg.max_tokens > 0 else None,
            )
            return OllamaChatProvider(runtime)
        return OllamaChatProvider(self._ollama())

    def _create_ollama_embedding(self) -> EmbeddingProvider:
        self._require_embedding_model("ollama")
        logger.info("embedding_provider_selected", extra={"ai_provider": "ollama"})
        return OllamaEmbeddingProvider(self._ollama())

    def _create_openrouter_chat(
        self,
        *,
        base_url: str = "",
        require_model: bool = True,
    ) -> ChatModelProvider:
        if require_model:
            self._require_chat_model("openrouter")
        cfg = self.settings
        if not cfg.api_key.strip():
            raise ProviderConfigurationError(
                "OpenRouter requires AI_API_KEY (or OPENROUTER_API_KEY) in .env. "
                "Create a key at https://openrouter.ai/keys, add it to the project "
                ".env file, then use Refresh in Sébastien Settings or restart the API.",
                provider="openrouter",
                operation="factory",
            )
        from ai.config import looks_like_openrouter_api_key

        if not looks_like_openrouter_api_key(cfg.api_key):
            raise ProviderConfigurationError(
                "AI_API_KEY does not look like an OpenRouter key (expected sk-or-v1-...). "
                "Copy the full key from https://openrouter.ai/keys — not a hash or other token.",
                provider="openrouter",
                operation="factory",
            )
        logger.info("chat_provider_selected", extra={"ai_provider": "openrouter"})
        return OpenRouterChatProvider(
            api_base_url=base_url,
            api_key=cfg.api_key,
            default_model=cfg.chat_model if require_model else "",
            timeout_seconds=cfg.request_timeout_seconds,
            max_attempts=cfg.retry_max_attempts,
            backoff_seconds=cfg.retry_backoff_seconds,
            default_max_tokens=cfg.max_tokens if cfg.max_tokens > 0 else None,
            http_referer=cfg.http_referer,
            app_title=cfg.app_title,
        )

    def _create_openrouter_embedding(self) -> EmbeddingProvider:
        self._require_embedding_model("openrouter")
        cfg = self.settings
        if not cfg.api_key.strip():
            raise ProviderConfigurationError(
                "OpenRouter embeddings require AI_API_KEY (or OPENROUTER_API_KEY) in .env.",
                provider="openrouter",
                operation="factory",
            )
        from ai.config import looks_like_openrouter_api_key

        if not looks_like_openrouter_api_key(cfg.api_key):
            raise ProviderConfigurationError(
                "AI_API_KEY does not look like an OpenRouter key (expected sk-or-v1-...). "
                "Copy the full key from https://openrouter.ai/keys.",
                provider="openrouter",
                operation="factory",
            )
        logger.info("embedding_provider_selected", extra={"ai_provider": "openrouter"})
        return OpenRouterEmbeddingProvider(
            api_base_url=cfg.api_base_url,
            api_key=cfg.api_key,
            default_model=cfg.embedding_model,
            timeout_seconds=cfg.request_timeout_seconds,
            max_attempts=cfg.retry_max_attempts,
            backoff_seconds=cfg.retry_backoff_seconds,
            http_referer=cfg.http_referer,
            app_title=cfg.app_title,
        )

    def _create_lmstudio_chat(
        self,
        *,
        base_url: str = "",
        require_model: bool = True,
    ) -> ChatModelProvider:
        if require_model:
            self._require_chat_model("lmstudio")
        cfg = self.settings
        logger.info("chat_provider_selected", extra={"ai_provider": "lmstudio"})
        return LMStudioChatProvider(
            api_base_url=base_url,
            api_key=cfg.api_key,
            default_model=cfg.chat_model if require_model else "",
            timeout_seconds=cfg.request_timeout_seconds,
            max_attempts=cfg.retry_max_attempts,
            backoff_seconds=cfg.retry_backoff_seconds,
            default_max_tokens=cfg.max_tokens if cfg.max_tokens > 0 else None,
        )

    def _create_lmstudio_embedding(self) -> EmbeddingProvider:
        self._require_embedding_model("lmstudio")
        cfg = self.settings
        logger.info("embedding_provider_selected", extra={"ai_provider": "lmstudio"})
        return LMStudioEmbeddingProvider(
            api_base_url=cfg.api_base_url,
            api_key=cfg.api_key,
            default_model=cfg.embedding_model,
            timeout_seconds=cfg.request_timeout_seconds,
            max_attempts=cfg.retry_max_attempts,
            backoff_seconds=cfg.retry_backoff_seconds,
        )

    def _create_openai_compatible_chat(
        self,
        *,
        base_url: str = "",
        require_model: bool = True,
    ) -> ChatModelProvider:
        if require_model:
            self._require_chat_model("openai_compatible")
        cfg = self.settings
        resolved_base = base_url or cfg.api_base_url
        if not resolved_base.strip():
            raise ProviderConfigurationError(
                "AI_CHAT_PROVIDER=openai_compatible requires AI_API_BASE_URL.",
                provider="openai_compatible",
                operation="factory",
            )
        logger.info(
            "chat_provider_selected",
            extra={"ai_provider": "openai_compatible"},
        )
        return OpenAICompatibleChatProvider(
            api_base_url=resolved_base,
            api_key=cfg.api_key,
            default_model=cfg.chat_model if require_model else "",
            timeout_seconds=cfg.request_timeout_seconds,
            max_attempts=cfg.retry_max_attempts,
            backoff_seconds=cfg.retry_backoff_seconds,
            default_max_tokens=cfg.max_tokens if cfg.max_tokens > 0 else None,
            default_base_url=resolved_base,
        )

    def _create_openai_compatible_embedding(self) -> EmbeddingProvider:
        self._require_embedding_model("openai_compatible")
        cfg = self.settings
        if not cfg.api_base_url.strip():
            raise ProviderConfigurationError(
                "AI_EMBEDDING_PROVIDER=openai_compatible requires AI_API_BASE_URL.",
                provider="openai_compatible",
                operation="factory",
            )
        logger.info(
            "embedding_provider_selected",
            extra={"ai_provider": "openai_compatible"},
        )
        return OpenAICompatibleEmbeddingProvider(
            api_base_url=cfg.api_base_url,
            api_key=cfg.api_key,
            default_model=cfg.embedding_model,
            timeout_seconds=cfg.request_timeout_seconds,
            max_attempts=cfg.retry_max_attempts,
            backoff_seconds=cfg.retry_backoff_seconds,
            default_base_url=cfg.api_base_url,
        )

    def create_local_provider(self) -> OllamaProvider:
        """Return the shared Ollama runtime (``local`` / ``ollama``).

        Prefer ``create_chat_provider`` / ``create`` in application code.
        """
        name = _CHAT_ALIASES.get(self.settings.chat_provider, self.settings.chat_provider)
        embed = _EMBED_ALIASES.get(
            self.settings.embedding_provider, self.settings.embedding_provider
        )
        if name != "ollama" and embed != "ollama":
            raise ProviderConfigurationError(
                "Local/Ollama runtime requested but neither chat nor embedding "
                "provider is set to 'ollama' or 'local'.",
                provider="ollama",
                operation="factory",
            )
        return self._ollama()


def create_chat_provider(settings: AISettings | None = None) -> ChatModelProvider:
    """Convenience wrapper around ``ProviderFactory.create_chat_provider``."""
    return ProviderFactory(settings).create_chat_provider()


def create_embedding_provider(
    settings: AISettings | None = None,
) -> EmbeddingProvider:
    """Convenience wrapper around ``ProviderFactory.create_embedding_provider``."""
    return ProviderFactory(settings).create_embedding_provider()


__all__ = [
    "DisabledChatProvider",
    "DisabledEmbeddingProvider",
    "ProviderError",
    "ProviderFactory",
    "create_chat_provider",
    "create_embedding_provider",
]
