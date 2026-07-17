"""Analytics and aggregation over stored Telegram data."""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import Settings, ensure_directories, load_settings
from database import get_session, init_db
from entity_extractor import CONTENT_ENTITY_TYPES
from models import Chat, ExtractedEntity, Message, User
from utils import get_logger, setup_logging

logger = get_logger("analytics")

WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")
DEFAULT_STOP_WORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "with",
        "this",
        "that",
        "from",
        "have",
        "was",
        "were",
        "will",
        "your",
        "about",
        "into",
        "https",
        "http",
    }
)


@dataclass(frozen=True)
class RankedCount:
    """A ranked analytics item."""

    label: str
    count: int
    detail: str | None = None


@dataclass(frozen=True)
class SearchHit:
    """A message returned by keyword search."""

    message_row_id: int
    chat_id: int
    message_id: int
    timestamp: datetime | None
    text: str | None
    chat_title: str | None


@dataclass(frozen=True)
class AnalyticsSummary:
    """Complete analytics snapshot."""

    total_messages: int
    messages_per_day: tuple[RankedCount, ...]
    messages_per_hour: tuple[RankedCount, ...]
    top_chats: tuple[RankedCount, ...]
    top_senders: tuple[RankedCount, ...]
    top_domains: tuple[RankedCount, ...]
    top_hashtags: tuple[RankedCount, ...]
    top_words: tuple[RankedCount, ...]
    keyword_flags: tuple[RankedCount, ...]


class AnalyticsEngine:
    """Compute statistics and search results from stored messages."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def total_message_count(self) -> int:
        """Return the total number of stored messages."""
        return int(self.session.scalar(select(func.count()).select_from(Message)) or 0)

    def messages_per_day(self, limit: int = 30) -> list[RankedCount]:
        """Return message counts grouped by calendar day."""
        day_expr = func.date(Message.timestamp)
        stmt = (
            select(day_expr, func.count(Message.id))
            .where(Message.timestamp.is_not(None))
            .group_by(day_expr)
            .order_by(day_expr.desc())
            .limit(limit)
        )
        rows = self.session.execute(stmt).all()
        return [
            RankedCount(label=str(day), count=int(count))
            for day, count in reversed(rows)
            if day is not None
        ]

    def messages_per_hour(self) -> list[RankedCount]:
        """Return message counts grouped by hour of day (0-23)."""
        hour_expr = func.strftime("%H", Message.timestamp)
        stmt = (
            select(hour_expr, func.count(Message.id))
            .where(Message.timestamp.is_not(None))
            .group_by(hour_expr)
            .order_by(hour_expr)
        )
        rows = self.session.execute(stmt).all()
        return [
            RankedCount(label=f"{hour}:00", count=int(count))
            for hour, count in rows
            if hour is not None
        ]

    def top_chats(self, limit: int = 10) -> list[RankedCount]:
        """Return chats ranked by stored message count."""
        stmt = (
            select(Chat.id, Chat.title, func.count(Message.id))
            .join(Message, Message.chat_id == Chat.id)
            .group_by(Chat.id, Chat.title)
            .order_by(func.count(Message.id).desc())
            .limit(limit)
        )
        return [
            RankedCount(
                label=title or f"Chat {chat_id}",
                count=int(count),
                detail=str(chat_id),
            )
            for chat_id, title, count in self.session.execute(stmt).all()
        ]

    def top_senders(self, limit: int = 10) -> list[RankedCount]:
        """Return senders ranked by stored message count."""
        stmt = (
            select(User.id, User.username, User.first_name, func.count(Message.id))
            .join(Message, Message.sender_id == User.id)
            .group_by(User.id, User.username, User.first_name)
            .order_by(func.count(Message.id).desc())
            .limit(limit)
        )
        results: list[RankedCount] = []
        for user_id, username, first_name, count in self.session.execute(stmt).all():
            label = username or first_name or f"User {user_id}"
            if username and first_name:
                label = f"{first_name} (@{username})"
            results.append(
                RankedCount(label=label, count=int(count), detail=str(user_id))
            )
        return results

    def top_entities(self, entity_type: str, limit: int = 10) -> list[RankedCount]:
        """Return top extracted entities for a given type."""
        stmt = (
            select(ExtractedEntity.entity_value, func.count(ExtractedEntity.id))
            .where(ExtractedEntity.entity_type == entity_type)
            .group_by(ExtractedEntity.entity_value)
            .order_by(func.count(ExtractedEntity.id).desc())
            .limit(limit)
        )
        return [
            RankedCount(label=value, count=int(count))
            for value, count in self.session.execute(stmt).all()
        ]

    def top_domains(self, limit: int = 10) -> list[RankedCount]:
        """Return the most frequent extracted domains."""
        return self.top_entities("domain", limit=limit)

    def top_hashtags(self, limit: int = 10) -> list[RankedCount]:
        """Return the most frequent hashtags."""
        return self.top_entities("hashtag", limit=limit)

    def keyword_flag_counts(self) -> list[RankedCount]:
        """Return counts for keyword flag categories and terms."""
        stmt = (
            select(ExtractedEntity.entity_type, ExtractedEntity.entity_value, func.count())
            .where(ExtractedEntity.entity_type.not_in(tuple(CONTENT_ENTITY_TYPES)))
            .group_by(ExtractedEntity.entity_type, ExtractedEntity.entity_value)
            .order_by(func.count().desc())
        )
        return [
            RankedCount(
                label=f"{entity_type}: {entity_value}",
                count=int(count),
            )
            for entity_type, entity_value, count in self.session.execute(stmt).all()
        ]

    def word_frequency(self, limit: int = 20) -> list[RankedCount]:
        """Return the most common words across message text."""
        texts = self.session.scalars(
            select(Message.text).where(Message.text.is_not(None))
        ).all()
        counter: Counter[str] = Counter()
        for text in texts:
            if not text:
                continue
            for token in WORD_PATTERN.findall(text.lower()):
                if len(token) < 3 or token in DEFAULT_STOP_WORDS:
                    continue
                counter[token] += 1
        return [
            RankedCount(label=word, count=count)
            for word, count in counter.most_common(limit)
        ]

    def search_messages(self, query: str, limit: int = 50) -> list[SearchHit]:
        """Search stored message text for a keyword or phrase."""
        cleaned = query.strip()
        if not cleaned:
            return []

        pattern = f"%{cleaned}%"
        stmt = (
            select(Message, Chat.title)
            .join(Chat, Chat.id == Message.chat_id, isouter=True)
            .where(Message.text.ilike(pattern))
            .order_by(Message.timestamp.desc())
            .limit(limit)
        )
        hits: list[SearchHit] = []
        for message, chat_title in self.session.execute(stmt).all():
            hits.append(
                SearchHit(
                    message_row_id=message.id,
                    chat_id=message.chat_id,
                    message_id=message.message_id,
                    timestamp=message.timestamp,
                    text=message.text,
                    chat_title=chat_title,
                )
            )
        return hits

    def build_summary(self) -> AnalyticsSummary:
        """Compute a full analytics snapshot."""
        logger.info("Building analytics summary")
        return AnalyticsSummary(
            total_messages=self.total_message_count(),
            messages_per_day=tuple(self.messages_per_day()),
            messages_per_hour=tuple(self.messages_per_hour()),
            top_chats=tuple(self.top_chats()),
            top_senders=tuple(self.top_senders()),
            top_domains=tuple(self.top_domains()),
            top_hashtags=tuple(self.top_hashtags()),
            top_words=tuple(self.word_frequency()),
            keyword_flags=tuple(self.keyword_flag_counts()),
        )


def messages_per_day_chart(summary: AnalyticsSummary) -> go.Figure:
    """Build a Plotly timeline chart for messages per day."""
    labels = [item.label for item in summary.messages_per_day]
    counts = [item.count for item in summary.messages_per_day]
    figure = go.Figure(
        data=[go.Scatter(x=labels, y=counts, mode="lines+markers", name="Messages")],
    )
    figure.update_layout(
        title="Messages Per Day",
        xaxis_title="Date",
        yaxis_title="Message Count",
        template="plotly_white",
    )
    return figure


def messages_per_hour_chart(summary: AnalyticsSummary) -> go.Figure:
    """Build a Plotly bar chart for messages by hour."""
    labels = [item.label for item in summary.messages_per_hour]
    counts = [item.count for item in summary.messages_per_hour]
    figure = go.Figure(data=[go.Bar(x=labels, y=counts, name="Messages")])
    figure.update_layout(
        title="Messages Per Hour",
        xaxis_title="Hour",
        yaxis_title="Message Count",
        template="plotly_white",
    )
    return figure


def save_charts(summary: AnalyticsSummary, exports_dir: Path) -> tuple[Path, Path]:
    """Save timeline charts to the exports directory."""
    exports_dir.mkdir(parents=True, exist_ok=True)
    daily_path = exports_dir / "messages_per_day.html"
    hourly_path = exports_dir / "messages_per_hour.html"
    messages_per_day_chart(summary).write_html(str(daily_path), include_plotlyjs="cdn")
    messages_per_hour_chart(summary).write_html(str(hourly_path), include_plotlyjs="cdn")
    logger.info("Saved charts to %s and %s", daily_path, hourly_path)
    return daily_path, hourly_path


def _print_ranked_section(title: str, items: tuple[RankedCount, ...]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not items:
        print("  (none)")
        return
    for index, item in enumerate(items, start=1):
        detail = f" [{item.detail}]" if item.detail else ""
        print(f"  {index:>2}. {item.label}{detail}: {item.count}")


def print_summary(summary: AnalyticsSummary) -> None:
    """Print analytics summary to stdout."""
    print("\nAnalytics Summary")
    print("=================")
    print(f"Total messages: {summary.total_messages}")
    _print_ranked_section("Messages Per Day", summary.messages_per_day)
    _print_ranked_section("Messages Per Hour", summary.messages_per_hour)
    _print_ranked_section("Top Chats", summary.top_chats)
    _print_ranked_section("Top Senders", summary.top_senders)
    _print_ranked_section("Top Domains", summary.top_domains)
    _print_ranked_section("Top Hashtags", summary.top_hashtags)
    _print_ranked_section("Top Words", summary.top_words)
    _print_ranked_section("Keyword Flags", summary.keyword_flags)


def run_analytics(
    settings: Settings | None = None,
    search_query: str | None = None,
    save_html_charts: bool = True,
) -> AnalyticsSummary:
    """Load data and compute analytics."""
    cfg = ensure_directories(settings)
    init_db(cfg)

    with get_session(cfg) as session:
        engine = AnalyticsEngine(session)
        summary = engine.build_summary()

        if search_query:
            hits = engine.search_messages(search_query)
            print(f"\nSearch results for {search_query!r}: {len(hits)}")
            for hit in hits[:10]:
                preview = (hit.text or "")[:120].replace("\n", " ")
                print(
                    f"  - chat={hit.chat_title or hit.chat_id} "
                    f"msg_id={hit.message_id} ts={hit.timestamp} :: {preview}"
                )

    if save_html_charts and summary.total_messages > 0:
        save_charts(summary, cfg.exports_dir)

    return summary


def main() -> None:
    """CLI entry point for analytics."""
    cfg = ensure_directories()
    setup_logging(cfg)

    search_query = None
    if len(sys.argv) > 1:
        search_query = " ".join(sys.argv[1:])

    summary = run_analytics(cfg, search_query=search_query)
    print_summary(summary)

    if summary.total_messages == 0:
        print("\nNo stored messages yet. Run scrape.bat first.")
        raise SystemExit(0)

    if cfg.exports_dir.exists():
        print(f"\nCharts saved under: {cfg.exports_dir}")


if __name__ == "__main__":
    main()
