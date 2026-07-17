"""Streamlit dashboard helpers and page renderers for stored Telegram data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics import (
    AnalyticsEngine,
    AnalyticsSummary,
    SearchHit,
    messages_per_day_chart,
    messages_per_hour_chart,
)
from config import Settings, ensure_directories, load_minimal_settings, load_settings
from database import get_session, init_db
from entity_extractor import CONTENT_ENTITY_TYPES, KEYWORD_ENTITY_TYPES
from export_dashboard import ExportDashboardData, find_export_file, load_export_dashboard
from exporter import run_export
from models import Chat, ExtractedEntity, Message, User

PRIVATE_CHAT_TYPE = "private chat"
PAGE_NAMES: tuple[str, ...] = (
    "Overview",
    "Chats",
    "Messages",
    "Keywords",
    "Analytics",
    "Entities",
    "Search",
    "Export",
)
LINK_ENTITY_TYPES: frozenset[str] = frozenset({"url", "domain", "email", "phone"})


@dataclass(frozen=True)
class OverviewMetrics:
    """High-level counts shown on the dashboard home page."""

    total_messages: int
    total_chats: int
    flagged_chats: int
    total_entities: int
    keyword_flag_count: int
    content_entity_count: int
    private_chat_count: int
    unique_senders: int


@dataclass(frozen=True)
class DashboardFilters:
    """Shared filters applied across dashboard pages."""

    chat_ids: tuple[int, ...]
    categories: tuple[str, ...]
    include_private: bool
    chat_type: str | None
    min_messages: int
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True)
class DashboardInsights:
    """Auto-generated highlights from the current filtered dataset."""

    busiest_chat: str | None
    busiest_chat_messages: int
    top_keyword: str | None
    top_keyword_count: int
    top_category: str | None
    top_category_count: int
    multi_flag_messages: int
    earliest_message: str | None
    latest_message: str | None
    private_share_pct: float


@dataclass(frozen=True)
class StoredChatOption:
    """A chat available for dashboard filtering."""

    chat_id: int
    title: str
    chat_type: str
    message_count: int


def database_available(settings: Settings) -> bool:
    """Return True when the configured SQLite database file exists."""
    try:
        return settings.database_path.is_file()
    except ValueError:
        return False


def default_filters() -> DashboardFilters:
    """Return default dashboard filter values."""
    return DashboardFilters(
        chat_ids=(),
        categories=(),
        include_private=True,
        chat_type=None,
        min_messages=0,
        date_from=None,
        date_to=None,
    )


def _date_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _date_end(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _apply_message_filters(
    stmt: Any,
    filters: DashboardFilters,
    *,
    chat_joined: bool = False,
) -> Any:
    """Apply shared dashboard filters to a message query."""
    if filters.chat_ids:
        stmt = stmt.where(Message.chat_id.in_(filters.chat_ids))
    if filters.date_from:
        stmt = stmt.where(Message.timestamp >= _date_start(filters.date_from))
    if filters.date_to:
        stmt = stmt.where(Message.timestamp <= _date_end(filters.date_to))

    needs_chat = (
        not filters.include_private
        or (filters.chat_type and filters.chat_type != "All")
    )
    if needs_chat and not chat_joined:
        stmt = stmt.join(Chat, Chat.id == Message.chat_id, isouter=True)
        chat_joined = True

    if not filters.include_private:
        stmt = stmt.where(
            (Chat.chat_type.is_(None)) | (Chat.chat_type != PRIVATE_CHAT_TYPE)
        )
    if filters.chat_type and filters.chat_type != "All":
        stmt = stmt.where(Chat.chat_type == filters.chat_type)
    return stmt


def get_message_timestamp_bounds(session: Session) -> tuple[date | None, date | None]:
    """Return earliest and latest stored message dates."""
    earliest = session.scalar(select(func.min(Message.timestamp)).where(Message.timestamp.is_not(None)))
    latest = session.scalar(select(func.max(Message.timestamp)).where(Message.timestamp.is_not(None)))
    if earliest is None or latest is None:
        return None, None
    return earliest.date(), latest.date()


def get_stored_chat_options(
    session: Session,
    *,
    include_private: bool = True,
) -> list[StoredChatOption]:
    """Return every chat in SQLite with stored message counts."""
    stmt = (
        select(
            Chat.id,
            Chat.title,
            Chat.chat_type,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.chat_id == Chat.id)
        .group_by(Chat.id, Chat.title, Chat.chat_type)
        .order_by(func.count(Message.id).desc(), Chat.title)
    )
    if not include_private:
        stmt = stmt.where(
            (Chat.chat_type.is_(None)) | (Chat.chat_type != PRIVATE_CHAT_TYPE)
        )

    options: list[StoredChatOption] = []
    for chat_id, title, chat_type, message_count in session.execute(stmt).all():
        count = int(message_count or 0)
        if count == 0:
            continue
        options.append(
            StoredChatOption(
                chat_id=int(chat_id),
                title=title or f"Chat {chat_id}",
                chat_type=chat_type or "unknown",
                message_count=count,
            )
        )
    return options


def _message_ids_matching_categories(
    session: Session,
    categories: tuple[str, ...],
) -> set[int] | None:
    """Return message row IDs that match selected keyword categories."""
    if not categories:
        return None

    ids = session.scalars(
        select(ExtractedEntity.message_row_id)
        .where(ExtractedEntity.entity_type.in_(categories))
        .distinct()
    ).all()
    return set(ids)


def get_detailed_chat_summaries(
    session: Session,
    filters: DashboardFilters,
) -> list[dict[str, Any]]:
    """Return per-chat stats including keyword category breakdowns."""
    chat_options = get_stored_chat_options(session, include_private=filters.include_private)
    if filters.chat_ids:
        allowed = set(filters.chat_ids)
        chat_options = [chat for chat in chat_options if chat.chat_id in allowed]
    if filters.chat_type and filters.chat_type != "All":
        chat_options = [chat for chat in chat_options if chat.chat_type == filters.chat_type]
    if filters.min_messages > 0:
        chat_options = [
            chat for chat in chat_options if chat.message_count >= filters.min_messages
        ]

    rows: list[dict[str, Any]] = []
    for chat in chat_options:
        category_counts = dict.fromkeys(KEYWORD_ENTITY_TYPES, 0)
        stmt = (
            select(ExtractedEntity.entity_type, func.count(ExtractedEntity.id))
            .join(Message, Message.id == ExtractedEntity.message_row_id)
            .where(
                Message.chat_id == chat.chat_id,
                ExtractedEntity.entity_type.in_(tuple(KEYWORD_ENTITY_TYPES)),
            )
            .group_by(ExtractedEntity.entity_type)
        )
        for entity_type, count in session.execute(stmt).all():
            category_counts[str(entity_type)] = int(count)

        entity_count = int(
            session.scalar(
                select(func.count(ExtractedEntity.id))
                .join(Message, Message.id == ExtractedEntity.message_row_id)
                .where(Message.chat_id == chat.chat_id)
            )
            or 0
        )

        rows.append(
            {
                "chat_id": chat.chat_id,
                "title": chat.title,
                "chat_type": chat.chat_type,
                "messages": chat.message_count,
                "entities": entity_count,
                "narcotics": category_counts["narcotics"],
                "human_trafficking": category_counts["human_trafficking"],
                "firearms": category_counts["firearms"],
            }
        )
    return rows


def get_overview_metrics(session: Session, summary: AnalyticsSummary) -> OverviewMetrics:
    """Compute overview metrics from the database and analytics summary."""
    total_chats = int(session.scalar(select(func.count()).select_from(Chat)) or 0)
    flagged_chats = len(get_stored_chat_options(session, include_private=True))
    total_entities = int(
        session.scalar(select(func.count()).select_from(ExtractedEntity)) or 0
    )
    content_entity_count = int(
        session.scalar(
            select(func.count())
            .select_from(ExtractedEntity)
            .where(ExtractedEntity.entity_type.in_(tuple(CONTENT_ENTITY_TYPES)))
        )
        or 0
    )
    private_chat_count = int(
        session.scalar(
            select(func.count())
            .select_from(Chat)
            .where(Chat.chat_type == PRIVATE_CHAT_TYPE)
        )
        or 0
    )
    unique_senders = int(
        session.scalar(
            select(func.count(func.distinct(Message.sender_id))).where(
                Message.sender_id.is_not(None)
            )
        )
        or 0
    )
    keyword_flag_count = sum(item.count for item in summary.keyword_flags)
    return OverviewMetrics(
        total_messages=summary.total_messages,
        total_chats=total_chats,
        flagged_chats=flagged_chats,
        total_entities=total_entities,
        keyword_flag_count=keyword_flag_count,
        content_entity_count=content_entity_count,
        private_chat_count=private_chat_count,
        unique_senders=unique_senders,
    )


def get_chat_table_rows(
    session: Session,
    *,
    include_private: bool = False,
) -> list[dict[str, Any]]:
    """Return chat rows with stored message counts for tabular display."""
    return get_detailed_chat_summaries(
        session,
        DashboardFilters(
            chat_ids=(),
            categories=(),
            include_private=include_private,
            chat_type=None,
            min_messages=0,
        ),
    )


def get_message_rows(
    session: Session,
    filters: DashboardFilters,
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return flagged messages with keyword and entity context."""
    category_message_ids = _message_ids_matching_categories(session, filters.categories)

    stmt = (
        select(Message, Chat.title, Chat.chat_type, User.username, User.first_name)
        .join(Chat, Chat.id == Message.chat_id, isouter=True)
        .join(User, User.id == Message.sender_id, isouter=True)
        .order_by(Message.timestamp.desc(), Message.id.desc())
        .limit(limit)
    )
    stmt = _apply_message_filters(stmt, filters, chat_joined=True)

    rows: list[dict[str, Any]] = []
    for message, chat_title, chat_type, username, first_name in session.execute(stmt).all():
        if category_message_ids is not None and message.id not in category_message_ids:
            continue

        keywords = session.scalars(
            select(ExtractedEntity.entity_value)
            .where(
                ExtractedEntity.message_row_id == message.id,
                ExtractedEntity.entity_type.in_(tuple(KEYWORD_ENTITY_TYPES)),
            )
            .order_by(ExtractedEntity.entity_type, ExtractedEntity.entity_value)
        ).all()
        categories = session.scalars(
            select(ExtractedEntity.entity_type)
            .where(
                ExtractedEntity.message_row_id == message.id,
                ExtractedEntity.entity_type.in_(tuple(KEYWORD_ENTITY_TYPES)),
            )
            .distinct()
            .order_by(ExtractedEntity.entity_type)
        ).all()
        entity_count = int(
            session.scalar(
                select(func.count())
                .select_from(ExtractedEntity)
                .where(ExtractedEntity.message_row_id == message.id)
            )
            or 0
        )

        sender = username or first_name or ""
        if username and first_name:
            sender = f"{first_name} (@{username})"

        rows.append(
            {
                "chat_id": message.chat_id,
                "chat": chat_title or f"Chat {message.chat_id}",
                "chat_type": chat_type or "unknown",
                "message_id": message.message_id,
                "timestamp": _format_timestamp(message.timestamp),
                "sender": sender,
                "categories": ", ".join(categories),
                "keywords": ", ".join(keywords),
                "entities": entity_count,
                "views": message.views if message.views is not None else "",
                "media_type": message.media_type or "",
                "text": message.text or "",
            }
        )

    if filters.min_messages > 0:
        counts_by_chat = {row["chat_id"]: 0 for row in rows}
        for row in rows:
            counts_by_chat[row["chat_id"]] = counts_by_chat.get(row["chat_id"], 0) + 1
        allowed_chats = {
            chat_id for chat_id, count in counts_by_chat.items() if count >= filters.min_messages
        }
        rows = [row for row in rows if row["chat_id"] in allowed_chats]

    return rows


def get_chat_type_breakdown(
    session: Session,
    filters: DashboardFilters,
) -> list[dict[str, Any]]:
    """Return flagged message counts grouped by chat type."""
    stmt = (
        select(Chat.chat_type, func.count(Message.id))
        .join(Message, Message.chat_id == Chat.id)
        .group_by(Chat.chat_type)
        .order_by(func.count(Message.id).desc())
    )
    stmt = _apply_message_filters(stmt, filters, chat_joined=True)
    rows: list[dict[str, Any]] = []
    for chat_type, count in session.execute(stmt).all():
        rows.append(
            {
                "chat_type": chat_type or "unknown",
                "messages": int(count),
            }
        )
    return rows


def get_top_keyword_term_rows(
    session: Session,
    filters: DashboardFilters,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return the most frequent keyword term values."""
    stmt = (
        select(ExtractedEntity.entity_type, ExtractedEntity.entity_value, func.count())
        .join(Message, Message.id == ExtractedEntity.message_row_id)
        .where(ExtractedEntity.entity_type.in_(tuple(KEYWORD_ENTITY_TYPES)))
        .group_by(ExtractedEntity.entity_type, ExtractedEntity.entity_value)
        .order_by(func.count().desc())
        .limit(limit)
    )
    if filters.categories:
        stmt = stmt.where(ExtractedEntity.entity_type.in_(filters.categories))
    stmt = _apply_message_filters(stmt, filters, chat_joined=False)
    return [
        {
            "category": entity_type,
            "term": entity_value,
            "count": int(count),
        }
        for entity_type, entity_value, count in session.execute(stmt).all()
    ]


def get_sender_activity_rows(
    session: Session,
    filters: DashboardFilters,
    *,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Return senders ranked by flagged message volume."""
    stmt = (
        select(
            User.id,
            User.username,
            User.first_name,
            func.count(Message.id),
        )
        .join(Message, Message.sender_id == User.id)
        .group_by(User.id, User.username, User.first_name)
        .order_by(func.count(Message.id).desc())
        .limit(limit)
    )
    stmt = _apply_message_filters(stmt, filters, chat_joined=False)
    rows: list[dict[str, Any]] = []
    for user_id, username, first_name, count in session.execute(stmt).all():
        label = username or first_name or f"User {user_id}"
        if username and first_name:
            label = f"{first_name} (@{username})"
        rows.append(
            {
                "sender": label,
                "sender_id": int(user_id),
                "messages": int(count),
            }
        )
    return rows


def get_media_type_breakdown(
    session: Session,
    filters: DashboardFilters,
) -> list[dict[str, Any]]:
    """Return message counts grouped by media type."""
    media_label = func.coalesce(Message.media_type, "text only")
    stmt = (
        select(media_label, func.count(Message.id))
        .group_by(media_label)
        .order_by(func.count(Message.id).desc())
    )
    stmt = _apply_message_filters(stmt, filters, chat_joined=False)
    return [
        {"media_type": str(label), "messages": int(count)}
        for label, count in session.execute(stmt).all()
    ]


def get_multi_category_message_rows(
    session: Session,
    filters: DashboardFilters,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return messages that matched more than one keyword category."""
    rows = get_message_rows(session, filters, limit=limit * 4)
    multi_flag: list[dict[str, Any]] = []
    for row in rows:
        categories = [part.strip() for part in str(row.get("categories", "")).split(",") if part.strip()]
        if len(set(categories)) > 1:
            multi_flag.append(row)
        if len(multi_flag) >= limit:
            break
    return multi_flag


def get_link_entity_rows(
    session: Session,
    filters: DashboardFilters,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return URL, domain, email, and phone entities."""
    rows = get_entity_table_rows(session, filters, entity_type=None, limit=limit * 4)
    return [row for row in rows if str(row.get("entity_type")) in LINK_ENTITY_TYPES][:limit]


def get_dashboard_insights(
    session: Session,
    filters: DashboardFilters,
) -> DashboardInsights:
    """Compute quick insight highlights for the overview page."""
    chat_rows = get_detailed_chat_summaries(session, filters)
    term_rows = get_top_keyword_term_rows(session, filters, limit=1)
    category_rows = get_category_summary_rows(session, filters)
    message_rows = get_message_rows(session, filters, limit=5000)
    multi_flag = get_multi_category_message_rows(session, filters, limit=5000)

    busiest_chat = None
    busiest_chat_messages = 0
    if chat_rows:
        top_chat = max(chat_rows, key=lambda row: int(row["messages"]))
        busiest_chat = str(top_chat["title"])
        busiest_chat_messages = int(top_chat["messages"])

    top_keyword = term_rows[0]["term"] if term_rows else None
    top_keyword_count = term_rows[0]["count"] if term_rows else 0
    top_category = category_rows[0]["category"] if category_rows else None
    top_category_count = category_rows[0]["count"] if category_rows else 0

    timestamps = [row["timestamp"] for row in message_rows if row.get("timestamp")]
    timestamps.sort()
    private_messages = sum(
        int(row["messages"])
        for row in chat_rows
        if row.get("chat_type") == PRIVATE_CHAT_TYPE
    )
    total_messages = sum(int(row["messages"]) for row in chat_rows)
    private_share = (private_messages / total_messages * 100.0) if total_messages else 0.0

    return DashboardInsights(
        busiest_chat=busiest_chat,
        busiest_chat_messages=busiest_chat_messages,
        top_keyword=top_keyword,
        top_keyword_count=top_keyword_count,
        top_category=top_category,
        top_category_count=top_category_count,
        multi_flag_messages=len(multi_flag),
        earliest_message=timestamps[0] if timestamps else None,
        latest_message=timestamps[-1] if timestamps else None,
        private_share_pct=round(private_share, 1),
    )


def timeline_from_message_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group message rows by calendar day for charting."""
    counts: dict[str, int] = {}
    for row in rows:
        timestamp = str(row.get("timestamp") or "")
        day = timestamp[:10] if len(timestamp) >= 10 else "unknown"
        if day == "unknown":
            continue
        counts[day] = counts.get(day, 0) + 1
    return [{"date": day, "messages": count} for day, count in sorted(counts.items())]


def top_terms_from_entity_rows(
    entities: list[dict[str, Any]],
    *,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Aggregate top keyword terms from export entity rows."""
    counts: dict[tuple[str, str], int] = {}
    for entity in entities:
        entity_type = str(entity.get("entity_type") or "")
        if entity_type not in KEYWORD_ENTITY_TYPES:
            continue
        key = (entity_type, str(entity.get("entity_value") or ""))
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    return [
        {"category": key[0], "term": key[1], "count": count}
        for key, count in ranked[:limit]
    ]


def chat_type_breakdown_from_summaries(
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate message counts by chat type from summary rows."""
    counts: dict[str, int] = {}
    for summary in summaries:
        chat_type = str(summary.get("chat_type") or "unknown")
        counts[chat_type] = counts.get(chat_type, 0) + int(summary.get("messages") or 0)
    return [
        {"chat_type": chat_type, "messages": count}
        for chat_type, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def get_category_summary_rows(session: Session, filters: DashboardFilters) -> list[dict[str, Any]]:
    """Return keyword category totals, optionally filtered by chat."""
    stmt = (
        select(ExtractedEntity.entity_type, func.count(ExtractedEntity.id))
        .join(Message, Message.id == ExtractedEntity.message_row_id)
        .where(ExtractedEntity.entity_type.in_(tuple(KEYWORD_ENTITY_TYPES)))
        .group_by(ExtractedEntity.entity_type)
        .order_by(func.count(ExtractedEntity.id).desc())
    )
    if filters.categories:
        stmt = stmt.where(ExtractedEntity.entity_type.in_(filters.categories))
    stmt = _apply_message_filters(stmt, filters, chat_joined=False)
    return [
        {"category": entity_type, "count": int(count)}
        for entity_type, count in session.execute(stmt).all()
    ]


def list_entity_types(session: Session) -> list[str]:
    """Return distinct entity types present in the database."""
    values = session.scalars(
        select(ExtractedEntity.entity_type)
        .distinct()
        .order_by(ExtractedEntity.entity_type)
    ).all()
    return list(values)


def get_entity_table_rows(
    session: Session,
    filters: DashboardFilters,
    *,
    entity_type: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return entity rows joined with chat context for tabular display."""
    stmt = (
        select(
            ExtractedEntity.entity_type,
            ExtractedEntity.entity_value,
            Message.message_id,
            Message.chat_id,
            Chat.title,
            Chat.chat_type,
            Message.timestamp,
        )
        .join(Message, Message.id == ExtractedEntity.message_row_id)
        .join(Chat, Chat.id == Message.chat_id, isouter=True)
        .order_by(Message.timestamp.desc(), ExtractedEntity.id.desc())
        .limit(limit)
    )
    if entity_type:
        stmt = stmt.where(ExtractedEntity.entity_type == entity_type)
    if filters.chat_ids:
        stmt = stmt.where(Message.chat_id.in_(filters.chat_ids))
    if filters.categories:
        stmt = stmt.where(ExtractedEntity.entity_type.in_(filters.categories))
    if not filters.include_private:
        stmt = stmt.where(
            (Chat.chat_type.is_(None)) | (Chat.chat_type != PRIVATE_CHAT_TYPE)
        )

    rows: list[dict[str, Any]] = []
    for (
        entity_kind,
        value,
        message_id,
        chat_id,
        chat_title,
        chat_type,
        timestamp,
    ) in session.execute(stmt).all():
        rows.append(
            {
                "entity_type": entity_kind,
                "entity_value": value,
                "message_id": message_id,
                "chat_id": chat_id,
                "chat": chat_title or f"Chat {chat_id}",
                "chat_type": chat_type or "unknown",
                "timestamp": _format_timestamp(timestamp),
            }
        )
    return rows


def search_messages_filtered(
    session: Session,
    engine: AnalyticsEngine,
    query: str,
    filters: DashboardFilters,
    *,
    limit: int = 100,
) -> list[SearchHit]:
    """Search messages and apply dashboard chat/category filters."""
    hits = engine.search_messages(query, limit=limit)
    if not hits:
        return hits

    filtered: list[SearchHit] = []
    for hit in hits:
        if filters.chat_ids and hit.chat_id not in filters.chat_ids:
            continue

        chat_type = session.scalar(select(Chat.chat_type).where(Chat.id == hit.chat_id))
        if not filters.include_private and chat_type == PRIVATE_CHAT_TYPE:
            continue
        if filters.chat_type and filters.chat_type != "All" and chat_type != filters.chat_type:
            continue

        if filters.categories:
            matched = session.scalar(
                select(func.count())
                .select_from(ExtractedEntity)
                .where(
                    ExtractedEntity.message_row_id == hit.message_row_id,
                    ExtractedEntity.entity_type.in_(filters.categories),
                )
            )
            if not int(matched or 0):
                continue

        filtered.append(hit)
    return filtered


def search_hits_as_rows(hits: list[SearchHit]) -> list[dict[str, Any]]:
    """Convert search hits into rows suitable for a dataframe."""
    return [
        {
            "chat_id": hit.chat_id,
            "chat": hit.chat_title or hit.chat_id,
            "message_id": hit.message_id,
            "timestamp": _format_timestamp(hit.timestamp),
            "text": hit.text or "",
        }
        for hit in hits
    ]


def ranked_counts_as_rows(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    """Convert ranked analytics items into label/count rows."""
    return [
        {
            "label": item.label,
            "count": item.count,
            **({"detail": item.detail} if item.detail else {}),
        }
        for item in items
    ]


def messages_per_chat_chart(chat_rows: list[dict[str, Any]]) -> go.Figure:
    """Build a bar chart of flagged messages per chat."""
    labels = [row["title"] for row in chat_rows]
    counts = [row["messages"] for row in chat_rows]
    figure = go.Figure(data=[go.Bar(x=labels, y=counts, name="Messages")])
    figure.update_layout(
        title="Flagged Messages Per Chat",
        xaxis_title="Chat",
        yaxis_title="Messages",
        template="plotly_white",
    )
    return figure


def keyword_category_chart(category_rows: list[dict[str, Any]]) -> go.Figure:
    """Build a bar chart for keyword category totals."""
    labels = [row["category"] for row in category_rows]
    counts = [row["count"] for row in category_rows]
    figure = go.Figure(data=[go.Bar(x=labels, y=counts, name="Flags")])
    figure.update_layout(
        title="Keyword Flags By Category",
        xaxis_title="Category",
        yaxis_title="Count",
        template="plotly_white",
    )
    return figure


def category_by_chat_stacked_chart(chat_rows: list[dict[str, Any]]) -> go.Figure:
    """Build a stacked bar chart of keyword categories per chat."""
    labels = [row["title"] for row in chat_rows]
    figure = go.Figure()
    for category, color in (
        ("narcotics", "#ef4444"),
        ("firearms", "#3b82f6"),
        ("human_trafficking", "#f97316"),
    ):
        figure.add_trace(
            go.Bar(
                name=category.replace("_", " ").title(),
                x=labels,
                y=[int(row.get(category, 0)) for row in chat_rows],
                marker_color=color,
            )
        )
    figure.update_layout(
        barmode="stack",
        title="Keyword Categories by Chat",
        xaxis_title="Chat",
        yaxis_title="Flag Count",
        template="plotly_white",
    )
    return figure


def chat_type_pie_chart(breakdown_rows: list[dict[str, Any]]) -> go.Figure:
    """Build a pie chart for message share by chat type."""
    labels = [row["chat_type"] for row in breakdown_rows]
    values = [row["messages"] for row in breakdown_rows]
    figure = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.35)])
    figure.update_layout(title="Messages by Chat Type", template="plotly_white")
    return figure


def top_keyword_terms_chart(term_rows: list[dict[str, Any]]) -> go.Figure:
    """Build a horizontal bar chart for top keyword terms."""
    labels = [f"{row['term']} ({row['category']})" for row in reversed(term_rows)]
    counts = [row["count"] for row in reversed(term_rows)]
    figure = go.Figure(data=[go.Bar(x=counts, y=labels, orientation="h", name="Terms")])
    figure.update_layout(
        title="Top Keyword Terms",
        xaxis_title="Occurrences",
        yaxis_title="Term",
        template="plotly_white",
        height=max(320, len(term_rows) * 28),
    )
    return figure


def filtered_timeline_chart(timeline_rows: list[dict[str, Any]]) -> go.Figure:
    """Build a timeline chart from filtered message rows."""
    labels = [row["date"] for row in timeline_rows]
    counts = [row["messages"] for row in timeline_rows]
    figure = go.Figure(
        data=[go.Scatter(x=labels, y=counts, mode="lines+markers", name="Messages")],
    )
    figure.update_layout(
        title="Flagged Messages Over Time",
        xaxis_title="Date",
        yaxis_title="Messages",
        template="plotly_white",
    )
    return figure


def list_export_files(exports_dir: Path) -> list[Path]:
    """Return export files sorted by name."""
    if not exports_dir.is_dir():
        return []
    return sorted(path for path in exports_dir.iterdir() if path.is_file())


def dataframe_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Convert row dictionaries to CSV bytes for download buttons."""
    frame = pd.DataFrame(rows)
    return frame.to_csv(index=False).encode("utf-8")


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat(sep=" ", timespec="seconds")


def _apply_streamlit_secrets() -> None:
    """Copy Streamlit Cloud secrets into environment variables."""
    try:
        import streamlit as st

        for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE"):
            if key in st.secrets and str(st.secrets[key]).strip():
                import os

                os.environ[key] = str(st.secrets[key]).strip()
    except Exception:
        return


def _load_settings_or_none() -> Settings | None:
    _apply_streamlit_secrets()
    try:
        return ensure_directories()
    except ValueError:
        pass

    try:
        settings = ensure_directories(load_minimal_settings())
        if find_export_file(settings):
            return settings
    except ValueError:
        return None
    return None


def _render_export_dashboard(st: Any, settings: Settings, export_data: ExportDashboardData) -> None:
    st.sidebar.title("Telegram Scraper")
    st.sidebar.caption("Streamlit Cloud · export.json mode")
    page = st.sidebar.radio(
        "Navigate",
        ("Overview", "Chats", "Messages", "Keywords", "Analytics", "Entities", "Search"),
        label_visibility="collapsed",
    )

    messages = list(export_data.messages)
    chat_summaries = list(export_data.chat_summaries)
    entities = list(export_data.entities)
    category_rows = list(export_data.category_counts)
    term_rows = top_terms_from_entity_rows(entities, limit=20)
    chat_type_rows = chat_type_breakdown_from_summaries(chat_summaries)
    timeline_rows = timeline_from_message_rows(messages)

    st.info(
        f"Showing exported data from `{export_data.source_path}`. "
        "Scrape locally, run `streamlit_export.bat`, commit `demo/export.json`, and redeploy to refresh."
    )

    if page == "Overview":
        st.header("Overview")
        cols = st.columns(4)
        cols[0].metric("Flagged messages", len(messages))
        cols[1].metric("Flagged chats", len(chat_summaries))
        cols[2].metric("Keyword categories", len(category_rows))
        cols[3].metric("Entities", len(entities))
        st.caption(f"Exported at: {export_data.exported_at}")
        if term_rows:
            st.metric("Top keyword", term_rows[0]["term"], term_rows[0]["count"])
        left, right = st.columns(2)
        with left:
            st.subheader("Chats")
            st.dataframe(pd.DataFrame(chat_summaries), use_container_width=True, hide_index=True)
            if chat_summaries:
                st.plotly_chart(messages_per_chat_chart(chat_summaries), use_container_width=True)
        with right:
            st.subheader("Keyword categories")
            st.dataframe(pd.DataFrame(category_rows), use_container_width=True, hide_index=True)
            if category_rows:
                st.plotly_chart(keyword_category_chart(category_rows), use_container_width=True)
        if timeline_rows:
            st.plotly_chart(filtered_timeline_chart(timeline_rows), use_container_width=True)
        if chat_type_rows:
            st.plotly_chart(chat_type_pie_chart(chat_type_rows), use_container_width=True)
        st.subheader("Recent messages")
        st.dataframe(pd.DataFrame(messages[:25]), use_container_width=True, hide_index=True)
    elif page == "Chats":
        st.header("Chats")
        st.dataframe(pd.DataFrame(chat_summaries), use_container_width=True, hide_index=True)
        if chat_summaries:
            st.plotly_chart(category_by_chat_stacked_chart(chat_summaries), use_container_width=True)
    elif page == "Messages":
        st.header("Messages")
        st.dataframe(pd.DataFrame(messages), use_container_width=True, hide_index=True)
        with st.expander("Expanded message view"):
            for row in messages[:50]:
                st.markdown(f"**{row['chat']}** · `{row.get('timestamp', '')}` · flags: {row.get('keywords', '')}")
                st.write(row.get("text") or "(no text)")
                st.divider()
    elif page == "Keywords":
        st.header("Keywords")
        if category_rows:
            st.plotly_chart(keyword_category_chart(category_rows), use_container_width=True)
        if chat_summaries:
            st.plotly_chart(category_by_chat_stacked_chart(chat_summaries), use_container_width=True)
        if term_rows:
            st.plotly_chart(top_keyword_terms_chart(term_rows), use_container_width=True)
            st.dataframe(pd.DataFrame(term_rows), use_container_width=True, hide_index=True)
    elif page == "Analytics":
        st.header("Analytics")
        if timeline_rows:
            st.plotly_chart(filtered_timeline_chart(timeline_rows), use_container_width=True)
        if chat_summaries:
            st.plotly_chart(messages_per_chat_chart(chat_summaries), use_container_width=True)
        link_rows = [row for row in entities if str(row.get("entity_type")) in LINK_ENTITY_TYPES]
        keyword_rows = [row for row in entities if str(row.get("entity_type")) in KEYWORD_ENTITY_TYPES]
        left, right = st.columns(2)
        with left:
            st.subheader("Link entities")
            st.dataframe(pd.DataFrame(link_rows[:100]), use_container_width=True, hide_index=True)
        with right:
            st.subheader("Keyword entities")
            st.dataframe(pd.DataFrame(keyword_rows[:100]), use_container_width=True, hide_index=True)
    elif page == "Entities":
        st.header("Entities")
        st.dataframe(pd.DataFrame(entities), use_container_width=True, hide_index=True)
    else:
        st.header("Search")
        query = st.text_input("Search message text")
        rows = list(messages)
        if query.strip():
            needle = query.strip().lower()
            rows = [row for row in rows if needle in str(row.get("text", "")).lower()]
        st.write(f"{len(rows)} result(s)")
        st.dataframe(pd.DataFrame(rows[:200]), use_container_width=True, hide_index=True)


def _with_session(settings: Settings, callback: Callable[[Session, AnalyticsEngine], None]) -> None:
    init_db(settings)
    with get_session(settings) as session:
        callback(session, AnalyticsEngine(session))


def _init_session_state(st: Any) -> None:
    if "filters" not in st.session_state:
        st.session_state.filters = default_filters()


def _render_sidebar_filters(st: Any, session: Session) -> DashboardFilters:
    _init_session_state(st)

    st.sidebar.markdown("### Filters")
    if st.sidebar.button("Refresh data", use_container_width=True):
        st.rerun()

    include_private = st.sidebar.checkbox(
        "Include private chats",
        value=st.session_state.filters.include_private,
    )

    chat_options = get_stored_chat_options(session, include_private=include_private)
    chat_labels = {
        f"{chat.title} ({chat.message_count} msgs)": chat.chat_id for chat in chat_options
    }
    selected_labels = st.sidebar.multiselect(
        "Chats",
        options=list(chat_labels.keys()),
        default=list(chat_labels.keys()),
        help="Each scrape run stores one chat. Select multiple to compare channels/groups.",
    )
    selected_chat_ids = tuple(chat_labels[label] for label in selected_labels)

    categories = st.sidebar.multiselect(
        "Keyword categories",
        options=sorted(KEYWORD_ENTITY_TYPES),
        default=[],
        help="Leave empty to include all keyword categories.",
    )

    chat_types = ["All"] + sorted({chat.chat_type for chat in chat_options})
    chat_type = st.sidebar.selectbox("Chat type", options=chat_types, index=0)

    min_messages = st.sidebar.slider(
        "Minimum messages per chat",
        min_value=0,
        max_value=max((chat.message_count for chat in chat_options), default=0),
        value=0,
    )

    earliest, latest = get_message_timestamp_bounds(session)
    use_date_filter = st.sidebar.checkbox("Filter by date range", value=False)
    date_from = date_to = None
    if use_date_filter and earliest and latest:
        picked = st.sidebar.date_input(
            "Date range",
            value=(earliest, latest),
            min_value=earliest,
            max_value=latest,
        )
        if isinstance(picked, tuple) and len(picked) == 2:
            date_from, date_to = picked

    filters = DashboardFilters(
        chat_ids=selected_chat_ids,
        categories=tuple(categories),
        include_private=include_private,
        chat_type=chat_type,
        min_messages=min_messages,
        date_from=date_from,
        date_to=date_to,
    )
    st.session_state.filters = filters

    st.sidebar.markdown("### Collection")
    st.sidebar.caption(
        "Each Telegram DM is a **separate chat**. To collect dummy texts from multiple people, run:\n\n"
        "`scrape_all.bat` or `message_scraper.py all-private 1000`"
    )
    if len(chat_options) <= 1:
        st.sidebar.warning("Only 1 flagged chat in SQLite. Scrape another channel to compare.")

    return filters


def render_dashboard() -> None:
    """Render the Streamlit dashboard."""
    import streamlit as st

    st.set_page_config(
        page_title="Telegram Intelligence Scraper",
        page_icon="📊",
        layout="wide",
    )

    settings = _load_settings_or_none()
    if settings is None:
        st.error(
            "Configuration is incomplete. For Streamlit Cloud, add secrets in the app settings. "
            "For local use, copy `.env.example` to `.env` and fill in the values."
        )
        st.stop()

    export_path = find_export_file(settings)
    if export_path and not database_available(settings):
        export_data = load_export_dashboard(export_path)
        _render_export_dashboard(st, settings, export_data)
        return

    st.sidebar.title("Telegram Scraper")
    st.sidebar.caption("Local OSINT dashboard over stored SQLite data.")
    page = st.sidebar.radio("Navigate", PAGE_NAMES, label_visibility="collapsed")

    if not database_available(settings):
        st.warning(
            "No database found yet. Run `auth.bat`, then `scrape.bat` on a channel "
            "or group to collect flagged messages first."
        )
        if page != "Export":
            st.stop()

    init_db(settings)
    with get_session(settings) as session:
        filters = _render_sidebar_filters(st, session)

    page_handlers = {
        "Overview": _page_overview,
        "Chats": _page_chat_explorer,
        "Messages": _page_messages,
        "Keywords": _page_keywords,
        "Analytics": _page_analytics,
        "Entities": _page_entity_explorer,
        "Search": _page_search,
        "Export": _page_export,
    }
    page_handlers[page](settings, filters)


def _page_overview(settings: Settings, filters: DashboardFilters) -> None:
    import streamlit as st

    st.header("Overview")
    _with_session(
        settings,
        lambda session, engine: _render_overview(st, session, engine, filters),
    )


def _render_overview(
    st: Any,
    session: Session,
    engine: AnalyticsEngine,
    filters: DashboardFilters,
) -> None:
    summary = engine.build_summary()
    metrics = get_overview_metrics(session, summary)
    chat_rows = get_detailed_chat_summaries(session, filters)
    category_rows = get_category_summary_rows(session, filters)
    recent_messages = get_message_rows(session, filters, limit=25)
    insights = get_dashboard_insights(session, filters)
    chat_type_rows = get_chat_type_breakdown(session, filters)
    timeline_rows = timeline_from_message_rows(get_message_rows(session, filters, limit=2000))

    row1 = st.columns(4)
    row1[0].metric("Flagged messages", metrics.total_messages)
    row1[1].metric("Flagged chats", metrics.flagged_chats)
    row1[2].metric("Keyword flags", metrics.keyword_flag_count)
    row1[3].metric("Unique senders", metrics.unique_senders)

    row2 = st.columns(4)
    row2[0].metric("Total entities", metrics.total_entities)
    row2[1].metric("Content entities", metrics.content_entity_count)
    row2[2].metric("Private chats", metrics.private_chat_count)
    row2[3].metric("Filtered chats", len(chat_rows))

    if metrics.total_messages == 0:
        st.info("No flagged messages stored yet. Scrape a channel or group to populate the dashboard.")
        return

    if metrics.flagged_chats <= 1:
        st.info(
            "Only **one flagged chat** is stored. If your test texts are in DMs from different people, "
            "run **`scrape_all.bat`** to scan every private chat at once. Messages are only stored when "
            "they match keywords like `meth`, `cocaine`, or `ghost gun`."
        )

    if metrics.private_chat_count and not filters.include_private:
        st.warning(
            f"{metrics.private_chat_count} private chat(s) stored but hidden. "
            "Enable **Include private chats** in the sidebar to view them."
        )

    insight_cols = st.columns(4)
    insight_cols[0].metric("Busiest chat", insights.busiest_chat or "—")
    insight_cols[1].metric("Top keyword", insights.top_keyword or "—", insights.top_keyword_count)
    insight_cols[2].metric("Top category", insights.top_category or "—", insights.top_category_count)
    insight_cols[3].metric("Multi-flag msgs", insights.multi_flag_messages)
    if insights.earliest_message and insights.latest_message:
        st.caption(
            f"Filtered activity window: {insights.earliest_message} → {insights.latest_message} · "
            f"{insights.private_share_pct:.1f}% of flagged messages are from private chats"
        )

    left, right = st.columns(2)
    with left:
        if chat_rows:
            st.subheader("All flagged chats")
            st.dataframe(pd.DataFrame(chat_rows), use_container_width=True, hide_index=True)
            st.plotly_chart(messages_per_chat_chart(chat_rows), use_container_width=True)
        else:
            st.info("No chats match the current sidebar filters.")
    with right:
        if category_rows:
            st.subheader("Keyword categories")
            st.dataframe(pd.DataFrame(category_rows), use_container_width=True, hide_index=True)
            st.plotly_chart(keyword_category_chart(category_rows), use_container_width=True)
        st.subheader("Top keyword terms")
        term_rows = get_top_keyword_term_rows(session, filters, limit=10)
        if term_rows:
            st.dataframe(pd.DataFrame(term_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No keyword terms match the current filters.")

    if timeline_rows:
        st.subheader("Activity timeline")
        st.plotly_chart(filtered_timeline_chart(timeline_rows), use_container_width=True)

    bottom_left, bottom_right = st.columns(2)
    with bottom_left:
        if chat_type_rows:
            st.subheader("Chat type mix")
            st.plotly_chart(chat_type_pie_chart(chat_type_rows), use_container_width=True)
    with bottom_right:
        if chat_rows:
            st.subheader("Categories per chat")
            st.plotly_chart(category_by_chat_stacked_chart(chat_rows), use_container_width=True)

    st.subheader("Recent flagged messages")
    if recent_messages:
        st.dataframe(pd.DataFrame(recent_messages), use_container_width=True, hide_index=True)
    else:
        st.info("No messages match the current filters.")


def _page_chat_explorer(settings: Settings, filters: DashboardFilters) -> None:
    import streamlit as st

    st.header("Chats")
    st.caption("Detailed breakdown for every flagged chat currently stored in SQLite.")

    def render(session: Session, _engine: AnalyticsEngine) -> None:
        rows = get_detailed_chat_summaries(session, filters)
        if not rows:
            st.info("No chats match the current filters.")
            return

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.download_button(
            "Download chat summary CSV",
            data=dataframe_csv_bytes(rows),
            file_name="chat_summary.csv",
            mime="text/csv",
        )

        chat_ids = [row["chat_id"] for row in rows]
        selected_id = st.selectbox(
            "Inspect chat",
            options=chat_ids,
            format_func=lambda chat_id: next(
                row["title"] for row in rows if row["chat_id"] == chat_id
            ),
        )
        chat_messages = get_message_rows(
            session,
            DashboardFilters(
                chat_ids=(selected_id,),
                categories=filters.categories,
                include_private=filters.include_private,
                chat_type=filters.chat_type,
                min_messages=0,
            ),
            limit=200,
        )
        st.subheader("Messages in selected chat")
        st.dataframe(pd.DataFrame(chat_messages), use_container_width=True, hide_index=True)

    _with_session(settings, render)


def _page_messages(settings: Settings, filters: DashboardFilters) -> None:
    import streamlit as st

    st.header("Messages")
    limit = st.number_input("Max messages", min_value=10, max_value=2000, value=200, step=50)
    sort_by = st.selectbox("Sort by", ("Newest first", "Oldest first", "Chat name", "Most entities"))

    def render(session: Session, _engine: AnalyticsEngine) -> None:
        rows = get_message_rows(session, filters, limit=int(limit))
        if sort_by == "Oldest first":
            rows = sorted(rows, key=lambda row: str(row.get("timestamp", "")))
        elif sort_by == "Chat name":
            rows = sorted(rows, key=lambda row: (str(row.get("chat", "")), str(row.get("timestamp", ""))))
        elif sort_by == "Most entities":
            rows = sorted(rows, key=lambda row: int(row.get("entities", 0)), reverse=True)

        st.write(f"Showing {len(rows)} message(s)")
        if not rows:
            st.info("No messages match the current filters.")
            return

        st.download_button(
            "Download messages CSV",
            data=dataframe_csv_bytes(rows),
            file_name="filtered_messages.csv",
            mime="text/csv",
        )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("Expanded message view"):
            for row in rows[:50]:
                st.markdown(f"**{row['chat']}** · `{row['timestamp']}` · flags: {row['keywords']}")
                st.write(row["text"] or "(no text)")
                st.divider()

    _with_session(settings, render)


def _page_keywords(settings: Settings, filters: DashboardFilters) -> None:
    import streamlit as st

    st.header("Keywords")
    st.caption("Keyword term frequency, category mix, and multi-category hits.")

    def render(session: Session, _engine: AnalyticsEngine) -> None:
        term_rows = get_top_keyword_term_rows(session, filters, limit=20)
        category_rows = get_category_summary_rows(session, filters)
        chat_rows = get_detailed_chat_summaries(session, filters)
        multi_rows = get_multi_category_message_rows(session, filters, limit=50)

        if not term_rows and not category_rows:
            st.info("No keyword data matches the current filters.")
            return

        left, right = st.columns(2)
        with left:
            if category_rows:
                st.plotly_chart(keyword_category_chart(category_rows), use_container_width=True)
        with right:
            if chat_rows:
                st.plotly_chart(category_by_chat_stacked_chart(chat_rows), use_container_width=True)

        if term_rows:
            st.subheader("Top keyword terms")
            st.plotly_chart(top_keyword_terms_chart(term_rows), use_container_width=True)
            st.dataframe(pd.DataFrame(term_rows), use_container_width=True, hide_index=True)
            st.download_button(
                "Download keyword terms CSV",
                data=dataframe_csv_bytes(term_rows),
                file_name="keyword_terms.csv",
                mime="text/csv",
            )

        st.subheader("Multi-category messages")
        st.caption("Messages that matched more than one keyword category (e.g. narcotics + firearms).")
        if multi_rows:
            st.dataframe(pd.DataFrame(multi_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No multi-category messages in the current filter set.")

    _with_session(settings, render)


def _page_analytics(settings: Settings, filters: DashboardFilters) -> None:
    import streamlit as st

    st.header("Analytics")

    def render(session: Session, engine: AnalyticsEngine) -> None:
        summary = engine.build_summary()
        chat_rows = get_detailed_chat_summaries(session, filters)
        category_rows = get_category_summary_rows(session, filters)
        filtered_messages = get_message_rows(session, filters, limit=2000)
        timeline_rows = timeline_from_message_rows(filtered_messages)
        sender_rows = get_sender_activity_rows(session, filters)
        media_rows = get_media_type_breakdown(session, filters)

        if summary.total_messages == 0:
            st.info("No messages available for analytics.")
            return

        if timeline_rows:
            st.plotly_chart(filtered_timeline_chart(timeline_rows), use_container_width=True)
        else:
            st.plotly_chart(messages_per_day_chart(summary), use_container_width=True)
        st.plotly_chart(messages_per_hour_chart(summary), use_container_width=True)

        if chat_rows:
            st.plotly_chart(messages_per_chat_chart(chat_rows), use_container_width=True)
        if category_rows:
            st.plotly_chart(keyword_category_chart(category_rows), use_container_width=True)

        left, right = st.columns(2)
        with left:
            st.subheader("Top senders (filtered)")
            if sender_rows:
                st.dataframe(pd.DataFrame(sender_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No sender activity for the current filters.")
            st.subheader("Top domains")
            st.dataframe(
                ranked_counts_as_rows(summary.top_domains),
                use_container_width=True,
                hide_index=True,
            )
        with right:
            st.subheader("Top hashtags")
            st.dataframe(
                ranked_counts_as_rows(summary.top_hashtags),
                use_container_width=True,
                hide_index=True,
            )
            st.subheader("Top words")
            st.dataframe(
                ranked_counts_as_rows(summary.top_words),
                use_container_width=True,
                hide_index=True,
            )

        if media_rows:
            st.subheader("Media types")
            st.dataframe(pd.DataFrame(media_rows), use_container_width=True, hide_index=True)

    _with_session(settings, render)


def _page_entity_explorer(settings: Settings, filters: DashboardFilters) -> None:
    import streamlit as st

    st.header("Entities")
    entity_limit = st.number_input("Max entities", min_value=50, max_value=2000, value=500, step=50)
    view_mode = st.radio(
        "View",
        ("All entities", "Links & contacts", "Keyword flags only"),
        horizontal=True,
    )

    def render(session: Session, _engine: AnalyticsEngine) -> None:
        entity_types = list_entity_types(session)
        if not entity_types:
            st.info("No extracted entities yet.")
            return

        type_options = ["All"] + entity_types
        selected = st.selectbox("Entity type", type_options, index=0)
        entity_type = None if selected == "All" else selected

        rows = get_entity_table_rows(
            session,
            filters,
            entity_type=entity_type,
            limit=int(entity_limit),
        )
        if view_mode == "Links & contacts":
            rows = [row for row in rows if str(row.get("entity_type")) in LINK_ENTITY_TYPES]
        elif view_mode == "Keyword flags only":
            rows = [row for row in rows if str(row.get("entity_type")) in KEYWORD_ENTITY_TYPES]

        st.write(f"Showing {len(rows)} entity row(s)")
        if rows:
            st.download_button(
                "Download entities CSV",
                data=dataframe_csv_bytes(rows),
                file_name="filtered_entities.csv",
                mime="text/csv",
            )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No entities match the current filters.")

    _with_session(settings, render)


def _page_search(settings: Settings, filters: DashboardFilters) -> None:
    import streamlit as st

    st.header("Search")
    query = st.text_input("Search message text")
    limit = st.number_input("Max results", min_value=1, max_value=500, value=100, step=10)

    if not query.strip():
        st.caption("Enter a keyword or phrase to search stored messages.")
        return

    def render(session: Session, engine: AnalyticsEngine) -> None:
        hits = search_messages_filtered(
            session,
            engine,
            query,
            filters,
            limit=int(limit),
        )
        rows = search_hits_as_rows(hits)
        st.write(f"{len(rows)} result(s)")
        if rows:
            st.download_button(
                "Download search results CSV",
                data=dataframe_csv_bytes(rows),
                file_name="search_results.csv",
                mime="text/csv",
            )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No messages matched your query and filters.")

    _with_session(settings, render)


def _page_export(settings: Settings, _filters: DashboardFilters) -> None:
    import streamlit as st

    st.header("Export")
    st.caption("Generate CSV and JSON exports from the current SQLite database.")

    col1, col2 = st.columns(2)
    with col1:
        run_clicked = st.button("Run export now", type="primary", use_container_width=True)
    with col2:
        if st.button("Open exports folder tip", use_container_width=True):
            st.info(f"Exports are written to: `{settings.exports_dir}`")

    if run_clicked:
        try:
            result = run_export(settings)
        except OSError as exc:
            st.error(f"Export failed: {exc}")
            return

        st.success(
            f"Exported {result.message_count} message(s), "
            f"{result.entity_count} entity(ies), "
            f"{result.chat_count} chat(s)."
        )

    export_files = list_export_files(settings.exports_dir)
    if not export_files:
        st.info("No export files yet. Click **Run export now** to create them.")
        return

    st.subheader("Download files")
    for path in export_files:
        data = path.read_bytes()
        mime = "application/json" if path.suffix == ".json" else "text/csv"
        st.download_button(
            label=f"Download {path.name}",
            data=data,
            file_name=path.name,
            mime=mime,
            key=f"download-{path.name}",
        )


def main() -> None:
    """CLI entry point that launches Streamlit."""
    import subprocess
    import sys

    app_path = Path(__file__).resolve().parent / "app.py"
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(app_path),
                *sys.argv[1:],
            ]
        )
    )


if __name__ == "__main__":
    main()
