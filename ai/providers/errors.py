"""Centralized provider error types.

Callers outside ``ai.providers`` should catch ``ProviderError`` (or subclasses)
rather than Ollama/HTTP-specific exceptions.
"""

from __future__ import annotations

from typing import Any


class ProviderError(Exception):
    """Base error for all model provider failures."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        operation: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.operation = operation
        self.status_code = status_code
        self.details = details or {}

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.provider:
            parts.append(f"provider={self.provider}")
        if self.operation:
            parts.append(f"operation={self.operation}")
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        return " | ".join(parts)


class ProviderConfigurationError(ProviderError):
    """Invalid or incomplete provider configuration (e.g. missing model)."""


class ProviderTimeoutError(ProviderError):
    """Upstream request exceeded the configured timeout."""


class ProviderConnectionError(ProviderError):
    """Could not connect to the upstream provider."""


class ProviderHTTPError(ProviderError):
    """Upstream returned a non-success HTTP status."""


class ProviderResponseError(ProviderError):
    """Upstream response was malformed or missing required fields."""


class ProviderRateLimitError(ProviderHTTPError):
    """Upstream signaled rate limiting (HTTP 429)."""
