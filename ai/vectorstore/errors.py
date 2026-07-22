"""Vector store errors."""

from __future__ import annotations

from typing import Any


class VectorStoreError(Exception):
    """Base error for vector store operations."""

    def __init__(
        self,
        message: str,
        *,
        backend: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.backend = backend
        self.details = details or {}


class VectorStoreConfigurationError(VectorStoreError):
    """Invalid configuration or missing collection/dimension."""


class VectorStoreNotFoundError(VectorStoreError):
    """Requested point(s) do not exist (e.g. update target missing)."""


class VectorStoreHTTPError(VectorStoreError):
    """Upstream vector DB returned an HTTP error."""
