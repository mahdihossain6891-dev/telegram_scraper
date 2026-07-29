"""Resolve monitored chats and run keyword-filtered scrapes in the background."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from typing import Callable

from chat_discovery import ChatDiscovery, DiscoveredChat, filter_chats_for_scrape
from config import Settings, ensure_directories, load_settings
from database import MongoSession, get_session, init_db
from message_scraper import MessageScrapeError, MessageScraper, ScrapeResult, normalize_limit
from models import Chat
from scrape_jobs.store import ScrapeJobStore, get_scrape_job_store
from telegram_client import TelegramAuthError, TelegramClientManager
from utils import setup_logging

logger = logging.getLogger("scrape_jobs.runner")

ProgressCallback = Callable[[ScrapeResult, int, int], None]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def scrape_limit_from_env(default: int = 500) -> int:
    raw = os.getenv("SCRAPE_MESSAGE_LIMIT") or os.getenv("AUTO_UPDATE_SCRAPE_LIMIT", str(default))
    try:
        return normalize_limit(int(str(raw).strip()))
    except (TypeError, ValueError, MessageScrapeError):
        return normalize_limit(default)


def monitored_scope_from_env() -> str:
    return (
        os.getenv("SCRAPE_MONITORED_SCOPE")
        or os.getenv("AUTO_UPDATE_SCRAPE_TARGET", "non-private")
        or "non-private"
    ).strip().lower()


def resolve_monitored_chats(
    session: MongoSession,
    discovered: list[DiscoveredChat],
    *,
    include_private: bool | None = None,
    scope: str | None = None,
) -> tuple[list[DiscoveredChat], str]:
    """Return chats to scrape — only configured monitored channels/groups."""
    include_private = (
        _env_bool("SCRAPE_INCLUDE_PRIVATE", False) if include_private is None else include_private
    )
    stored: list[Chat] = session.list_chats()
    if stored:
        allowed = {
            chat.id
            for chat in stored
            if include_private or chat.chat_type != "private chat"
        }
        matched = [chat for chat in discovered if chat.chat_id in allowed]
        return matched, "monitored_db"

    resolved_scope = (scope or monitored_scope_from_env()).strip().lower()
    if resolved_scope.isdigit():
        chat_id = int(resolved_scope)
        matched = [chat for chat in discovered if chat.chat_id == chat_id]
        return matched, f"chat:{chat_id}"

    # Batch scopes such as non-private, channels, groups
    if resolved_scope in {"all", "private", "groups", "channels", "non-private"}:
        filtered = filter_chats_for_scrape(discovered, resolved_scope)
        if not include_private:
            filtered = [chat for chat in filtered if chat.chat_type != "private chat"]
        return filtered, resolved_scope

    # Legacy AUTO_UPDATE target may be a chat index from discovery listing
    try:
        index = int(resolved_scope)
        matched = [chat for chat in discovered if chat.index == index]
        if matched:
            return matched, f"index:{index}"
    except ValueError:
        pass

    filtered = filter_chats_for_scrape(discovered, "non-private")
    return filtered, "non-private"


async def run_monitored_scrape_async(
    settings: Settings,
    store: ScrapeJobStore,
    *,
    limit: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Scan monitored channels only; persist keyword-flagged threat messages."""
    cfg = ensure_directories(settings)
    setup_logging(cfg)
    init_db(cfg)
    per_chat_limit = normalize_limit(limit if limit is not None else scrape_limit_from_env())

    manager = TelegramClientManager(cfg)
    client = manager.create_client()

    try:
        await manager.start(client)
    except TelegramAuthError as exc:
        raise MessageScrapeError(str(exc)) from exc

    try:
        discovery = ChatDiscovery(client)
        discovered = await discovery.fetch_chats(limit=None)
        if not discovered:
            raise MessageScrapeError("No accessible Telegram chats found for this session.")

        with get_session(cfg) as session:
            monitored, scope = resolve_monitored_chats(session, discovered)

        if not monitored:
            raise MessageScrapeError(
                "No monitored channels/groups matched. Add chats to MongoDB or set "
                "SCRAPE_MONITORED_SCOPE / AUTO_UPDATE_SCRAPE_TARGET."
            )

        if not store.start(
            channels_total=len(monitored),
            scope=scope,
            limit_per_chat=per_chat_limit,
        ):
            raise MessageScrapeError("Failed to initialize scrape job state.")

        scraper = MessageScraper(client, cfg)
        total_processed = 0
        total_flagged = 0

        def _progress(result: ScrapeResult, index: int, total: int) -> None:
            nonlocal total_processed, total_flagged
            total_processed += result.processed
            total_flagged += result.flagged_stored
            store.update_progress(
                channels_scanned=index,
                messages_analyzed=total_processed,
                threats_detected=total_flagged,
                current_channel=result.chat_name,
            )
            if on_progress:
                on_progress(result, index, total)

        batch = await scraper.scrape_chats(
            monitored,
            limit=per_chat_limit,
            scope=scope,
            on_progress=_progress,
        )
        try:
            from behavioral_analytics import rebuild_behavioral_analytics
            from personnel import rebuild_user_activity

            with get_session(settings) as session:
                rebuild_user_activity(session)
                rebuild_behavioral_analytics(session)
        except Exception:
            logger.exception("post_scrape_analytics_rebuild_failed")
        store.complete(
            messages_analyzed=batch.total_processed,
            threats_detected=batch.total_flagged_stored,
        )
        logger.info(
            "scrape_job_complete chats=%d processed=%d flagged=%d",
            batch.chats_scanned,
            batch.total_processed,
            batch.total_flagged_stored,
        )
    finally:
        await manager.stop(client)


def _thread_target(settings: Settings, limit: int | None) -> None:
    store = get_scrape_job_store()
    try:
        asyncio.run(run_monitored_scrape_async(settings, store, limit=limit))
    except Exception as exc:  # noqa: BLE001 — surface to dashboard
        logger.exception("scrape_job_failed")
        store.fail(str(exc))


def start_scrape_job_in_background(
    settings: Settings | None = None,
    *,
    limit: int | None = None,
) -> bool:
    """Start scrape on a daemon thread. Returns False if already running."""
    store = get_scrape_job_store()
    if not store.try_begin():
        return False
    cfg = ensure_directories(settings or load_settings())
    thread = threading.Thread(
        target=_thread_target,
        args=(cfg, limit),
        name="scrape-job",
        daemon=True,
    )
    thread.start()
    return True
