"""Metadata filter helpers shared by vector backends."""

from __future__ import annotations

from typing import Any


def normalize_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    """Return a shallow copy of equality filters (None → empty)."""
    if not filters:
        return {}
    return {str(k): v for k, v in filters.items() if v is not None}


def payload_matches(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Return True when ``payload`` satisfies all equality filters.

    Nested keys may be expressed with dotted paths, e.g. ``metadata.chat_id``.
    """
    if not filters:
        return True
    for key, expected in filters.items():
        actual = _dig(payload, key)
        if actual != expected:
            return False
    return True


def _dig(payload: dict[str, Any], key: str) -> Any:
    if key in payload:
        return payload[key]
    if "." not in key:
        return None
    current: Any = payload
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
