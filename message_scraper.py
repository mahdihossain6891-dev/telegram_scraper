"""Collect flagged messages from a selected chat and store them in MongoDB."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Callable

from telethon import TelegramClient, utils
from telethon.errors import RPCError
from telethon.tl.types import Message as TelethonMessage
from telethon.tl.types import User as TelethonUser

from chat_discovery import (
    SCRAPE_SCOPES,
    ChatDiscovery,
    ChatDiscoveryError,
    ChatNotFoundError,
    DiscoveredChat,
    filter_chats_for_scrape,
    prompt_for_selection,
)
from config import Settings, ensure_directories, load_settings
from database import MongoSession, get_session, init_db, message_exists
from entity_extractor import store_entities_for_message
from keyword_filter import KeywordScanResult, scan_message_text
from models import Chat, ExtractedEntity, Message, User
from personnel import record_user_activity, refresh_chat_risk
from risk_scoring import score_message
from entity_extractor import collect_alert_addresses
from telegram_alerts import AlertMessage, maybe_alert_after_scrape
from telegram_client import TelegramAuthError, TelegramClientManager
from utils import get_logger, setup_logging

logger = get_logger("message_scraper")

DEFAULT_BATCH_SIZE = 100
ALLOWED_LIMITS: tuple[int, ...] = (100, 500, 1000)


class MessageScrapeError(Exception):
    """Raised when message collection fails."""


@dataclass(frozen=True)
class ScrapeResult:
    """Summary of a message collection run."""

    chat_id: int
    chat_name: str
    requested_limit: int
    processed: int
    flagged_stored: int
    skipped_duplicates: int
    skipped_no_keyword: int
    error: str | None = None


@dataclass(frozen=True)
class MultiScrapeResult:
    """Summary of a batch collection run across multiple chats."""

    scope: str
    requested_limit: int
    chats_scanned: int
    total_processed: int
    total_flagged_stored: int
    total_skipped_duplicates: int
    total_skipped_no_keyword: int
    chat_results: tuple[ScrapeResult, ...]


@dataclass(frozen=True)
class ParsedMessage:
    """Normalized message fields ready for database storage."""

    message_id: int
    chat_id: int
    sender_id: int | None
    timestamp: object | None
    text: str | None
    media_type: str | None
    reply_to_message_id: int | None
    forward_from_chat_id: int | None
    forward_from_message_id: int | None
    views: int | None
    sender_username: str | None = None
    sender_first_name: str | None = None
    sender_last_name: str | None = None


def normalize_limit(limit: int) -> int:
    """Validate and return an allowed scrape limit."""
    if limit not in ALLOWED_LIMITS:
        allowed = ", ".join(str(value) for value in ALLOWED_LIMITS)
        raise MessageScrapeError(f"Limit must be one of: {allowed}. Got: {limit}")
    return limit


def parse_limit_input(raw: str) -> int:
    """Parse a user-provided limit string."""
    value = raw.strip()
    if not value:
        raise MessageScrapeError("Message limit is required.")
    try:
        return normalize_limit(int(value))
    except ValueError as exc:
        raise MessageScrapeError(f"Invalid message limit: {raw!r}") from exc


def _media_type(message: TelethonMessage) -> str | None:
    """Return a simple media type label when media is present."""
    if message.media is None:
        return None
    return type(message.media).__name__


def _reply_id(message: TelethonMessage) -> int | None:
    """Return the replied-to message ID when available."""
    if message.reply_to is None:
        return None
    return getattr(message.reply_to, "reply_to_msg_id", None)


def _forward_info(message: TelethonMessage) -> tuple[int | None, int | None]:
    """Return forward source chat ID and message ID when available."""
    forward = message.forward
    if forward is None:
        return None, None

    forward_chat_id = None
    if forward.from_id is not None:
        forward_chat_id = utils.get_peer_id(forward.from_id)

    forward_message_id = forward.channel_post or forward.saved_from_msg_id
    return forward_chat_id, forward_message_id


def _sender_fields(message: TelethonMessage) -> tuple[int | None, str | None, str | None, str | None]:
    """Extract sender ID and profile fields from a Telethon message."""
    sender_id = getattr(message, "sender_id", None)
    sender = getattr(message, "sender", None)
    if isinstance(sender, TelethonUser):
        return (
            sender.id,
            sender.username,
            sender.first_name,
            sender.last_name,
        )
    return sender_id, None, None, None


def _extract_message_text(message: TelethonMessage) -> str | None:
    """Return message body text, including captions when present."""
    for candidate in (
        message.message,
        getattr(message, "raw_text", None),
        getattr(message, "text", None),
    ):
        if candidate and str(candidate).strip():
            return str(candidate).replace("\u200b", "").strip()
    return None


def parse_telethon_message(message: TelethonMessage, chat_id: int) -> ParsedMessage:
    """Convert a Telethon message into database-ready fields."""
    forward_chat_id, forward_message_id = _forward_info(message)
    sender_id, username, first_name, last_name = _sender_fields(message)

    return ParsedMessage(
        message_id=message.id,
        chat_id=chat_id,
        sender_id=sender_id,
        timestamp=message.date,
        text=_extract_message_text(message),
        media_type=_media_type(message),
        reply_to_message_id=_reply_id(message),
        forward_from_chat_id=forward_chat_id,
        forward_from_message_id=forward_message_id,
        views=getattr(message, "views", None),
        sender_username=username,
        sender_first_name=first_name,
        sender_last_name=last_name,
    )


def ensure_chat_record(session: MongoSession, chat: DiscoveredChat) -> Chat:
    """Insert the chat metadata if it is not already stored."""
    return session.upsert_chat(
        Chat(
            id=chat.chat_id,
            title=chat.name,
            username=chat.username,
            chat_type=chat.chat_type,
        )
    )


def ensure_user_record(session: MongoSession, parsed: ParsedMessage) -> None:
    """Insert or update a sender record when sender information is available."""
    if parsed.sender_id is None:
        return

    session.upsert_user(
        User(
            id=parsed.sender_id,
            username=parsed.sender_username,
            first_name=parsed.sender_first_name,
            last_name=parsed.sender_last_name,
        )
    )


def store_parsed_message(
    session: MongoSession,
    parsed: ParsedMessage,
    keyword_scan: KeywordScanResult,
) -> bool:
    """Store a flagged message and its keyword hits, skipping duplicates."""
    if not keyword_scan.matched:
        return False

    if message_exists(session, parsed.chat_id, parsed.message_id):
        return False

    ensure_user_record(session, parsed)
    keywords = [hit.keyword for hit in keyword_scan.hits]
    categories = [str(c) for c in keyword_scan.categories]
    risk = score_message(
        keywords=keywords,
        categories=categories,
        text=parsed.text,
    )
    record = session.insert_message(
        Message(
            message_id=parsed.message_id,
            chat_id=parsed.chat_id,
            sender_id=parsed.sender_id,
            timestamp=parsed.timestamp,
            text=parsed.text,
            media_type=parsed.media_type,
            reply_to_message_id=parsed.reply_to_message_id,
            forward_from_chat_id=parsed.forward_from_chat_id,
            forward_from_message_id=parsed.forward_from_message_id,
            views=parsed.views,
            risk_score=risk.score,
            risk_level=risk.level,
            risk_factors=list(risk.factors),
        )
    )

    for hit in keyword_scan.hits:
        session.insert_entity(
            ExtractedEntity(
                message_row_id=record.id or 0,
                entity_type=hit.category,
                entity_value=hit.keyword,
            )
        )

    content_stored, _content_skipped = store_entities_for_message(
        session,
        record.id or 0,
        parsed.text,
    )

    if parsed.sender_id is not None:
        record_user_activity(
            session,
            user_id=parsed.sender_id,
            chat_id=parsed.chat_id,
            timestamp=parsed.timestamp,
            keywords=keywords,
            categories=categories,
            username=parsed.sender_username,
            first_name=parsed.sender_first_name,
            last_name=parsed.sender_last_name,
            message_risk_score=risk.score,
        )
    refresh_chat_risk(session, parsed.chat_id)

    logger.info(
        "Flagged message_id=%s chat_id=%s categories=%s keywords=%s risk=%s/%s content_entities=%d",
        parsed.message_id,
        parsed.chat_id,
        ",".join(categories),
        ",".join(keywords),
        risk.score,
        risk.level,
        content_stored,
    )
    return True


class MessageScraper:
    """Download messages from a selected chat and persist keyword-flagged matches."""

    def __init__(
        self,
        client: TelegramClient,
        settings: Settings | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.client = client
        self.settings = settings or load_settings()
        self.batch_size = batch_size

    async def scrape_chat(
        self,
        chat: DiscoveredChat,
        limit: int,
    ) -> ScrapeResult:
        """Collect up to ``limit`` messages from the selected chat."""
        limit = normalize_limit(limit)
        init_db(self.settings)

        if not await self.client.is_user_authorized():
            raise MessageScrapeError(
                "Telegram session is not authorized. Run telegram_client.py first."
            )

        logger.info(
            "Starting keyword-filtered collection for chat_id=%s name=%r limit=%d",
            chat.chat_id,
            chat.name,
            limit,
        )

        flagged_stored = 0
        skipped_duplicates = 0
        skipped_no_keyword = 0
        processed = 0
        pending: list[TelethonMessage] = []
        alert_items: list[AlertMessage] = []

        try:
            async for message in self.client.iter_messages(chat.chat_id, limit=limit):
                if not isinstance(message, TelethonMessage):
                    continue

                pending.append(message)
                if len(pending) >= self.batch_size:
                    batch_flagged, batch_dupes, batch_no_keyword, batch_alerts = self._store_batch(
                        chat, pending
                    )
                    flagged_stored += batch_flagged
                    skipped_duplicates += batch_dupes
                    skipped_no_keyword += batch_no_keyword
                    alert_items.extend(batch_alerts)
                    processed += len(pending)
                    pending.clear()
                    logger.info(
                        "Progress chat_id=%s processed=%d flagged=%d no_keyword=%d dupes=%d",
                        chat.chat_id,
                        processed,
                        flagged_stored,
                        skipped_no_keyword,
                        skipped_duplicates,
                    )

            if pending:
                batch_flagged, batch_dupes, batch_no_keyword, batch_alerts = self._store_batch(
                    chat, pending
                )
                flagged_stored += batch_flagged
                skipped_duplicates += batch_dupes
                skipped_no_keyword += batch_no_keyword
                alert_items.extend(batch_alerts)
                processed += len(pending)
        except RPCError as exc:
            logger.error("Telegram API error during message collection: %s", exc)
            raise MessageScrapeError(f"Failed to collect messages: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error during message collection: %s", exc)
            raise MessageScrapeError(f"Failed to collect messages: {exc}") from exc

        if alert_items:
            maybe_alert_after_scrape(alert_items, chat_name=chat.name)

        result = ScrapeResult(
            chat_id=chat.chat_id,
            chat_name=chat.name,
            requested_limit=limit,
            processed=processed,
            flagged_stored=flagged_stored,
            skipped_duplicates=skipped_duplicates,
            skipped_no_keyword=skipped_no_keyword,
        )
        logger.info(
            "Finished collection for chat_id=%s processed=%d flagged=%d no_keyword=%d dupes=%d",
            chat.chat_id,
            result.processed,
            result.flagged_stored,
            result.skipped_no_keyword,
            result.skipped_duplicates,
        )
        return result

    def _store_batch(
        self,
        chat: DiscoveredChat,
        messages: list[TelethonMessage],
    ) -> tuple[int, int, int, list[AlertMessage]]:
        """Persist keyword-flagged messages from a batch."""
        flagged_stored = 0
        skipped_duplicates = 0
        skipped_no_keyword = 0
        chat_record_created = False
        alert_items: list[AlertMessage] = []

        with get_session(self.settings) as session:
            for message in messages:
                parsed = parse_telethon_message(message, chat.chat_id)
                keyword_scan = scan_message_text(parsed.text)

                if not keyword_scan.matched:
                    skipped_no_keyword += 1
                    continue

                if message_exists(session, parsed.chat_id, parsed.message_id):
                    skipped_duplicates += 1
                    continue

                if not chat_record_created:
                    ensure_chat_record(session, chat)
                    chat_record_created = True

                if store_parsed_message(session, parsed, keyword_scan):
                    flagged_stored += 1
                    sender_parts = [
                        p
                        for p in (parsed.sender_first_name, parsed.sender_last_name)
                        if p
                    ]
                    sender = (
                        " ".join(sender_parts)
                        or (f"@{parsed.sender_username}" if parsed.sender_username else None)
                        or (f"User {parsed.sender_id}" if parsed.sender_id else "unknown")
                    )
                    alert_items.append(
                        AlertMessage(
                            chat_name=chat.name,
                            message_id=parsed.message_id,
                            sender=sender,
                            text=parsed.text or "",
                            categories=tuple(str(c) for c in keyword_scan.categories),
                            keywords=tuple(hit.keyword for hit in keyword_scan.hits),
                            timestamp=parsed.timestamp.isoformat() if parsed.timestamp else None,
                            addresses=collect_alert_addresses(parsed.text),
                            alert_key=f"{parsed.chat_id}:{parsed.message_id}",
                        )
                    )

        return flagged_stored, skipped_duplicates, skipped_no_keyword, alert_items

    async def scrape_chats(
        self,
        chats: list[DiscoveredChat],
        limit: int,
        *,
        scope: str = "all",
        on_progress: Callable[[ScrapeResult, int, int], None] | None = None,
    ) -> MultiScrapeResult:
        """Collect flagged messages from every chat in the provided list."""
        limit = normalize_limit(limit)
        results: list[ScrapeResult] = []

        for index, chat in enumerate(chats, start=1):
            print(
                f"[{index}/{len(chats)}] Scanning {chat.name} "
                f"({chat.chat_type}, ID {chat.chat_id})..."
            )
            logger.info(
                "Batch scrape %d/%d chat_id=%s name=%r type=%s",
                index,
                len(chats),
                chat.chat_id,
                chat.name,
                chat.chat_type,
            )
            try:
                result = await self.scrape_chat(chat, limit=limit)
            except MessageScrapeError as exc:
                logger.error(
                    "Skipping chat_id=%s name=%r after scrape error: %s",
                    chat.chat_id,
                    chat.name,
                    exc,
                )
                print(f"    Skipped due to error: {exc}")
                result = ScrapeResult(
                    chat_id=chat.chat_id,
                    chat_name=chat.name,
                    requested_limit=limit,
                    processed=0,
                    flagged_stored=0,
                    skipped_duplicates=0,
                    skipped_no_keyword=0,
                    error=str(exc),
                )
            else:
                print(
                    f"    Scanned {result.processed}, stored {result.flagged_stored}, "
                    f"no keyword {result.skipped_no_keyword}, duplicates {result.skipped_duplicates}"
                )
            results.append(result)
            if on_progress:
                on_progress(result, index, len(chats))

        return MultiScrapeResult(
            scope=scope,
            requested_limit=limit,
            chats_scanned=len(results),
            total_processed=sum(result.processed for result in results),
            total_flagged_stored=sum(result.flagged_stored for result in results),
            total_skipped_duplicates=sum(result.skipped_duplicates for result in results),
            total_skipped_no_keyword=sum(result.skipped_no_keyword for result in results),
            chat_results=tuple(results),
        )


def parse_scrape_target(raw: str) -> tuple[str, str | None]:
    """Parse CLI target such as ``all``, ``all-private``, or a chat index/ID."""
    value = raw.strip().lower()
    if not value:
        return "single", None
    if value == "all":
        return "batch", "all"
    if value.startswith("all-"):
        scope = value.removeprefix("all-")
        if scope in SCRAPE_SCOPES and scope != "all":
            return "batch", scope
        allowed = ", ".join(f"all-{scope_name}" for scope_name in SCRAPE_SCOPES if scope_name != "all")
        raise MessageScrapeError(f"Unknown batch scope {value!r}. Use: all, {allowed}")
    return "single", raw


def print_multi_scrape_summary(result: MultiScrapeResult) -> None:
    """Print a human-readable batch scrape summary."""
    print(
        f"\nBatch keyword-filtered collection complete "
        f"(scope={result.scope}, limit={result.requested_limit} per chat)\n"
        f"  Chats scanned:          {result.chats_scanned}\n"
        f"  Messages scanned:       {result.total_processed}\n"
        f"  Flagged and stored:     {result.total_flagged_stored}\n"
        f"  Skipped (no keyword):   {result.total_skipped_no_keyword}\n"
        f"  Skipped (duplicate):    {result.total_skipped_duplicates}"
    )
    chats_with_hits = [item for item in result.chat_results if item.flagged_stored > 0]
    if chats_with_hits:
        print("\n  Chats with flagged messages:")
        for item in chats_with_hits:
            print(
                f"    - {item.chat_name} (ID: {item.chat_id}): "
                f"{item.flagged_stored} stored / {item.processed} scanned"
            )
    else:
        print("\n  No keyword matches were stored. Check that test messages use terms from keyword_filter.py.")

    scanned_without_hits = [
        item
        for item in result.chat_results
        if item.flagged_stored == 0 and item.processed > 0 and not item.error
    ]
    if scanned_without_hits:
        print(f"\n  DMs/chats scanned with no keyword match ({len(scanned_without_hits)}):")
        for item in scanned_without_hits[:25]:
            print(
                f"    - {item.chat_name}: {item.processed} message(s) scanned, 0 flagged"
            )
        if len(scanned_without_hits) > 25:
            print(f"    ... and {len(scanned_without_hits) - 25} more")

    failed = [item for item in result.chat_results if item.error]
    if failed:
        print(f"\n  Chats skipped due to errors ({len(failed)}):")
        for item in failed[:10]:
            print(f"    - {item.chat_name}: {item.error}")


async def scrape_selected_chat(
    chat: DiscoveredChat,
    limit: int,
    settings: Settings | None = None,
) -> ScrapeResult:
    """Connect with the saved session and scrape the selected chat."""
    cfg = ensure_directories(settings)
    manager = TelegramClientManager(cfg)
    client = manager.create_client()

    try:
        await manager.start(client)
    except TelegramAuthError as exc:
        raise MessageScrapeError(str(exc)) from exc

    try:
        scraper = MessageScraper(client, cfg)
        return await scraper.scrape_chat(chat, limit=limit)
    finally:
        await manager.stop(client)


def prompt_for_limit(default: int = 100) -> int:
    """Prompt the user to choose an allowed scrape limit."""
    allowed = ", ".join(str(value) for value in ALLOWED_LIMITS)
    raw = input(f"Message limit ({allowed}) [{default}]: ").strip()
    if not raw:
        return normalize_limit(default)
    return parse_limit_input(raw)


async def _async_main() -> int:
    """CLI entry point: discover a chat, then collect messages."""
    cfg = ensure_directories()
    setup_logging(cfg)
    init_db(cfg)

    argv_target: str | None = None
    argv_limit: int | None = None
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        argv_target = sys.argv[1].strip()
    if len(sys.argv) >= 3 and sys.argv[2].strip():
        try:
            argv_limit = parse_limit_input(sys.argv[2].strip())
        except MessageScrapeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    manager = TelegramClientManager(cfg)
    client = manager.create_client()

    try:
        try:
            await manager.start(client)
        except TelegramAuthError as exc:
            logger.error("Authentication required before scraping: %s", exc)
            print(f"Authentication required: {exc}", file=sys.stderr)
            return 1

        try:
            mode, selection = (
                parse_scrape_target(argv_target) if argv_target else ("single", None)
            )
        except MessageScrapeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        discovery = ChatDiscovery(client)
        chats = await discovery.fetch_chats(limit=None)
        if mode != "batch":
            discovery.display_chats(chats)
        if not chats:
            return 0

        try:
            limit = argv_limit if argv_limit is not None else prompt_for_limit(default=500)
        except MessageScrapeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        scraper = MessageScraper(client, cfg)

        if mode == "batch":
            scope = selection or "all"
            selected_chats = filter_chats_for_scrape(chats, scope)
            if not selected_chats:
                print(f"No chats matched scope {scope!r}.", file=sys.stderr)
                return 1

            private_count = sum(1 for chat in selected_chats if chat.chat_type == "private chat")
            print(
                f"\nBatch scrape: {len(selected_chats)} chat(s), "
                f"scope={scope!r}, limit={limit} messages per chat"
            )
            if scope == "private":
                print(f"  Private DMs to scan: {private_count}")
            batch_result = await scraper.scrape_chats(selected_chats, limit=limit, scope=scope)
            print_multi_scrape_summary(batch_result)
            return 0

        selection = selection or prompt_for_selection()
        if not selection:
            print("No chat selected.")
            return 0

        try:
            selected = discovery.select_chat(chats, selection)
        except ChatNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if selected.chat_type == "private chat":
            print(
                "Note: each private chat is a separate person. "
                "Use `all-private` to scrape every DM at once.",
                file=sys.stderr,
            )

        result = await scraper.scrape_chat(selected, limit=limit)
        print(
            f"\nKeyword-filtered collection complete for {result.chat_name} "
            f"(ID: {result.chat_id})\n"
            f"  Scanned:              {result.processed}\n"
            f"  Flagged and stored:   {result.flagged_stored}\n"
            f"  Skipped (no keyword): {result.skipped_no_keyword}\n"
            f"  Skipped (duplicate):  {result.skipped_duplicates}"
        )
        if result.flagged_stored == 0:
            print(
                "\nNo keyword matches stored. Dummy texts must include terms like "
                "cocaine, meth, ghost gun, human trafficking, etc."
            )
        return 0
    except (ChatDiscoveryError, MessageScrapeError) as exc:
        logger.error("Message scraping failed: %s", exc)
        print(f"Message scraping failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await manager.stop(client)


def main() -> None:
    """Run interactive message collection from the command line."""
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
