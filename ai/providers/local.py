"""Backward-compatible local provider aliases.

``AI_CHAT_PROVIDER=local`` remains supported and maps to Ollama.
Prefer importing from ``ai.providers.ollama`` for new code.
"""

from __future__ import annotations

from ai.providers.ollama import (
    OllamaChatProvider as LocalChatProvider,
    OllamaEmbeddingProvider as LocalEmbeddingProvider,
    OllamaProvider as LocalProvider,
    normalize_ollama_base_url,
)

__all__ = [
    "LocalChatProvider",
    "LocalEmbeddingProvider",
    "LocalProvider",
    "normalize_ollama_base_url",
]
