"""Streamlit dashboard helpers and page renderers for stored Telegram data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics import (
    AnalyticsEngine,
    AnalyticsSummary,
    SearchHit,
    messages_per_day_chart,
    messages_per_hour_chart,
)
from config import Settings, ensure_directories, load_settings
from database import get_session, init_db
from entity_extractor import CONTENT_ENTITY_TYPES, KEYWORD_ENTITY_TYPES
from exporter import run_export
from models import Chat, ExtractedEntity, Message

PRIVATE_CHAT_TYPE = "private chat"
PAGE_NAMES: tuple[str, ...] = (
    "Overview",
    "Chat Explorer",
    "Analytics",
    "Entity Explorer",
    "Search",
    "Export",
)


@dataclass(frozen=True)
class OverviewMetrics:
    """High-level counts shown on the dashboard home page."""

    total_messages: int
    total_chats: int
    total_entities: int
    keyword_flag_count: int
    private_chat_count: int


def database_available(settings: Settings) -> bool:
    """Return True when the configured SQLite database file exists."""
    try:
        return settings.database_path.is_file()
    except ValueError:
        return False


def get_overview_metrics(session: Session, summary: AnalyticsSummary) -> OverviewMetrics:
    """Compute overview metrics from the database and analytics summary."""
    total_chats = int(session.scalar(select(func.count()).select_from(Chat)) or 0)
    total_entities = int(
        session.scalar(select(func.count()).select_from(ExtractedEntity)) or 0
    )
    private_chat_count = int(
        session.scalar(
            select(func.count())
            .select_from(Chat)
            .where(Chat.chat_type == PRIVATE_CHAT_TYPE)
        )
        or 0
    )
    keyword_flag_count = sum(item.count for item in summary.keyword_flags)
    return OverviewMetrics(
        total_messages=summary.total_messages,
        total_chats=total_chats,
        total_entities=total_entities,
        keyword_flag_count=keyword_flag_count,
        private_chat_count=private_chat_count,
    )


def get_chat_table_rows(
    session: Session,
    *,
    include_private: bool = False,
) -> list[dict[str, Any]]:
    """Return chat rows with stored message counts for tabular display."""
    stmt = (
        select(
            Chat.id,
            Chat.title,
            Chat.username,
            Chat.chat_type,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.chat_id == Chat.id)
        .group_by(Chat.id, Chat.title, Chat.username, Chat.chat_type)
        .order_by(func.count(Message.id).desc(), Chat.title)
    )
    if not include_private:
        stmt = stmt.where(
            (Chat.chat_type.is_(None)) | (Chat.chat_type != PRIVATE_CHAT_TYPE)
        )

    rows: list[dict[str, Any]] = []
    for chat_id, title, username, chat_type, message_count in session.execute(stmt).all():
        rows.append(
            {
                "chat_id": chat_id,
                "title": title or f"Chat {chat_id}",
                "username": username or "",
                "chat_type": chat_type or "unknown",
                "message_count": int(message_count or 0),
            }
        )
    return rows


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
    *,
    entity_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return entity rows joined with chat context for tabular display."""
    stmt = (
        select(
            ExtractedEntity.entity_type,
            ExtractedEntity.entity_value,
            Message.message_id,
            Chat.title,
            Message.timestamp,
        )
        .join(Message, Message.id == ExtractedEntity.message_row_id)
        .join(Chat, Chat.id == Message.chat_id, isouter=True)
        .order_by(Message.timestamp.desc(), ExtractedEntity.id.desc())
        .limit(limit)
    )
    if entity_type:
        stmt = stmt.where(ExtractedEntity.entity_type == entity_type)

    rows: list[dict[str, Any]] = []
    for entity_kind, value, message_id, chat_title, timestamp in session.execute(stmt).all():
        rows.append(
            {
                "entity_type": entity_kind,
                "entity_value": value,
                "message_id": message_id,
                "chat": chat_title or "",
                "timestamp": _format_timestamp(timestamp),
            }
        )
    return rows


def search_hits_as_rows(hits: list[SearchHit]) -> list[dict[str, Any]]:
    """Convert search hits into rows suitable for a dataframe."""
    return [
        {
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


def list_export_files(exports_dir: Path) -> list[Path]:
    """Return export files sorted by name."""
    if not exports_dir.is_dir():
        return []
    return sorted(path for path in exports_dir.iterdir() if path.is_file())


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat(sep=" ", timespec="seconds")


def _load_settings_or_none() -> Settings | None:
    try:
        return ensure_directories()
    except ValueError:
        return None


def _with_session(settings: Settings, callback: Callable[[Session, AnalyticsEngine], None]) -> None:
    init_db(settings)
    with get_session(settings) as session:
        callback(session, AnalyticsEngine(session))


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
            "Configuration is incomplete. Copy `.env.example` to `.env` and fill in "
            "the required values before opening the dashboard."
        )
        st.stop()

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

    page_handlers = {
        "Overview": _page_overview,
        "Chat Explorer": _page_chat_explorer,
        "Analytics": _page_analytics,
        "Entity Explorer": _page_entity_explorer,
        "Search": _page_search,
        "Export": _page_export,
    }
    page_handlers[page](settings)


def _page_overview(settings: Settings) -> None:
    import streamlit as st

    st.header("Overview")
    _with_session(
        settings,
        lambda session, engine: _render_overview(st, session, engine),
    )


def _render_overview(st: Any, session: Session, engine: AnalyticsEngine) -> None:
    summary = engine.build_summary()
    metrics = get_overview_metrics(session, summary)

    cols = st.columns(5)
    cols[0].metric("Messages", metrics.total_messages)
    cols[1].metric("Chats", metrics.total_chats)
    cols[2].metric("Entities", metrics.total_entities)
    cols[3].metric("Keyword flags", metrics.keyword_flag_count)
    cols[4].metric("Private chats", metrics.private_chat_count)

    if metrics.total_messages == 0:
        st.info("No flagged messages stored yet. Scrape a channel or group to populate the dashboard.")
        return

    if metrics.private_chat_count:
        st.warning(
            f"{metrics.private_chat_count} private chat(s) are stored. "
            "Run `clear.bat --private-chats` to remove them."
        )

    left, right = st.columns(2)
    with left:
        st.subheader("Top chats")
        st.dataframe(ranked_counts_as_rows(summary.top_chats), use_container_width=True, hide_index=True)
    with right:
        st.subheader("Keyword flags")
        st.dataframe(ranked_counts_as_rows(summary.keyword_flags), use_container_width=True, hide_index=True)


def _page_chat_explorer(settings: Settings) -> None:
    import streamlit as st

    st.header("Chat Explorer")
    include_private = st.checkbox("Show private chats", value=False)

    def render(session: Session, _engine: AnalyticsEngine) -> None:
        rows = get_chat_table_rows(session, include_private=include_private)
        if not rows:
            st.info("No chats match the current filter.")
            return
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    _with_session(settings, render)


def _page_analytics(settings: Settings) -> None:
    import streamlit as st

    st.header("Analytics")

    def render(_session: Session, engine: AnalyticsEngine) -> None:
        summary = engine.build_summary()
        if summary.total_messages == 0:
            st.info("No messages available for analytics.")
            return

        st.plotly_chart(messages_per_day_chart(summary), use_container_width=True)
        st.plotly_chart(messages_per_hour_chart(summary), use_container_width=True)

        left, right = st.columns(2)
        with left:
            st.subheader("Top senders")
            st.dataframe(
                ranked_counts_as_rows(summary.top_senders),
                use_container_width=True,
                hide_index=True,
            )
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

    _with_session(settings, render)


def _page_entity_explorer(settings: Settings) -> None:
    import streamlit as st

    st.header("Entity Explorer")

    def render(session: Session, _engine: AnalyticsEngine) -> None:
        entity_types = list_entity_types(session)
        if not entity_types:
            st.info("No extracted entities yet.")
            return

        labels = ["All"] + entity_types
        selected = st.selectbox("Entity type", labels, index=0)
        entity_type = None if selected == "All" else selected

        if entity_type is None:
            st.caption(
                "Content entities: "
                + ", ".join(sorted(CONTENT_ENTITY_TYPES))
                + " · Keyword categories: "
                + ", ".join(sorted(KEYWORD_ENTITY_TYPES))
            )

        rows = get_entity_table_rows(session, entity_type=entity_type)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    _with_session(settings, render)


def _page_search(settings: Settings) -> None:
    import streamlit as st

    st.header("Search")
    query = st.text_input("Search message text")
    limit = st.number_input("Max results", min_value=1, max_value=500, value=50, step=10)

    if not query.strip():
        st.caption("Enter a keyword or phrase to search stored messages.")
        return

    def render(_session: Session, engine: AnalyticsEngine) -> None:
        hits = engine.search_messages(query, limit=int(limit))
        rows = search_hits_as_rows(hits)
        st.write(f"{len(rows)} result(s)")
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No messages matched your query.")

    _with_session(settings, render)


def _page_export(settings: Settings) -> None:
    import streamlit as st

    st.header("Export")
    st.caption("Generate CSV and JSON exports from the current SQLite database.")

    if st.button("Run export now", type="primary"):
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
