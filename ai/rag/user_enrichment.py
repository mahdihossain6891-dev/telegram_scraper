"""Centralized Telegram user identity enrichment for AI / RAG.

All AI features (query, investigate, chat, summary, reports) should resolve
users through this module so the LLM never sees bare IDs when better names
exist. Mongo access stays inside the AI package boundary.
"""

from __future__ import annotations

import logging
from typing import Any

from pymongo.database import Database as MongoDatabase

logger = logging.getLogger("ai.rag.user_enrichment")

# Metadata key attached to every EvidenceItem after hydration.
USER_META_KEY = "sender_user"


def normalize_username(username: str | None) -> str | None:
    if not username:
        return None
    cleaned = str(username).strip().lstrip("@")
    return cleaned or None


def format_username(username: str | None) -> str | None:
    cleaned = normalize_username(username)
    return f"@{cleaned}" if cleaned else None


def build_display_name(
    *,
    display_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    username: str | None = None,
    user_id: int | None = None,
) -> str:
    """Human-readable label with analyst-friendly fallbacks.

    Priority:
      explicit display_name → first+last → first → @username → Unknown User (User ID: …)
    """
    explicit = (display_name or "").strip()
    if explicit:
        return explicit

    first = (first_name or "").strip()
    last = (last_name or "").strip()
    if first and last:
        return f"{first} {last}"
    if first:
        return first
    if last:
        return last

    handle = format_username(username)
    if handle:
        return handle

    if user_id is not None:
        return f"Unknown User (User ID: {user_id})"
    return "Unknown User"


def format_user_bullet(user: dict[str, Any], *, similarity: float | None = None) -> str:
    """One analyst-facing bullet for connected / related users lists."""
    display = str(user.get("display_name") or "Unknown User")
    handle = format_username(user.get("username"))
    if handle and handle.lstrip("@").lower() not in display.lower():
        headline = f"{display} ({handle})"
    elif handle and display.startswith("@"):
        headline = display
    else:
        headline = display if not handle else f"{display} ({handle})"

    risk = _risk_label(user.get("risk_level"), user.get("risk_score"))
    lines = [f"• {headline}", risk]
    behavior = user.get("behavior_score")
    if behavior is not None:
        try:
            lines.append(f"Behavior Score: {int(behavior)}")
        except (TypeError, ValueError):
            lines.append(f"Behavior Score: {behavior}")
    if similarity is not None:
        try:
            lines.append(f"Similarity: {float(similarity):.2f}")
        except (TypeError, ValueError):
            pass
    return "\n".join(lines)


def _risk_label(level: Any, score: Any) -> str:
    text = str(level or "").strip()
    if text:
        low = text.lower()
        if low in {"high", "critical"}:
            return "High Risk"
        if low == "medium":
            return "Medium Risk"
        if low == "low":
            return "Low Risk"
        return f"{text} Risk" if not text.lower().endswith("risk") else text
    try:
        value = int(score)
    except (TypeError, ValueError):
        return "Risk Unknown"
    if value >= 70:
        return "High Risk"
    if value >= 40:
        return "Medium Risk"
    return "Low Risk"


def enrich_user_record(
    user_id: int | None,
    *,
    user_doc: dict[str, Any] | None = None,
    activity_doc: dict[str, Any] | None = None,
    behavior_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge users / user_activity / behavioral_analytics into one enriched object."""
    user_doc = user_doc or {}
    activity_doc = activity_doc or {}
    behavior_doc = behavior_doc or {}

    uid = user_id
    if uid is None:
        raw = user_doc.get("_id", activity_doc.get("_id", behavior_doc.get("user_id")))
        try:
            uid = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            uid = None

    first_name = (
        user_doc.get("first_name")
        or activity_doc.get("first_name")
        or behavior_doc.get("first_name")
    )
    last_name = (
        user_doc.get("last_name")
        or activity_doc.get("last_name")
        or behavior_doc.get("last_name")
    )
    username = normalize_username(
        user_doc.get("username")
        or activity_doc.get("username")
        or behavior_doc.get("username")
    )
    explicit_display = (
        user_doc.get("display_name")
        or activity_doc.get("display_name")
        or behavior_doc.get("display_name")
    )

    risk_score = activity_doc.get("risk_score")
    if risk_score is None:
        risk_score = behavior_doc.get("risk_score")
    risk_level = activity_doc.get("risk_level") or behavior_doc.get("risk_level")

    behavior_score = behavior_doc.get("behavior_score")
    if behavior_score is None:
        behavior_score = activity_doc.get("behavior_score")

    photo = (
        user_doc.get("photo_url")
        or user_doc.get("profile_photo")
        or activity_doc.get("photo_url")
    )

    display = build_display_name(
        display_name=str(explicit_display).strip() if explicit_display else None,
        first_name=str(first_name).strip() if first_name else None,
        last_name=str(last_name).strip() if last_name else None,
        username=username,
        user_id=uid,
    )

    enriched: dict[str, Any] = {
        "user_id": uid,
        "display_name": display,
        "first_name": str(first_name).strip() if first_name else None,
        "last_name": str(last_name).strip() if last_name else None,
        "username": format_username(username),
        "risk_score": _as_int(risk_score),
        "risk_level": str(risk_level).strip() if risk_level else None,
        "behavior_score": _as_int(behavior_score),
        "behavior_status": behavior_doc.get("behavior_status"),
        "profile_photo": photo,
    }
    return enriched


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_user_id(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class UserIdentityEnricher:
    """Batch-load Mongo identity docs and enrich sender references."""

    def __init__(self, db: MongoDatabase | None = None) -> None:
        self.db = db

    def lookup_many(self, user_ids: list[int | str | None]) -> dict[int, dict[str, Any]]:
        """Return ``{user_id: enriched_user}`` for the given ids."""
        ids: list[int] = []
        seen: set[int] = set()
        for raw in user_ids:
            uid = _coerce_user_id(raw)
            if uid is None or uid in seen:
                continue
            seen.add(uid)
            ids.append(uid)

        if not ids:
            return {}

        if self.db is None:
            return {
                uid: enrich_user_record(uid)
                for uid in ids
            }

        users = {
            int(doc["_id"]): dict(doc)
            for doc in self.db["users"].find({"_id": {"$in": ids}})
            if doc.get("_id") is not None
        }
        activities = {
            int(doc["_id"]): dict(doc)
            for doc in self.db["user_activity"].find({"_id": {"$in": ids}})
            if doc.get("_id") is not None
        }
        behaviors: dict[int, dict[str, Any]] = {}
        try:
            for doc in self.db["behavioral_analytics"].find({"user_id": {"$in": ids}}):
                uid = _coerce_user_id(doc.get("user_id", doc.get("_id")))
                if uid is not None:
                    behaviors[uid] = dict(doc)
            # Some installs key BA docs by _id == user_id.
            for doc in self.db["behavioral_analytics"].find({"_id": {"$in": ids}}):
                uid = _coerce_user_id(doc.get("_id"))
                if uid is not None and uid not in behaviors:
                    behaviors[uid] = dict(doc)
        except Exception:  # noqa: BLE001
            logger.debug("behavioral_analytics_lookup_skipped", exc_info=True)

        enriched: dict[int, dict[str, Any]] = {}
        for uid in ids:
            enriched[uid] = enrich_user_record(
                uid,
                user_doc=users.get(uid),
                activity_doc=activities.get(uid),
                behavior_doc=behaviors.get(uid),
            )
        logger.debug(
            "users_enriched",
            extra={
                "ai_requested": len(ids),
                "ai_users_found": len(users),
                "ai_activity_found": len(activities),
                "ai_behavior_found": len(behaviors),
            },
        )
        return enriched

    def lookup_one(self, user_id: int | str | None) -> dict[str, Any] | None:
        uid = _coerce_user_id(user_id)
        if uid is None:
            return None
        return self.lookup_many([uid]).get(uid)

    def enrich_evidence_items(self, items: list[Any]) -> list[Any]:
        """Attach ``metadata.sender_user`` on each evidence item (in place + return)."""
        ids = [getattr(item, "metadata", {}).get("sender_id") for item in items]
        # Also pick up nested mongo_record sender_id.
        for item in items:
            meta = getattr(item, "metadata", None) or {}
            if meta.get("sender_id") is None:
                mongo = getattr(item, "mongo_record", None) or {}
                if mongo.get("sender_id") is not None:
                    meta["sender_id"] = mongo.get("sender_id")
            ids.append(meta.get("sender_id"))

        by_id = self.lookup_many(ids)
        for item in items:
            meta = dict(getattr(item, "metadata", None) or {})
            uid = _coerce_user_id(meta.get("sender_id"))
            if uid is None:
                mongo = getattr(item, "mongo_record", None) or {}
                uid = _coerce_user_id(mongo.get("sender_id"))
                if uid is not None:
                    meta["sender_id"] = uid
            if uid is None:
                continue
            user = by_id.get(uid) or enrich_user_record(uid)
            meta[USER_META_KEY] = user
            # Flat convenience fields for serializers / UI.
            meta["sender_display_name"] = user.get("display_name")
            meta["sender_username"] = user.get("username")
            meta["sender_first_name"] = user.get("first_name")
            meta["sender_last_name"] = user.get("last_name")
            meta["sender_risk_score"] = user.get("risk_score")
            meta["sender_risk_level"] = user.get("risk_level")
            meta["sender_behavior_score"] = user.get("behavior_score")
            item.metadata = meta
        return items


def format_users_roster(users: list[dict[str, Any]]) -> str:
    """Markdown roster of unique users for the LLM evidence context."""
    if not users:
        return ""
    lines = ["Connected Users / Senders in evidence", ""]
    for user in users:
        lines.append(format_user_bullet(user))
        lines.append("")
    return "\n".join(lines).rstrip()


def unique_users_from_evidence(items: list[Any]) -> list[dict[str, Any]]:
    """Deduplicate enriched sender users from evidence metadata."""
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        meta = getattr(item, "metadata", None) or {}
        user = meta.get(USER_META_KEY)
        if not isinstance(user, dict):
            continue
        uid = _coerce_user_id(user.get("user_id"))
        if uid is None or uid in seen:
            continue
        seen.add(uid)
        out.append(user)
    return out


def format_sender_line(user: dict[str, Any] | None, *, sender_id: Any = None) -> str:
    """Single-line sender header for an evidence chunk."""
    if not user:
        uid = _coerce_user_id(sender_id)
        if uid is not None:
            return f"Sender: Unknown User (User ID: {uid})"
        return "Sender: Unknown User"

    display = str(user.get("display_name") or "Unknown User")
    handle = format_username(user.get("username"))
    uid = user.get("user_id")
    parts = [f"Sender: {display}"]
    if handle and handle not in display:
        parts.append(handle)
    if uid is not None:
        parts.append(f"Telegram User ID: {uid}")
    risk = user.get("risk_score")
    level = user.get("risk_level")
    if risk is not None or level:
        risk_bits = []
        if level:
            risk_bits.append(str(level))
        if risk is not None:
            risk_bits.append(str(risk))
        parts.append(f"Risk: {' '.join(risk_bits)}")
    behavior = user.get("behavior_score")
    if behavior is not None:
        parts.append(f"Behavior Score: {behavior}")
    return " | ".join(parts)
