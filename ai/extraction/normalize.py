"""Normalization helpers for entity deduplication."""

from __future__ import annotations

import re


def normalize_entity_value(entity_type: str, value: str) -> str:
    """Return a stable comparison key for merge / unique indexes."""
    raw = (value or "").strip()
    etype = (entity_type or "").strip().lower()
    if not raw:
        return ""

    if etype in {"phone"}:
        digits = re.sub(r"\D+", "", raw)
        return digits

    if etype in {"email", "url"}:
        return raw.lower().rstrip("/")

    if etype in {"username", "mention"}:
        return raw.lower().lstrip("@")

    if etype == "wallet":
        return raw.strip()

    if etype in {"organization", "location", "person"}:
        return re.sub(r"\s+", " ", raw).strip().lower()

    return re.sub(r"\s+", " ", raw).strip().lower()
