"""Filter / subject helpers (moved from tools.py for the tools package)."""

from __future__ import annotations

import re
from typing import Any

_USER_ID_RE = re.compile(r"\b(?:user(?:_id)?|uid)\s*[:=]?\s*(-?\d+)\b", re.I)
_USERNAME_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{3,})\b")


def extract_subject_hints(question: str) -> dict[str, Any]:
    """Parse lightweight subject hints from the analyst question (no DB)."""
    hints: dict[str, Any] = {}
    uid = _USER_ID_RE.search(question or "")
    if uid:
        hints["user_id"] = int(uid.group(1))
    uname = _USERNAME_RE.search(question or "")
    if uname:
        hints["username"] = uname.group(1)
    return hints


def build_rag_filters(
    *,
    subject: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build vector-store metadata filters from session subject + extras."""
    filters: dict[str, Any] = {}
    subject = subject or {}
    if subject.get("user_id") is not None:
        filters["sender_id"] = subject["user_id"]
    if subject.get("chat_id") is not None:
        filters["chat_id"] = subject["chat_id"]
    if extra:
        filters.update({k: v for k, v in extra.items() if v is not None})
    return filters


def enrich_subject_identity(
    subject: dict[str, Any] | None,
    *,
    db: Any = None,
) -> dict[str, Any]:
    """Attach display_name / username fields onto a subject dict when possible."""
    subject = dict(subject or {})
    uid = subject.get("user_id")
    if uid is None:
        sid = subject.get("subject_id")
        stype = str(subject.get("subject_type") or "user")
        if sid is not None and stype in {"user", "personnel"}:
            raw = str(sid).strip()
            if raw.lstrip("-").isdigit():
                try:
                    uid = int(raw)
                except (TypeError, ValueError):
                    uid = None
    try:
        uid_int = int(uid) if uid is not None else None
    except (TypeError, ValueError):
        uid_int = None
    if uid_int is None:
        return subject

    from ai.rag.user_enrichment import UserIdentityEnricher

    user = UserIdentityEnricher(db).lookup_one(uid_int)
    if not user:
        return subject
    subject["user_id"] = uid_int
    subject["display_name"] = user.get("display_name")
    if user.get("username"):
        subject["username"] = str(user["username"]).lstrip("@")
    subject["first_name"] = user.get("first_name")
    subject["last_name"] = user.get("last_name")
    subject["risk_score"] = user.get("risk_score")
    subject["behavior_score"] = user.get("behavior_score")
    return subject
