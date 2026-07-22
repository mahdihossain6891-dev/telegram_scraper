"""Internal HTTP JSON transport for providers (stdlib only).

Not part of the public provider API — other packages should use
``ChatModelProvider`` / ``EmbeddingProvider`` instead.
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urljoin

from ai.providers.errors import (
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
)

logger = logging.getLogger("ai.providers.transport")


def join_url(base_url: str, path: str) -> str:
    """Join ``base_url`` and ``path`` with a single slash boundary."""
    base = base_url.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def _raise_transport_error(
    exc: BaseException,
    *,
    url: str,
    timeout_seconds: float,
    provider: str | None,
    operation: str | None,
) -> None:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        raise ProviderTimeoutError(
            f"Request timed out after {timeout_seconds}s",
            provider=provider,
            operation=operation,
            details={"url": url},
        ) from exc
    if isinstance(exc, urllib.error.HTTPError):
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — best-effort body capture
            error_body = ""
        details = {"url": url, "body": error_body[:2000]}
        if exc.code == 429:
            raise ProviderRateLimitError(
                "Upstream rate limited the request",
                provider=provider,
                operation=operation,
                status_code=429,
                details=details,
            ) from exc
        message = f"Upstream HTTP {exc.code}"
        if exc.code == 401 and provider == "openrouter":
            message = (
                "OpenRouter rejected the API key (HTTP 401). "
                "Use a key starting with sk-or-v1- from https://openrouter.ai/keys"
            )
        raise ProviderHTTPError(
            message,
            provider=provider,
            operation=operation,
            status_code=exc.code,
            details=details,
        ) from exc
    if isinstance(exc, urllib.error.URLError):
        raise ProviderConnectionError(
            f"Could not connect to upstream: {exc.reason!r}",
            provider=provider,
            operation=operation,
            details={"url": url},
        ) from exc
    if isinstance(exc, OSError):
        raise ProviderConnectionError(
            f"Network error talking to upstream: {exc}",
            provider=provider,
            operation=operation,
            details={"url": url},
        ) from exc
    raise ProviderConnectionError(
        f"Unexpected transport error: {exc}",
        provider=provider,
        operation=operation,
        details={"url": url},
    ) from exc


def _parse_json_object(
    raw: str,
    *,
    url: str,
    status: int,
    provider: str | None,
    operation: str | None,
) -> dict[str, Any]:
    if not raw.strip():
        raise ProviderResponseError(
            "Upstream returned an empty body",
            provider=provider,
            operation=operation,
            status_code=status,
            details={"url": url},
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderResponseError(
            "Upstream returned invalid JSON",
            provider=provider,
            operation=operation,
            status_code=status,
            details={"url": url, "body": raw[:500]},
        ) from exc
    if not isinstance(parsed, dict):
        raise ProviderResponseError(
            "Upstream JSON was not an object",
            provider=provider,
            operation=operation,
            status_code=status,
            details={"url": url},
        )
    return parsed


def get_json(
    url: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
    provider: str | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    """GET JSON and parse a JSON object response."""
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    request = urllib.request.Request(url, headers=req_headers, method="GET")
    logger.debug(
        "provider_http_request",
        extra={
            "ai_provider": provider,
            "ai_operation": operation,
            "ai_url": url,
            "ai_timeout_seconds": timeout_seconds,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            status = getattr(response, "status", 200)
    except Exception as exc:  # noqa: BLE001 — mapped below
        _raise_transport_error(
            exc,
            url=url,
            timeout_seconds=timeout_seconds,
            provider=provider,
            operation=operation,
        )
        raise  # pragma: no cover
    parsed = _parse_json_object(
        raw, url=url, status=status, provider=provider, operation=operation
    )
    logger.debug(
        "provider_http_response",
        extra={
            "ai_provider": provider,
            "ai_operation": operation,
            "ai_url": url,
            "ai_status": status,
        },
    )
    return parsed


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
    provider: str | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    """POST JSON and parse a JSON object response.

    Raises:
        ProviderTimeoutError: On socket/read timeouts.
        ProviderConnectionError: On connection failures.
        ProviderRateLimitError: On HTTP 429.
        ProviderHTTPError: On other non-2xx responses.
        ProviderResponseError: When the body is not a JSON object.
    """
    body = json.dumps(payload).encode("utf-8")
    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if headers:
        req_headers.update(headers)

    request = urllib.request.Request(
        url,
        data=body,
        headers=req_headers,
        method="POST",
    )

    logger.debug(
        "provider_http_request",
        extra={
            "ai_provider": provider,
            "ai_operation": operation,
            "ai_url": url,
            "ai_timeout_seconds": timeout_seconds,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            status = getattr(response, "status", 200)
    except Exception as exc:  # noqa: BLE001 — mapped below
        _raise_transport_error(
            exc,
            url=url,
            timeout_seconds=timeout_seconds,
            provider=provider,
            operation=operation,
        )
        raise  # pragma: no cover

    parsed = _parse_json_object(
        raw, url=url, status=status, provider=provider, operation=operation
    )
    logger.debug(
        "provider_http_response",
        extra={
            "ai_provider": provider,
            "ai_operation": operation,
            "ai_url": url,
            "ai_status": status,
        },
    )
    return parsed


def iter_sse_json_lines(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
    provider: str | None = None,
    operation: str | None = None,
):
    """POST JSON and yield parsed JSON objects from SSE ``data:`` lines."""
    body = json.dumps(payload).encode("utf-8")
    req_headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
    }
    if headers:
        req_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=body,
        headers=req_headers,
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request, timeout=timeout_seconds)
    except Exception as exc:  # noqa: BLE001 — mapped below
        _raise_transport_error(
            exc,
            url=url,
            timeout_seconds=timeout_seconds,
            provider=provider,
            operation=operation,
        )
        raise  # pragma: no cover

    with response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if line.startswith("data:"):
                data = line[5:].strip()
            else:
                data = line
            if data in {"[DONE]", "DONE"}:
                break
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                yield parsed
