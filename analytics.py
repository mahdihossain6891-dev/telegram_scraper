"""Analytics and aggregation over stored Telegram data."""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go

from config import Settings, ensure_directories, load_settings
from database import MongoSession, get_session, init_db
from entity_extractor import CONTENT_ENTITY_TYPES
from models import Message
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

    def __init__(self, session: MongoSession) -> None:
        self.session = session

    def total_message_count(self) -> int:
        """Return the total number of stored messages."""
        return int(self.session.messages.count_documents({}))

    def messages_per_day(self, limit: int = 30) -> list[RankedCount]:
        """Return message counts grouped by calendar day."""
        pipeline = [
            {"$match": {"timestamp": {"$ne": None}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": -1}},
            {"$limit": limit},
        ]
        rows = list(self.session.messages.aggregate(pipeline))
        rows.reverse()
        return [
            RankedCount(label=str(row["_id"]), count=int(row["count"]))
            for row in rows
            if row.get("_id")
        ]

    def messages_per_hour(self) -> list[RankedCount]:
        """Return message counts grouped by hour of day (0-23)."""
        pipeline = [
            {"$match": {"timestamp": {"$ne": None}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%H", "date": "$timestamp"}},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        return [
            RankedCount(label=f"{row['_id']}:00", count=int(row["count"]))
            for row in self.session.messages.aggregate(pipeline)
            if row.get("_id") is not None
        ]

    def top_chats(self, limit: int = 10) -> list[RankedCount]:
        """Return chats ranked by stored message count."""
        pipeline = [
            {"$group": {"_id": "$chat_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        results: list[RankedCount] = []
        for row in self.session.messages.aggregate(pipeline):
            chat_id = int(row["_id"])
            chat = self.session.get_chat(chat_id)
            title = chat.title if chat else None
            results.append(
                RankedCount(
                    label=title or f"Chat {chat_id}",
                    count=int(row["count"]),
                    detail=str(chat_id),
                )
            )
        return results

    def top_senders(self, limit: int = 10) -> list[RankedCount]:
        """Return senders ranked by stored message count."""
        pipeline = [
            {"$match": {"sender_id": {"$ne": None}}},
            {"$group": {"_id": "$sender_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        results: list[RankedCount] = []
        for row in self.session.messages.aggregate(pipeline):
            user_id = int(row["_id"])
            user = self.session.get_user(user_id)
            if user and user.username and user.first_name:
                label = f"{user.first_name} (@{user.username})"
            elif user:
                label = user.username or user.first_name or f"User {user_id}"
            else:
                label = f"User {user_id}"
            results.append(
                RankedCount(label=label, count=int(row["count"]), detail=str(user_id))
            )
        return results

    def top_entities(self, entity_type: str, limit: int = 10) -> list[RankedCount]:
        """Return top extracted entities for a given type."""
        pipeline = [
            {"$match": {"entity_type": entity_type}},
            {"$group": {"_id": "$entity_value", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        return [
            RankedCount(label=str(row["_id"]), count=int(row["count"]))
            for row in self.session.entities.aggregate(pipeline)
        ]

    def top_domains(self, limit: int = 10) -> list[RankedCount]:
        """Return the most frequent extracted domains."""
        return self.top_entities("domain", limit=limit)

    def top_hashtags(self, limit: int = 10) -> list[RankedCount]:
        """Return the most frequent hashtags."""
        return self.top_entities("hashtag", limit=limit)

    def keyword_flag_counts(self) -> list[RankedCount]:
        """Return counts for keyword flag categories and terms."""
        pipeline = [
            {"$match": {"entity_type": {"$nin": list(CONTENT_ENTITY_TYPES)}}},
            {
                "$group": {
                    "_id": {"type": "$entity_type", "value": "$entity_value"},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
        ]
        return [
            RankedCount(
                label=f"{row['_id']['type']}: {row['_id']['value']}",
                count=int(row["count"]),
            )
            for row in self.session.entities.aggregate(pipeline)
        ]

    def word_frequency(self, limit: int = 20) -> list[RankedCount]:
        """Return the most common words across message text."""
        counter: Counter[str] = Counter()
        for doc in self.session.messages.find({"text": {"$ne": None}}, {"text": 1}):
            text = doc.get("text")
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

        hits: list[SearchHit] = []
        cursor = (
            self.session.messages.find(
                {"text": {"$regex": re.escape(cleaned), "$options": "i"}}
            )
            .sort("timestamp", -1)
            .limit(limit)
        )
        for doc in cursor:
            message = Message.from_doc(doc)
            chat = self.session.get_chat(message.chat_id)
            hits.append(
                SearchHit(
                    message_row_id=message.id or 0,
                    chat_id=message.chat_id,
                    message_id=message.message_id,
                    timestamp=message.timestamp,
                    text=message.text,
                    chat_title=chat.title if chat else None,
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
            for hit in hits[:20]:
                preview = (hit.text or "")[:80].replace("\n", " ")
                print(f"  - [{hit.chat_title}] {preview}")

    if save_html_charts:
        save_charts(summary, cfg.exports_dir)
    return summary


def main() -> None:
    """CLI entry point."""
    cfg = ensure_directories()
    setup_logging(cfg)
    query = sys.argv[1] if len(sys.argv) > 1 else None
    summary = run_analytics(cfg, search_query=query)
    print_summary(summary)


if __name__ == "__main__":
    main()
