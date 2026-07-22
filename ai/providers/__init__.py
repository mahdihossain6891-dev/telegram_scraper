"""Swappable model provider adapters.

Public surface for the rest of the ``ai`` package:

- Interfaces: ``ChatModelProvider``, ``EmbeddingProvider``
- Factory: ``ProviderFactory``, ``create_chat_provider``, ``create_embedding_provider``
- Errors: ``ProviderError`` and subclasses

Do not import ``transport`` or provider HTTP details outside this package.
Sebastian must obtain providers only via ``ProviderFactory``.
"""

from __future__ import annotations

from .base import (
    ChatCompletion,
    ChatMessage,
    ChatModelProvider,
    EmbeddingProvider,
    EmbeddingResult,
    ProviderHealth,
)
from .errors import (
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from .factory import (
    ProviderFactory,
    create_chat_provider,
    create_embedding_provider,
)
from .local import LocalProvider
from .ollama import OllamaProvider

__all__ = [
    "ChatCompletion",
    "ChatMessage",
    "ChatModelProvider",
    "EmbeddingProvider",
    "EmbeddingResult",
    "LocalProvider",
    "OllamaProvider",
    "ProviderConfigurationError",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderFactory",
    "ProviderHTTPError",
    "ProviderHealth",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "create_chat_provider",
    "create_embedding_provider",
]
