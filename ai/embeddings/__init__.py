"""Embedding service package — chunk, hash-dedup, batch embed, persist."""

from __future__ import annotations

from .chunking import ChunkingService
from .hashing import content_hash, normalize_for_hash
from .message_source import FlaggedMessageSource
from .repository import EmbeddingRepository
from .service import EmbeddingService

__all__ = [
    "ChunkingService",
    "EmbeddingRepository",
    "EmbeddingService",
    "FlaggedMessageSource",
    "content_hash",
    "normalize_for_hash",
]
