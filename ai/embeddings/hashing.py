"""Content hashing for embedding deduplication."""

from __future__ import annotations

import hashlib
import re


_WHITESPACE = re.compile(r"\s+")


def normalize_for_hash(text: str) -> str:
    """Normalize text before hashing (stable across minor whitespace noise)."""
    return _WHITESPACE.sub(" ", (text or "").strip()).lower()


def content_hash(text: str, *, embedding_model: str = "") -> str:
    """Return a SHA-256 hex digest for ``text`` (and optional model id).

    Including ``embedding_model`` keeps vectors from different models distinct
    even when the source text is identical.
    """
    payload = f"{embedding_model}\n{normalize_for_hash(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
