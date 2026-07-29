"""Behavioral Analytics — isolated module.

Computes HOW users behave (frequency, hours, forwards, media, language, joins)
from existing messages/chats/users **without modifying those collections**.

Results are stored only in ``behavioral_analytics``.

Enable/disable: remove ``/behavioral-analytics`` page + ``/api/behavioral*`` routes;
no other app features depend on this module.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from database import MongoSession
from models import utcnow
from utils import get_logger

logger = get_logger("behavioral_analytics")

COLLECTION = "behavioral_analytics"

# Behavior score contributions (documented, tunable)
WEIGHT_ACTIVITY_SPIKE = 20
WEIGHT_NIGHT_ACTIVITY = 15
WEIGHT_HIGH_FORWARDING = 25
WEIGHT_RAPID_JOINS = 20
WEIGHT_USERNAME_CHANGE = 10
WEIGHT_DELETION = 30  # reserved — data usually unavailable
WEIGHT_LANGUAGE_SWITCH = 15
WEIGHT_MEDIA_SPIKE = 10

NIGHT_HOURS = set(range(0, 5))  # 00:00–04:59
SPIKE_RATIO = 5.0  # daily count vs average
FORWARD_FLAG_RATIO = 0.7
MEDIA_SPIKE_RATIO = 0.8
RAPID_JOIN_THRESHOLD = 5  # distinct chats in short window (heuristic)


@dataclass
class BehaviorAlert:
    time: str | None
    reason: str
    impact: int
    severity: str  # Low | Medium | High | Critical

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ensure_behavioral_indexes(session: MongoSession) -> None:
    col = session.db[COLLECTION]
    col.create_index([("user_id", 1)], unique=True, name="uq_behavioral_user")
    col.create_index([("behavior_score", 1)], name="ix_behavioral_score")
    col.create_index([("username", 1)], name="ix_behavioral_username")
    col.create_index([("behavior_status", 1)], name="ix_behavioral_status")
    col.create_index([("last_updated", -1)], name="ix_behavioral_updated")


def _iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _display_name(user: dict[str, Any] | None, user_id: int) -> str:
    if not user:
        return f"User {user_id}"
    parts = [user.get("first_name") or "", user.get("last_name") or ""]
    name = " ".join(p for p in parts if p).strip()
    if name:
        return name
    if user.get("username"):
        return f"@{user['username']}"
    return f"User {user_id}"


def _detect_scripts(text: str) -> list[str]:
    """Lightweight language/script detection (no external NLP dependency)."""
    if not text or not text.strip():
        return []
    counts = Counter()
    for ch in text:
        o = ord(ch)
        if 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F:
            counts["Arabic"] += 1
        elif 0x0400 <= o <= 0x04FF:
            counts["Russian"] += 1
        elif 0x4E00 <= o <= 0x9FFF:
            counts["Chinese"] += 1
        elif 0x0900 <= o <= 0x097F:
            counts["Hindi"] += 1
        elif ("a" <= ch.lower() <= "z"):
            counts["English"] += 1
    if not counts:
        return ["Unknown"]
    total = sum(counts.values())
    # Keep scripts that are at least 15% of letters
    return [lang for lang, n in counts.most_common() if n / total >= 0.15] or [counts.most_common(1)[0][0]]


def _status_for_score(score: int) -> str:
    if score >= 76:
        return "High Risk"
    if score >= 51:
        return "Suspicious"
    if score >= 26:
        return "Unusual"
    return "Normal"


def _classify_media(media_type: str | None, text: str | None) -> str:
    raw = (media_type or "").lower()
    if not raw:
        if text and re.search(r"https?://", text):
            return "links"
        return "text"
    if "photo" in raw or "image" in raw:
        return "photos"
    if "video" in raw:
        return "videos"
    if "voice" in raw or "audio" in raw:
        return "voice"
    if "document" in raw or "file" in raw:
        return "documents"
    if "gif" in raw or "animation" in raw:
        return "gifs"
    if "sticker" in raw:
        return "stickers"
    return "other_media"


def _compute_user_profile(
    user_id: int,
    user_doc: dict[str, Any] | None,
    messages: list[dict[str, Any]],
    chats: dict[int, dict[str, Any]],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    timestamps = [_parse_ts(m.get("timestamp")) for m in messages]
    timestamps = [t for t in timestamps if t is not None]
    timestamps.sort()

    first_seen = timestamps[0] if timestamps else None
    last_seen = timestamps[-1] if timestamps else None

    # --- posting frequency ---
    by_day: Counter[str] = Counter()
    by_hour: Counter[int] = Counter()
    by_weekday: Counter[int] = Counter()
    for ts in timestamps:
        by_day[ts.strftime("%Y-%m-%d")] += 1
        by_hour[ts.hour] += 1
        by_weekday[ts.weekday()] += 1

    day_counts = list(by_day.values()) or [0]
    avg_per_day = round(sum(day_counts) / max(len(day_counts), 1), 2)
    peak_day = max(day_counts) if day_counts else 0
    msgs_per_week = round(avg_per_day * 7, 2)

    # hourly average across days
    span_days = max(len(by_day), 1)
    msgs_per_hour_avg = round(len(messages) / max(span_days * 24, 1), 4)

    # --- online hours ---
    hours = [ts.hour for ts in timestamps]
    first_hour = min(hours) if hours else None
    last_hour = max(hours) if hours else None
    most_active_hour = by_hour.most_common(1)[0][0] if by_hour else None
    most_active_weekday = by_weekday.most_common(1)[0][0] if by_weekday else None
    night_count = sum(1 for h in hours if h in NIGHT_HOURS)
    night_pct = round(100.0 * night_count / max(len(hours), 1), 1)
    active_duration_est = (
        (last_hour - first_hour) % 24 if first_hour is not None and last_hour is not None else 0
    )

    # --- forwarding ---
    forwarded = sum(
        1
        for m in messages
        if m.get("forward_from_chat_id") is not None or m.get("forward_from_message_id") is not None
    )
    original = len(messages) - forwarded
    forward_ratio = round(forwarded / max(len(messages), 1), 3)
    forward_sources = Counter(
        m.get("forward_from_chat_id")
        for m in messages
        if m.get("forward_from_chat_id") is not None
    )

    # --- media ---
    media_counts: Counter[str] = Counter()
    for m in messages:
        media_counts[_classify_media(m.get("media_type"), m.get("text"))] += 1
    media_total = sum(media_counts.values()) or 1
    media_usage = {k: round(100.0 * v / media_total, 1) for k, v in media_counts.items()}
    non_text_pct = round(100.0 * (media_total - media_counts.get("text", 0)) / media_total, 1)

    # --- language / scripts ---
    lang_counter: Counter[str] = Counter()
    for m in messages:
        for lang in _detect_scripts(m.get("text") or ""):
            lang_counter[lang] += 1
    lang_total = sum(lang_counter.values()) or 1
    language_distribution = {
        k: round(100.0 * v / lang_total, 1) for k, v in lang_counter.most_common()
    }
    languages_used = list(language_distribution.keys())

    # --- groups / channels ---
    chat_ids = {m.get("chat_id") for m in messages if m.get("chat_id") is not None}
    groups_joined = 0
    channels_joined = 0
    private_chats = 0
    for cid in chat_ids:
        chat = chats.get(cid) or {}
        ctype = (chat.get("chat_type") or "").lower()
        if ctype == "channel":
            channels_joined += 1
        elif ctype == "private chat":
            private_chats += 1
        else:
            groups_joined += 1

    # join pattern heuristic: distinct chats relative to message span
    join_rate = round(len(chat_ids) / max(span_days, 1), 2)

    # --- deletions (unavailable from current scraper) ---
    deletion_rate = {
        "available": False,
        "deleted_messages": 0,
        "deletion_percentage": 0.0,
        "avg_deletion_delay_seconds": None,
        "note": "Deletion events are not captured by the current scraper.",
    }

    # --- profile changes (compare to previous snapshot) ---
    username = (user_doc or {}).get("username")
    display = _display_name(user_doc, user_id)
    profile_changes: list[dict[str, Any]] = list((previous or {}).get("profile_changes") or [])
    if previous:
        prev_user = previous.get("username")
        prev_display = previous.get("display_name")
        now_iso = _iso(utcnow())
        if prev_user != username and (prev_user or username):
            profile_changes.append(
                {
                    "time": now_iso,
                    "field": "username",
                    "from": prev_user,
                    "to": username,
                }
            )
        if prev_display != display:
            profile_changes.append(
                {
                    "time": now_iso,
                    "field": "display_name",
                    "from": prev_display,
                    "to": display,
                }
            )
    profile_changes = profile_changes[-50:]

    # --- account age ---
    days_active = 1
    if first_seen and last_seen:
        days_active = max(1, (last_seen.date() - first_seen.date()).days + 1)

    # --- behavior score + alerts ---
    score = 0
    alerts: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = list((previous or {}).get("behavior_history") or [])
    n_msgs = len(messages)
    # Sparse corpora (early live scrapes / simulation) need softer thresholds so
    # profiles still receive meaningful scores instead of staying at 0.
    sparse = n_msgs < 40
    min_for_patterns = 3 if sparse else 5
    spike_min_peak = 5 if sparse else 20
    spike_ratio = 2.5 if sparse else SPIKE_RATIO
    forward_flag = 0.35 if sparse else FORWARD_FLAG_RATIO
    media_flag = 40.0 if sparse else MEDIA_SPIKE_RATIO * 100
    night_flag = 25.0 if sparse else 40.0

    # Baseline activity — every sender with messages gets a non-zero floor.
    if n_msgs > 0:
        volume_pts = min(20, int(math.log1p(n_msgs) * 4))
        score += volume_pts
        if volume_pts >= 8:
            history.append(
                {
                    "time": _iso(last_seen),
                    "title": "Sustained posting volume",
                    "detail": f"{n_msgs} monitored messages",
                }
            )

    # Multi-source footprint
    if len(chat_ids) >= 2:
        score += min(15, len(chat_ids) * 3)
        history.append(
            {
                "time": _iso(last_seen),
                "title": "Multi-source presence",
                "detail": f"Active across {len(chat_ids)} chats",
            }
        )

    if avg_per_day > 0 and peak_day >= avg_per_day * spike_ratio and peak_day >= spike_min_peak:
        score += WEIGHT_ACTIVITY_SPIKE
        alerts.append(
            BehaviorAlert(
                time=_iso(last_seen),
                reason=f"Activity spike: peak {peak_day}/day vs avg {avg_per_day}",
                impact=WEIGHT_ACTIVITY_SPIKE,
                severity="High",
            ).to_dict()
        )
        history.append(
            {
                "time": _iso(last_seen),
                "title": "Activity increased",
                "detail": f"Peak {peak_day} messages/day (avg {avg_per_day})",
            }
        )

    if night_pct >= night_flag and n_msgs >= min_for_patterns:
        score += WEIGHT_NIGHT_ACTIVITY
        alerts.append(
            BehaviorAlert(
                time=_iso(last_seen),
                reason=f"Elevated night activity ({night_pct}%)",
                impact=WEIGHT_NIGHT_ACTIVITY,
                severity="Medium",
            ).to_dict()
        )
        history.append(
            {
                "time": _iso(last_seen),
                "title": "Night activity pattern",
                "detail": f"{night_pct}% of messages between 00:00–05:00",
            }
        )

    if forward_ratio >= forward_flag and n_msgs >= min_for_patterns:
        score += WEIGHT_HIGH_FORWARDING
        alerts.append(
            BehaviorAlert(
                time=_iso(last_seen),
                reason=f"High forwarding rate ({round(forward_ratio * 100, 1)}%)",
                impact=WEIGHT_HIGH_FORWARDING,
                severity="High",
            ).to_dict()
        )
        history.append(
            {
                "time": _iso(last_seen),
                "title": "Forwarding spike",
                "detail": f"{forwarded}/{n_msgs} messages forwarded",
            }
        )

    rapid_join_days = 14 if sparse else 3
    rapid_join_min = 3 if sparse else RAPID_JOIN_THRESHOLD
    if len(chat_ids) >= rapid_join_min and days_active <= rapid_join_days:
        score += WEIGHT_RAPID_JOINS
        alerts.append(
            BehaviorAlert(
                time=_iso(first_seen),
                reason=f"Rapid expansion: {len(chat_ids)} sources in {days_active} day(s)",
                impact=WEIGHT_RAPID_JOINS,
                severity="High",
            ).to_dict()
        )
        history.append(
            {
                "time": _iso(first_seen),
                "title": "Joined multiple sources quickly",
                "detail": f"{len(chat_ids)} chats observed",
            }
        )

    if any(c.get("field") == "username" for c in profile_changes[-3:]):
        score += WEIGHT_USERNAME_CHANGE
        alerts.append(
            BehaviorAlert(
                time=profile_changes[-1].get("time"),
                reason="Recent username / identity change",
                impact=WEIGHT_USERNAME_CHANGE,
                severity="Medium",
            ).to_dict()
        )
        history.append(
            {
                "time": profile_changes[-1].get("time"),
                "title": "Changed username",
                "detail": f"{profile_changes[-1].get('from')} → {profile_changes[-1].get('to')}",
            }
        )

    if len(languages_used) >= 3:
        score += WEIGHT_LANGUAGE_SWITCH
        alerts.append(
            BehaviorAlert(
                time=_iso(last_seen),
                reason=f"Multi-script / language switching ({', '.join(languages_used[:4])})",
                impact=WEIGHT_LANGUAGE_SWITCH,
                severity="Medium",
            ).to_dict()
        )
        history.append(
            {
                "time": _iso(last_seen),
                "title": "Language / script changes",
                "detail": ", ".join(languages_used),
            }
        )

    if non_text_pct >= media_flag and n_msgs >= min_for_patterns:
        score += WEIGHT_MEDIA_SPIKE
        alerts.append(
            BehaviorAlert(
                time=_iso(last_seen),
                reason=f"Media-heavy behavior ({non_text_pct}% non-text)",
                impact=WEIGHT_MEDIA_SPIKE,
                severity="Medium",
            ).to_dict()
        )
        history.append(
            {
                "time": _iso(last_seen),
                "title": "Media usage spike",
                "detail": f"{non_text_pct}% media / links",
            }
        )

    # Seed timeline with first/last activity if empty
    if first_seen:
        history.insert(
            0,
            {
                "time": _iso(first_seen),
                "title": "First observed activity",
                "detail": f"{groups_joined} groups · {channels_joined} channels · {private_chats} DMs",
            },
        )
    # Deduplicate / cap history
    seen_h: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in history:
        key = f"{item.get('time')}|{item.get('title')}|{item.get('detail')}"
        if key in seen_h:
            continue
        seen_h.add(key)
        deduped.append(item)
    history = deduped[-100:]

    score = max(0, min(100, score))
    status = _status_for_score(score)

    # Chart series
    daily_series = [
        {"date": day, "messages": by_day[day]} for day in sorted(by_day.keys())
    ]
    hourly_series = [{"hour": h, "messages": by_hour.get(h, 0)} for h in range(24)]
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_series = [
        {"weekday": weekday_names[i], "messages": by_weekday.get(i, 0)} for i in range(7)
    ]

    # heatmap day x hour
    heat: dict[tuple[int, int], int] = defaultdict(int)
    for ts in timestamps:
        heat[(ts.weekday(), ts.hour)] += 1
    heatmap = [
        {"weekday": weekday_names[d], "hour": h, "messages": heat.get((d, h), 0)}
        for d in range(7)
        for h in range(24)
    ]

    return {
        "user_id": user_id,
        "username": username,
        "display_name": display,
        "phone_number": (user_doc or {}).get("phone") or (user_doc or {}).get("phone_number"),
        "risk_score": int((previous or {}).get("risk_score") or 0),  # optional overlay
        "behavior_score": score,
        "behavior_status": status,
        "first_seen": _iso(first_seen),
        "last_seen": _iso(last_seen),
        "groups_joined": groups_joined,
        "channels_joined": channels_joined,
        "private_chats": private_chats,
        "languages_used": languages_used,
        "average_messages_per_day": avg_per_day,
        "messages_per_hour_avg": msgs_per_hour_avg,
        "messages_per_week_avg": msgs_per_week,
        "peak_daily_messages": peak_day,
        "most_active_hour": most_active_hour,
        "most_active_weekday": most_active_weekday,
        "first_message_hour": first_hour,
        "last_message_hour": last_hour,
        "active_duration_hours_est": active_duration_est,
        "night_activity_percentage": night_pct,
        "media_usage": media_usage,
        "non_text_percentage": non_text_pct,
        "forwarding_rate": {
            "forwarded": forwarded,
            "original": original,
            "forward_ratio": forward_ratio,
            "forward_sources": [
                {"chat_id": k, "count": v} for k, v in forward_sources.most_common(10)
            ],
        },
        "deletion_rate": deletion_rate,
        "language_distribution": language_distribution,
        "profile_changes": profile_changes,
        "account_age": {
            "first_monitored": _iso(first_seen),
            "days_active": days_active,
            "groups_over_time": groups_joined,
            "channels_over_time": channels_joined,
        },
        "group_join_pattern": {
            "distinct_sources": len(chat_ids),
            "joins_per_day_est": join_rate,
            "chat_ids": list(chat_ids),
        },
        "posting_frequency": {
            "total_messages": len(messages),
            "avg_daily": avg_per_day,
            "peak_daily": peak_day,
            "per_hour_avg": msgs_per_hour_avg,
            "per_week_avg": msgs_per_week,
            "daily_series": daily_series,
        },
        "online_hours": {
            "first_hour": first_hour,
            "last_hour": last_hour,
            "most_active_hour": most_active_hour,
            "most_active_weekday": most_active_weekday,
            "night_activity_percentage": night_pct,
            "hourly_series": hourly_series,
            "weekday_series": weekday_series,
            "heatmap": heatmap,
        },
        "behavior_history": history,
        "alerts": alerts,
        "behavior_trend": _trend_label(previous, score),
        "message_count": len(messages),
        "last_updated": _iso(utcnow()),
    }


def _trend_label(previous: dict[str, Any] | None, score: int) -> str:
    if not previous:
        return "New"
    prev = int(previous.get("behavior_score") or 0)
    if score > prev + 5:
        return "Rising"
    if score < prev - 5:
        return "Falling"
    return "Stable"


def rebuild_behavioral_analytics(session: MongoSession) -> dict[str, int]:
    """Recompute all behavioral profiles from messages (read-only on source data)."""
    ensure_behavioral_indexes(session)
    col = session.db[COLLECTION]

    users = {doc["_id"]: doc for doc in session.users.find()}
    chats = {doc["_id"]: doc for doc in session.chats.find()}
    previous_docs = {doc["user_id"]: doc for doc in col.find()}

    by_sender: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for msg in session.messages.find():
        sid = msg.get("sender_id")
        if sid is None:
            continue
        by_sender[int(sid)].append(msg)

    # Drop stale profiles for senders who no longer have messages (e.g. sim reset).
    active_ids = set(by_sender.keys())
    if previous_docs:
        stale = [uid for uid in previous_docs if uid not in active_ids]
        if stale:
            col.delete_many({"user_id": {"$in": stale}})

    written = 0
    for user_id, msgs in by_sender.items():
        profile = _compute_user_profile(
            user_id,
            users.get(user_id),
            msgs,
            chats,
            previous_docs.get(user_id),
        )
        # Overlay content risk from user_activity if present
        activity = session.user_activity.find_one({"_id": user_id}) or {}
        profile["risk_score"] = int(activity.get("risk_score") or 0)
        profile["content_risk_level"] = activity.get("risk_level")

        col.update_one(
            {"user_id": user_id},
            {"$set": profile},
            upsert=True,
        )
        written += 1

    logger.info("Behavioral analytics rebuilt for %d users", written)
    return {"profiles_written": written, "users_with_messages": len(by_sender)}


def ensure_behavioral_analytics(session: MongoSession) -> dict[str, int] | None:
    """Rebuild profiles when messages exist but behavioral scores are missing/stale."""
    ensure_behavioral_indexes(session)
    message_count = session.messages.count_documents({})
    if message_count <= 0:
        return None
    profile_count = session.db[COLLECTION].count_documents({})
    if profile_count > 0:
        # Rebuild when scores are all zero but there is activity to score.
        sample = list(
            session.db[COLLECTION].find({}, {"behavior_score": 1}).limit(25)
        )
        if sample and any(int(row.get("behavior_score") or 0) > 0 for row in sample):
            return None
    return rebuild_behavioral_analytics(session)


def list_behavioral_profiles(
    session: MongoSession,
    *,
    q: str | None = None,
    min_score: int = 0,
    max_score: int = 100,
    status: str | None = None,
    chat_id: int | None = None,
    language: str | None = None,
    behavior_type: str | None = None,
    sort_by: str = "behavior_score",
    limit: int = 200,
) -> list[dict[str, Any]]:
    ensure_behavioral_analytics(session)
    ensure_behavioral_indexes(session)
    col = session.db[COLLECTION]
    query: dict[str, Any] = {
        "behavior_score": {"$gte": min_score, "$lte": max_score},
    }
    if status:
        query["behavior_status"] = status
    if chat_id is not None:
        query["group_join_pattern.chat_ids"] = chat_id
    if language:
        query["languages_used"] = language

    cursor = col.find(query)
    rows = list(cursor)
    if behavior_type:
        needle = behavior_type.strip().lower()
        rows = [
            row
            for row in rows
            if any(
                needle in str(a.get("reason") or "").lower()
                for a in (row.get("alerts") or [])
            )
        ]
    if q:
        needle = q.strip().lower().lstrip("@")
        filtered = []
        for row in rows:
            hay = " ".join(
                [
                    str(row.get("user_id") or ""),
                    str(row.get("username") or ""),
                    str(row.get("display_name") or ""),
                    str(row.get("phone_number") or ""),
                ]
            ).lower()
            if needle in hay:
                filtered.append(row)
        rows = filtered

    reverse = sort_by != "display_name"
    def sort_key(row: dict[str, Any]) -> Any:
        if sort_by == "display_name":
            return str(row.get("display_name") or "").lower()
        if sort_by == "last_seen":
            return row.get("last_seen") or ""
        if sort_by == "average_messages_per_day":
            return float(row.get("average_messages_per_day") or 0)
        if sort_by == "forward_ratio":
            return float((row.get("forwarding_rate") or {}).get("forward_ratio") or 0)
        return int(row.get("behavior_score") or 0)

    rows.sort(key=sort_key, reverse=reverse)
    # Strip heavy series for list view
    light: list[dict[str, Any]] = []
    for row in rows[:limit]:
        light.append(
            {
                "user_id": row.get("user_id"),
                "username": row.get("username"),
                "display_name": row.get("display_name"),
                "behavior_score": row.get("behavior_score"),
                "behavior_status": row.get("behavior_status"),
                "behavior_trend": row.get("behavior_trend"),
                "risk_score": row.get("risk_score"),
                "first_seen": row.get("first_seen"),
                "last_seen": row.get("last_seen"),
                "groups_joined": row.get("groups_joined"),
                "channels_joined": row.get("channels_joined"),
                "private_chats": row.get("private_chats"),
                "languages_used": row.get("languages_used"),
                "average_messages_per_day": row.get("average_messages_per_day"),
                "most_active_hour": row.get("most_active_hour"),
                "night_activity_percentage": row.get("night_activity_percentage"),
                "non_text_percentage": row.get("non_text_percentage"),
                "forward_ratio": (row.get("forwarding_rate") or {}).get("forward_ratio"),
                "alert_count": len(row.get("alerts") or []),
                "phone_number": row.get("phone_number"),
            }
        )
    return light


def get_behavioral_profile(session: MongoSession, user_id: int) -> dict[str, Any] | None:
    ensure_behavioral_analytics(session)
    ensure_behavioral_indexes(session)
    doc = session.db[COLLECTION].find_one({"user_id": user_id})
    if not doc:
        return None
    doc.pop("_id", None)
    return doc


def behavioral_overview(session: MongoSession) -> dict[str, Any]:
    ensure_behavioral_analytics(session)
    ensure_behavioral_indexes(session)
    col = session.db[COLLECTION]
    rows = list(col.find())
    if not rows:
        return {
            "total_users": 0,
            "distribution": {"Normal": 0, "Unusual": 0, "Suspicious": 0, "High Risk": 0},
            "avg_messages_per_day": 0,
            "avg_active_hour": None,
            "top_outliers": [],
            "recent_behavior_changes": [],
            "highest_forwarding": [],
            "highest_media": [],
            "activity_spikes": [],
        }

    dist = Counter(r.get("behavior_status") or "Normal" for r in rows)
    avg_mpd = round(
        sum(float(r.get("average_messages_per_day") or 0) for r in rows) / len(rows),
        2,
    )
    hours = [r.get("most_active_hour") for r in rows if r.get("most_active_hour") is not None]
    avg_hour = round(sum(hours) / len(hours), 1) if hours else None

    outliers = sorted(rows, key=lambda r: int(r.get("behavior_score") or 0), reverse=True)[:8]
    rising = [r for r in rows if r.get("behavior_trend") == "Rising"]
    rising = sorted(rising, key=lambda r: int(r.get("behavior_score") or 0), reverse=True)[:8]
    forwarding = sorted(
        rows,
        key=lambda r: float((r.get("forwarding_rate") or {}).get("forward_ratio") or 0),
        reverse=True,
    )[:8]
    media = sorted(rows, key=lambda r: float(r.get("non_text_percentage") or 0), reverse=True)[:8]
    spikes = [
        r
        for r in rows
        if any("spike" in str(a.get("reason") or "").lower() for a in (r.get("alerts") or []))
    ][:8]

    def brief(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "user_id": r.get("user_id"),
            "display_name": r.get("display_name"),
            "username": r.get("username"),
            "behavior_score": r.get("behavior_score"),
            "behavior_status": r.get("behavior_status"),
            "behavior_trend": r.get("behavior_trend"),
            "forward_ratio": (r.get("forwarding_rate") or {}).get("forward_ratio"),
            "non_text_percentage": r.get("non_text_percentage"),
            "average_messages_per_day": r.get("average_messages_per_day"),
            "last_seen": r.get("last_seen"),
        }

    return {
        "total_users": len(rows),
        "distribution": {
            "Normal": dist.get("Normal", 0),
            "Unusual": dist.get("Unusual", 0),
            "Suspicious": dist.get("Suspicious", 0),
            "High Risk": dist.get("High Risk", 0),
        },
        "avg_messages_per_day": avg_mpd,
        "avg_active_hour": avg_hour,
        "top_outliers": [brief(r) for r in outliers],
        "recent_behavior_changes": [brief(r) for r in rising],
        "highest_forwarding": [brief(r) for r in forwarding],
        "highest_media": [brief(r) for r in media],
        "activity_spikes": [brief(r) for r in spikes],
    }
