"""Collect flagged messages from a selected chat and store them in SQLite."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy.orm import Session
from telethon import TelegramClient, utils
from telethon.errors import RPCError
from telethon.tl.types import Message as TelethonMessage
from telethon.tl.types import User as TelethonUser

from chat_discovery import (
    ChatDiscovery,
    ChatDiscoveryError,
    ChatNotFoundError,
    DiscoveredChat,
    prompt_for_selection,
)
from config import Settings, ensure_directories, load_settings
from database import get_session, init_db, message_exists
from entity_extractor import store_entities_for_message
from keyword_filter import KeywordScanResult, scan_message_text
from models import Chat, ExtractedEntity, Message, User
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


def parse_telethon_message(message: TelethonMessage, chat_id: int) -> ParsedMessage:
    """Convert a Telethon message into database-ready fields."""
    forward_chat_id, forward_message_id = _forward_info(message)
    sender_id, username, first_name, last_name = _sender_fields(message)

    return ParsedMessage(
        message_id=message.id,
        chat_id=chat_id,
        sender_id=sender_id,
        timestamp=message.date,
        text=message.message,
        media_type=_media_type(message),
        reply_to_message_id=_reply_id(message),
        forward_from_chat_id=forward_chat_id,
        forward_from_message_id=forward_message_id,
        views=getattr(message, "views", None),
        sender_username=username,
        sender_first_name=first_name,
        sender_last_name=last_name,
    )


def ensure_chat_record(session: Session, chat: DiscoveredChat) -> Chat:
    """Insert the chat metadata if it is not already stored."""
    existing = session.get(Chat, chat.chat_id)
    if existing is not None:
        existing.title = chat.name
        existing.username = chat.username
        existing.chat_type = chat.chat_type
        return existing

    record = Chat(
        id=chat.chat_id,
        title=chat.name,
        username=chat.username,
        chat_type=chat.chat_type,
    )
    session.add(record)
    session.flush()
    logger.debug("Stored chat metadata for id=%s name=%r", chat.chat_id, chat.name)
    return record


def ensure_user_record(session: Session, parsed: ParsedMessage) -> None:
    """Insert or update a sender record when sender information is available."""
    if parsed.sender_id is None:
        return

    existing = session.get(User, parsed.sender_id)
    if existing is not None:
        if parsed.sender_username is not None:
            existing.username = parsed.sender_username
        if parsed.sender_first_name is not None:
            existing.first_name = parsed.sender_first_name
        if parsed.sender_last_name is not None:
            existing.last_name = parsed.sender_last_name
        return

    session.add(
        User(
            id=parsed.sender_id,
            username=parsed.sender_username,
            first_name=parsed.sender_first_name,
            last_name=parsed.sender_last_name,
        )
    )
    session.flush()


def store_parsed_message(
    session: Session,
    parsed: ParsedMessage,
    keyword_scan: KeywordScanResult,
) -> bool:
    """Store a flagged message and its keyword hits, skipping duplicates."""
    if not keyword_scan.matched:
        return False

    if message_exists(session, parsed.chat_id, parsed.message_id):
        return False

    ensure_user_record(session, parsed)
    record = Message(
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
    )
    session.add(record)
    session.flush()

    for hit in keyword_scan.hits:
        session.add(
            ExtractedEntity(
                message_row_id=record.id,
                entity_type=hit.category,
                entity_value=hit.keyword,
            )
        )

    content_stored, _content_skipped = store_entities_for_message(
        session,
        record.id,
        parsed.text,
    )

    logger.info(
        "Flagged message_id=%s chat_id=%s categories=%s keywords=%s content_entities=%d",
        parsed.message_id,
        parsed.chat_id,
        ",".join(keyword_scan.categories),
        ",".join(hit.keyword for hit in keyword_scan.hits),
        content_stored,
    )
    session.flush()
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

        try:
            async for message in self.client.iter_messages(chat.chat_id, limit=limit):
                if not isinstance(message, TelethonMessage):
                    continue

                pending.append(message)
                if len(pending) >= self.batch_size:
                    batch_flagged, batch_dupes, batch_no_keyword = self._store_batch(chat, pending)
                    flagged_stored += batch_flagged
                    skipped_duplicates += batch_dupes
                    skipped_no_keyword += batch_no_keyword
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
                batch_flagged, batch_dupes, batch_no_keyword = self._store_batch(chat, pending)
                flagged_stored += batch_flagged
                skipped_duplicates += batch_dupes
                skipped_no_keyword += batch_no_keyword
                processed += len(pending)
        except RPCError as exc:
            logger.error("Telegram API error during message collection: %s", exc)
            raise MessageScrapeError(f"Failed to collect messages: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error during message collection: %s", exc)
            raise MessageScrapeError(f"Failed to collect messages: {exc}") from exc

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
    ) -> tuple[int, int, int]:
        """Persist keyword-flagged messages from a batch."""
        flagged_stored = 0
        skipped_duplicates = 0
        skipped_no_keyword = 0
        chat_record_created = False

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

        return flagged_stored, skipped_duplicates, skipped_no_keyword


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

    argv_selection: str | None = None
    argv_limit: int | None = None
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        argv_selection = sys.argv[1].strip()
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

        discovery = ChatDiscovery(client)
        chats = await discovery.fetch_chats()
        discovery.display_chats(chats)
        if not chats:
            return 0

        selection = argv_selection or prompt_for_selection()
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
                "Warning: private chats are not recommended for OSINT collection. "
                "Pick a channel or group instead.",
                file=sys.stderr,
            )

        try:
            limit = argv_limit if argv_limit is not None else prompt_for_limit()
        except MessageScrapeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        scraper = MessageScraper(client, cfg)
        result = await scraper.scrape_chat(selected, limit=limit)
        print(
            f"\nKeyword-filtered collection complete for {result.chat_name} "
            f"(ID: {result.chat_id})\n"
            f"  Scanned:              {result.processed}\n"
            f"  Flagged and stored:   {result.flagged_stored}\n"
            f"  Skipped (no keyword): {result.skipped_no_keyword}\n"
            f"  Skipped (duplicate):  {result.skipped_duplicates}"
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
