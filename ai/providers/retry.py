"""Retry helpers for provider HTTP calls."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

from ai.providers.errors import (
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

logger = logging.getLogger("ai.providers.retry")

T = TypeVar("T")

# Errors that are safe to retry.
_RETRYABLE = (
    ProviderTimeoutError,
    ProviderConnectionError,
    ProviderRateLimitError,
)


def is_retryable(exc: BaseException) -> bool:
    """Return True when ``exc`` should be retried."""
    if isinstance(exc, ProviderRateLimitError):
        return True
    if isinstance(exc, ProviderHTTPError) and exc.status_code in {408, 425, 500, 502, 503, 504}:
        return True
    return isinstance(exc, _RETRYABLE)


def call_with_retry(
    operation: str,
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    backoff_seconds: float = 0.5,
    provider: str | None = None,
) -> T:
    """Execute ``fn`` with exponential backoff + jitter on retryable errors.

    Args:
        operation: Short name for logs (e.g. ``chat``, ``embed``).
        fn: Zero-arg callable performing one attempt.
        max_attempts: Total attempts including the first.
        backoff_seconds: Base delay before the first retry.
        provider: Provider name for structured logs.
    """
    attempts = max(1, int(max_attempts))
    last_error: BaseException | None = None

    for attempt in range(1, attempts + 1):
        try:
            result = fn()
            if attempt > 1:
                logger.info(
                    "provider_retry_succeeded",
                    extra={
                        "ai_provider": provider,
                        "ai_operation": operation,
                        "ai_attempt": attempt,
                    },
                )
            return result
        except ProviderError as exc:
            last_error = exc
            if attempt >= attempts or not is_retryable(exc):
                logger.error(
                    "provider_call_failed",
                    extra={
                        "ai_provider": provider,
                        "ai_operation": operation,
                        "ai_attempt": attempt,
                        "ai_error": str(exc),
                        "ai_status": exc.status_code,
                    },
                )
                raise
            delay = backoff_seconds * (2 ** (attempt - 1))
            delay += random.uniform(0, backoff_seconds * 0.25)
            logger.warning(
                "provider_retry",
                extra={
                    "ai_provider": provider,
                    "ai_operation": operation,
                    "ai_attempt": attempt,
                    "ai_next_delay_seconds": round(delay, 3),
                    "ai_error": str(exc),
                    "ai_status": exc.status_code,
                },
            )
            time.sleep(delay)

    assert last_error is not None
    raise last_error
