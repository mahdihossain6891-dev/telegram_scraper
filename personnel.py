"""Per-user activity rollups for person-centric intelligence views."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from models import KEYWORD_CATEGORIES, UserActivity, utcnow
from database import MongoSession
from risk_scoring import score_chat, score_message, score_user
from utils import get_logger

logger = get_logger("personnel")


def _display_name(
    first_name: str | None,
    last_name: str | None,
    username: str | None,
    user_id: int,
) -> str:
    parts = [p for p in (first_name, last_name) if p]
    if parts:
        return " ".join(parts)
    if username:
        return f"@{username}"
    return f"User {user_id}"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def record_user_activity(
    session: MongoSession,
    *,
    user_id: int,
    chat_id: int,
    timestamp: datetime | None,
    keywords: list[str],
    categories: list[str],
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    message_risk_score: int | None = None,
) -> None:
    """Incrementally update a user's activity profile after a flagged message."""
    now = utcnow()
    ts = timestamp or now
    chat_key = str(chat_id)

    inc: dict[str, int] = {
        "message_count": 1,
        "suspicious_count": 1,
        f"by_chat.{chat_key}.message_count": 1,
        f"by_chat.{chat_key}.suspicious_count": 1,
    }
    for keyword in keywords:
        safe = str(keyword).replace(".", "_")
        inc[f"keywords.{safe}"] = inc.get(f"keywords.{safe}", 0) + 1
        inc[f"by_chat.{chat_key}.keywords.{safe}"] = (
            inc.get(f"by_chat.{chat_key}.keywords.{safe}", 0) + 1
        )
    for category in categories:
        if category in KEYWORD_CATEGORIES:
            inc[f"categories.{category}"] = inc.get(f"categories.{category}", 0) + 1

    set_fields: dict[str, Any] = {
        "updated_at": now,
        f"by_chat.{chat_key}.chat_id": chat_id,
    }
    if username is not None:
        set_fields["username"] = username
    if first_name is not None:
        set_fields["first_name"] = first_name
    if last_name is not None:
        set_fields["last_name"] = last_name

    max_fields: dict[str, Any] = {
        "last_seen": ts,
        f"by_chat.{chat_key}.last_seen": ts,
    }
    if message_risk_score is not None:
        max_fields["max_message_score"] = int(message_risk_score)

    session.user_activity.update_one(
        {"_id": user_id},
        {
            "$inc": inc,
            "$set": set_fields,
            "$max": max_fields,
            "$min": {"first_seen": ts, f"by_chat.{chat_key}.first_seen": ts},
            "$addToSet": {"chat_ids": chat_id},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    # Re-read and persist dynamic user risk from rollup + behavior.
    refresh_user_risk(session, user_id)


def refresh_user_risk(session: MongoSession, user_id: int) -> None:
    """Recompute and store risk_score for one user activity doc."""
    doc = session.user_activity.find_one({"_id": user_id})
    if not doc:
        return
    activity = UserActivity.from_doc(doc)
    assessment = score_user(
        message_count=activity.message_count,
        chat_ids=activity.chat_ids,
        keywords=activity.keywords,
        categories=activity.categories,
        first_seen=activity.first_seen,
        max_message_score=int(doc.get("max_message_score") or 0) or None,
    )
    session.user_activity.update_one(
        {"_id": user_id},
        {
            "$set": {
                "risk_score": assessment.score,
                "risk_level": assessment.level,
                "risk_factors": list(assessment.factors),
            }
        },
    )


def refresh_chat_risk(session: MongoSession, chat_id: int) -> None:
    """Recompute and store risk fields on a chat document."""
    messages = list(session.messages.find({"chat_id": chat_id}, {"sender_id": 1, "risk_score": 1}))
    if not messages:
        return
    senders = {m.get("sender_id") for m in messages if m.get("sender_id") is not None}
    max_score = max((int(m.get("risk_score") or 0) for m in messages), default=0)

    # Aggregate keyword/category counts from entities for this chat's messages
    message_ids = [int(m["_id"]) for m in session.messages.find({"chat_id": chat_id}, {"_id": 1})]
    keywords: dict[str, int] = {}
    categories: dict[str, int] = {}
    if message_ids:
        for ent in session.entities.find(
            {
                "message_row_id": {"$in": message_ids},
                "entity_type": {"$in": list(KEYWORD_CATEGORIES)},
            }
        ):
            kw = str(ent["entity_value"])
            cat = str(ent["entity_type"])
            keywords[kw] = keywords.get(kw, 0) + 1
            categories[cat] = categories.get(cat, 0) + 1

    assessment = score_chat(
        message_count=len(messages),
        sender_count=len(senders),
        keywords=keywords,
        categories=categories,
        max_message_score=max_score or None,
    )
    session.chats.update_one(
        {"_id": chat_id},
        {
            "$set": {
                "risk_score": assessment.score,
                "risk_level": assessment.level,
                "risk_factors": list(assessment.factors),
                "updated_at": utcnow(),
            }
        },
    )


def rebuild_user_activity(session: MongoSession) -> int:
    """Rebuild all user_activity docs from messages + keyword entities."""
    session.user_activity.delete_many({})

    keyword_by_message: dict[int, list[tuple[str, str]]] = {}
    for doc in session.entities.find(
        {"entity_type": {"$in": list(KEYWORD_CATEGORIES)}},
        {"message_row_id": 1, "entity_type": 1, "entity_value": 1},
    ):
        mid = int(doc["message_row_id"])
        keyword_by_message.setdefault(mid, []).append(
            (str(doc["entity_type"]), str(doc["entity_value"]))
        )

    users = {u.id: u for u in session.list_users()}
    count = 0
    touched_chats: set[int] = set()
    for message in session.list_messages():
        if message.sender_id is None or message.id is None:
            continue
        hits = keyword_by_message.get(message.id, [])
        categories = sorted({cat for cat, _ in hits})
        keywords = [kw for _, kw in hits]
        if not keywords:
            keywords = ["(flagged)"]
            categories = []

        # Backfill message risk if missing
        risk = score_message(
            keywords=keywords,
            categories=categories,
            text=message.text,
        )
        session.messages.update_one(
            {"_id": message.id},
            {
                "$set": {
                    "risk_score": risk.score,
                    "risk_level": risk.level,
                    "risk_factors": list(risk.factors),
                }
            },
        )

        user = users.get(message.sender_id)
        record_user_activity(
            session,
            user_id=message.sender_id,
            chat_id=message.chat_id,
            timestamp=message.timestamp,
            keywords=keywords,
            categories=categories,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None,
            message_risk_score=risk.score,
        )
        touched_chats.add(message.chat_id)
        count += 1

    for chat_id in touched_chats:
        refresh_chat_risk(session, chat_id)

    logger.info("Rebuilt user_activity from %s messages", count)
    return count


def ensure_user_activity(session: MongoSession) -> None:
    """Backfill user_activity when the collection is empty but messages exist."""
    if session.user_activity.count_documents({}) > 0:
        return
    if session.messages.count_documents({}) == 0:
        return
    rebuild_user_activity(session)


def _chat_title_map(session: MongoSession) -> dict[int, str]:
    return {
        chat.id: (chat.title or chat.username or f"Chat {chat.id}")
        for chat in session.list_chats()
    }


def activity_to_row(
    activity: UserActivity,
    chat_titles: dict[int, str],
    *,
    chat_id: int | None = None,
) -> dict[str, Any]:
    """Serialize a user activity doc for list APIs / export."""
    by_chat = activity.by_chat
    message_count = activity.message_count
    suspicious_count = activity.suspicious_count
    keywords = activity.keywords
    first_seen = activity.first_seen
    last_seen = activity.last_seen
    group_name = ", ".join(
        chat_titles.get(cid, f"Chat {cid}") for cid in activity.chat_ids
    )

    if chat_id is not None:
        chat_key = str(chat_id)
        chat_stats = by_chat.get(chat_key) or {}
        message_count = int(chat_stats.get("message_count") or 0)
        suspicious_count = int(chat_stats.get("suspicious_count") or 0)
        keywords = {
            str(k): int(v) for k, v in (chat_stats.get("keywords") or {}).items()
        }
        first_seen = chat_stats.get("first_seen") or first_seen
        last_seen = chat_stats.get("last_seen") or last_seen
        group_name = chat_titles.get(chat_id, f"Chat {chat_id}")

    display = activity.display_name
    if display.startswith("User ") and activity.id in chat_titles:
        display = f"{chat_titles[activity.id]} (channel)"

    keyword_total = sum(keywords.values())
    return {
        "user_id": activity.id,
        "display_name": display,
        "username": activity.username,
        "first_name": activity.first_name,
        "last_name": activity.last_name,
        "group_name": group_name,
        "chat_ids": activity.chat_ids,
        "message_count": message_count,
        "suspicious_count": suspicious_count,
        "keywords": keywords,
        "keyword_list": sorted(keywords.keys()),
        "keyword_total": keyword_total,
        "categories": activity.categories,
        "first_seen": _iso(first_seen) if isinstance(first_seen, datetime) else first_seen,
        "last_seen": _iso(last_seen) if isinstance(last_seen, datetime) else last_seen,
        "risk_score": activity.risk_score,
        "risk_level": activity.risk_level,
        "risk_factors": activity.risk_factors,
    }


def list_personnel(
    session: MongoSession,
    *,
    chat_id: int | None = None,
    suspicious_only: bool = False,
    keyword: str | None = None,
    query: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = "suspicious_count",
) -> list[dict[str, Any]]:
    """Return filtered/sorted personnel activity rows."""
    ensure_user_activity(session)
    chat_titles = _chat_title_map(session)
    rows: list[dict[str, Any]] = []

    for doc in session.user_activity.find():
        activity = UserActivity.from_doc(doc)
        if chat_id is not None and chat_id not in activity.chat_ids:
            continue
        row = activity_to_row(activity, chat_titles, chat_id=chat_id)
        if suspicious_only and int(row["suspicious_count"] or 0) <= 0:
            continue
        if keyword:
            needle = keyword.lower()
            if not any(needle in k.lower() for k in row["keyword_list"]):
                continue
        if query:
            q = query.lower().strip().lstrip("@")
            hay = " ".join(
                str(x or "")
                for x in (
                    row["display_name"],
                    row["username"],
                    row["first_name"],
                    row["last_name"],
                    row["user_id"],
                )
            ).lower()
            if q not in hay:
                continue
        if date_from or date_to:
            last = row.get("last_seen")
            first = row.get("first_seen")
            # Keep users whose activity window overlaps the filter range.
            if date_from and last:
                last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00")) if isinstance(last, str) else last
                if isinstance(last_dt, datetime) and last_dt < date_from:
                    continue
            if date_to and first:
                first_dt = datetime.fromisoformat(str(first).replace("Z", "+00:00")) if isinstance(first, str) else first
                if isinstance(first_dt, datetime) and first_dt > date_to:
                    continue
        rows.append(row)

    sort_key = {
        "suspicious_count": lambda r: int(r["suspicious_count"] or 0),
        "message_count": lambda r: int(r["message_count"] or 0),
        "last_seen": lambda r: str(r.get("last_seen") or ""),
        "keyword_total": lambda r: int(r["keyword_total"] or 0),
        "display_name": lambda r: str(r.get("display_name") or "").lower(),
    }.get(sort_by, lambda r: int(r["suspicious_count"] or 0))

    reverse = sort_by != "display_name"
    rows.sort(key=sort_key, reverse=reverse)
    return rows


def get_personnel_detail(session: MongoSession, user_id: int) -> dict[str, Any] | None:
    """Return a detailed personnel profile with message history."""
    ensure_user_activity(session)
    doc = session.user_activity.find_one({"_id": user_id})
    user = session.get_user(user_id)
    chat_titles = _chat_title_map(session)

    if doc is None:
        # Fallback: synthesize from messages if activity missing for this user.
        messages = list(session.messages.find({"sender_id": user_id}).sort("timestamp", 1))
        if not messages:
            return None
        rebuild_user_activity(session)
        doc = session.user_activity.find_one({"_id": user_id})
        if doc is None:
            return None

    activity = UserActivity.from_doc(doc)
    summary = activity_to_row(activity, chat_titles)

    # Per-group breakdown
    groups = []
    for chat_key, stats in (activity.by_chat or {}).items():
        cid = int(stats.get("chat_id") or chat_key)
        groups.append(
            {
                "chat_id": cid,
                "group_name": chat_titles.get(cid, f"Chat {cid}"),
                "message_count": int(stats.get("message_count") or 0),
                "suspicious_count": int(stats.get("suspicious_count") or 0),
                "keywords": stats.get("keywords") or {},
                "first_seen": _iso(stats.get("first_seen"))
                if isinstance(stats.get("first_seen"), datetime)
                else stats.get("first_seen"),
                "last_seen": _iso(stats.get("last_seen"))
                if isinstance(stats.get("last_seen"), datetime)
                else stats.get("last_seen"),
            }
        )
    groups.sort(key=lambda g: g["suspicious_count"], reverse=True)

    message_docs = list(
        session.messages.find({"sender_id": user_id}).sort("timestamp", -1)
    )
    message_ids = [int(m["_id"]) for m in message_docs]
    entities_by_message: dict[int, list[dict[str, Any]]] = {}
    if message_ids:
        for ent in session.entities.find({"message_row_id": {"$in": message_ids}}):
            mid = int(ent["message_row_id"])
            entities_by_message.setdefault(mid, []).append(
                {
                    "entity_type": ent["entity_type"],
                    "entity_value": ent["entity_value"],
                }
            )

    history = []
    for msg in message_docs:
        mid = int(msg["_id"])
        ents = entities_by_message.get(mid, [])
        keyword_ents = [
            e for e in ents if e["entity_type"] in KEYWORD_CATEGORIES
        ]
        history.append(
            {
                "id": mid,
                "message_id": int(msg["message_id"]),
                "chat_id": int(msg["chat_id"]),
                "group_name": chat_titles.get(int(msg["chat_id"]), f"Chat {msg['chat_id']}"),
                "timestamp": _iso(msg.get("timestamp"))
                if isinstance(msg.get("timestamp"), datetime)
                else msg.get("timestamp"),
                "text": msg.get("text"),
                "media_type": msg.get("media_type"),
                "views": msg.get("views"),
                "categories": sorted({e["entity_type"] for e in keyword_ents}),
                "keywords": [e["entity_value"] for e in keyword_ents],
                "suspicious": bool(keyword_ents) or True,
                "entities": ents,
            }
        )

    return {
        "user": {
            "user_id": user_id,
            "display_name": _display_name(
                (user.first_name if user else None) or activity.first_name,
                (user.last_name if user else None) or activity.last_name,
                (user.username if user else None) or activity.username,
                user_id,
            ),
            "username": (user.username if user else None) or activity.username,
            "first_name": (user.first_name if user else None) or activity.first_name,
            "last_name": (user.last_name if user else None) or activity.last_name,
        },
        "summary": summary,
        "groups": groups,
        "keyword_frequency": dict(
            sorted(activity.keywords.items(), key=lambda kv: kv[1], reverse=True)
        ),
        "category_frequency": dict(
            sorted(activity.categories.items(), key=lambda kv: kv[1], reverse=True)
        ),
        "messages": history,
    }
