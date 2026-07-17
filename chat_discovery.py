"""Discover and select accessible Telegram chats using an authenticated session."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Literal

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.types import Channel, Chat, User

from config import Settings, ensure_directories, load_settings
from telegram_client import TelegramAuthError, TelegramClientManager
from utils import get_logger, setup_logging

logger = get_logger("chat_discovery")

ChatType = Literal["private chat", "group", "supergroup", "channel"]

CHAT_TYPES: tuple[ChatType, ...] = (
    "private chat",
    "group",
    "supergroup",
    "channel",
)

SCRAPE_SCOPES: tuple[str, ...] = (
    "all",
    "private",
    "groups",
    "channels",
    "non-private",
)


class ChatDiscoveryError(Exception):
    """Raised when chat discovery or selection fails."""


class ChatNotFoundError(ChatDiscoveryError):
    """Raised when a chat cannot be matched by ID or index."""


@dataclass(frozen=True)
class DiscoveredChat:
    """A chat available to the authenticated account."""

    chat_id: int
    name: str
    chat_type: ChatType
    index: int
    username: str | None = None


def classify_chat_type(entity: object) -> ChatType:
    """Map a Telethon entity to a human-readable chat type."""
    if isinstance(entity, User):
        return "private chat"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, Channel):
        if entity.megagroup:
            return "supergroup"
        return "channel"
    logger.warning("Unknown entity type %s; defaulting to private chat", type(entity).__name__)
    return "private chat"


def _chat_name(dialog: object) -> str:
    """Return the best available display name for a dialog."""
    name = getattr(dialog, "name", None) or getattr(dialog, "title", None)
    if name:
        return str(name).strip()
    return "Unknown"


def _chat_username(entity: object) -> str | None:
    """Return @username when available."""
    username = getattr(entity, "username", None)
    return str(username).strip() if username else None


def filter_chats_for_scrape(
    chats: list[DiscoveredChat],
    scope: str,
) -> list[DiscoveredChat]:
    """Return chats included in a batch scrape scope."""
    normalized = scope.strip().lower()
    if normalized == "all":
        return list(chats)
    if normalized == "private":
        return [chat for chat in chats if chat.chat_type == "private chat"]
    if normalized == "channels":
        return [chat for chat in chats if chat.chat_type == "channel"]
    if normalized == "groups":
        return [chat for chat in chats if chat.chat_type in {"group", "supergroup"}]
    if normalized == "non-private":
        return [chat for chat in chats if chat.chat_type != "private chat"]
    allowed = ", ".join(SCRAPE_SCOPES)
    raise ChatDiscoveryError(f"Scope must be one of: {allowed}. Got: {scope!r}")


class ChatDiscovery:
    """List and select chats from an authenticated Telethon client."""

    def __init__(self, client: TelegramClient) -> None:
        self.client = client

    async def fetch_chats(self, limit: int | None = None) -> list[DiscoveredChat]:
        """Retrieve accessible chats/channels for the authenticated account."""
        if not await self.client.is_user_authorized():
            raise ChatDiscoveryError(
                "Telegram session is not authorized. Run telegram_client.py first."
            )

        chats: list[DiscoveredChat] = []
        seen_ids: set[int] = set()
        try:
            index = 0
            async for dialog in self.client.iter_dialogs(limit=limit):
                if dialog.id in seen_ids:
                    continue
                seen_ids.add(dialog.id)
                index += 1
                entity = dialog.entity
                chat = DiscoveredChat(
                    chat_id=dialog.id,
                    name=_chat_name(dialog),
                    chat_type=classify_chat_type(entity),
                    index=index,
                    username=_chat_username(entity),
                )
                chats.append(chat)
                logger.debug(
                    "Discovered chat index=%d id=%s type=%s name=%r",
                    chat.index,
                    chat.chat_id,
                    chat.chat_type,
                    chat.name,
                )
        except RPCError as exc:
            logger.error("Telegram API error while listing dialogs: %s", exc)
            raise ChatDiscoveryError(f"Failed to retrieve chats: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error while listing dialogs: %s", exc)
            raise ChatDiscoveryError(f"Failed to retrieve chats: {exc}") from exc

        type_counts = {chat_type: 0 for chat_type in CHAT_TYPES}
        for chat in chats:
            type_counts[chat.chat_type] = type_counts.get(chat.chat_type, 0) + 1
        logger.info(
            "Discovered %d accessible chat(s): %s",
            len(chats),
            ", ".join(f"{name}={count}" for name, count in type_counts.items() if count),
        )
        return chats

    @staticmethod
    def format_chat_line(chat: DiscoveredChat) -> str:
        """Return a single formatted line for display."""
        username = f" @{chat.username}" if chat.username else ""
        return (
            f"[{chat.index:>4}] ID: {chat.chat_id:<15} "
            f"Type: {chat.chat_type:<12} Name: {chat.name}{username}"
        )

    @staticmethod
    def display_chats(chats: list[DiscoveredChat]) -> None:
        """Print all discovered chats to stdout."""
        if not chats:
            print("No accessible chats found.")
            return

        print(f"\n{'Index':>5}  {'Chat ID':<15}  {'Type':<12}  Name")
        print("-" * 72)
        for chat in chats:
            print(ChatDiscovery.format_chat_line(chat))
        print()

    @staticmethod
    def select_chat(chats: list[DiscoveredChat], selection: str | int) -> DiscoveredChat:
        """Select a chat by Telegram ID or 1-based list index."""
        if not chats:
            raise ChatNotFoundError("No chats available to select.")

        raw = str(selection).strip()
        if not raw:
            raise ChatNotFoundError("Selection cannot be empty.")

        try:
            numeric = int(raw)
        except ValueError as exc:
            raise ChatNotFoundError(f"Invalid selection: {selection!r}") from exc

        for chat in chats:
            if chat.chat_id == numeric:
                logger.info(
                    "Selected chat by ID: id=%s name=%r type=%s",
                    chat.chat_id,
                    chat.name,
                    chat.chat_type,
                )
                return chat

        if 1 <= numeric <= len(chats):
            chat = chats[numeric - 1]
            logger.info(
                "Selected chat by index: index=%d id=%s name=%r type=%s",
                numeric,
                chat.chat_id,
                chat.name,
                chat.chat_type,
            )
            return chat

        raise ChatNotFoundError(
            f"No chat matched selection {selection!r}. "
            f"Use a listed chat ID or an index between 1 and {len(chats)}."
        )


async def discover_and_select(
    client: TelegramClient,
    selection: str | None = None,
    limit: int | None = None,
) -> tuple[list[DiscoveredChat], DiscoveredChat | None]:
    """Fetch chats, display them, and optionally select one."""
    discovery = ChatDiscovery(client)
    chats = await discovery.fetch_chats(limit=limit)
    discovery.display_chats(chats)

    if selection is None:
        return chats, None

    selected = discovery.select_chat(chats, selection)
    return chats, selected


async def run_chat_discovery(
    settings: Settings | None = None,
    selection: str | None = None,
    limit: int | None = None,
) -> DiscoveredChat | None:
    """Connect with the saved session, list chats, and optionally select one."""
    cfg = ensure_directories(settings)
    manager = TelegramClientManager(cfg)
    client = manager.create_client()

    try:
        await manager.start(client)
    except TelegramAuthError as exc:
        raise ChatDiscoveryError(str(exc)) from exc

    try:
        _chats, selected = await discover_and_select(client, selection=selection, limit=limit)
        return selected
    finally:
        await manager.stop(client)


def prompt_for_selection() -> str:
    """Prompt the user to choose a chat by index or ID."""
    return input("Select a chat by index or chat ID (or press Enter to skip): ").strip()


async def _async_main() -> int:
    """CLI entry point for chat discovery."""
    cfg = ensure_directories()
    setup_logging(cfg)

    manager = TelegramClientManager(cfg)
    client = manager.create_client()

    try:
        try:
            await manager.start(client)
        except TelegramAuthError as exc:
            logger.error("Authentication required before chat discovery: %s", exc)
            print(f"Authentication required: {exc}", file=sys.stderr)
            return 1

        discovery = ChatDiscovery(client)
        chats = await discovery.fetch_chats()
        discovery.display_chats(chats)

        if not chats:
            return 0

        selection = prompt_for_selection()
        if not selection:
            print("No chat selected.")
            return 0

        selected = discovery.select_chat(chats, selection)
        print(
            f"\nSelected: {selected.name} "
            f"(ID: {selected.chat_id}, Type: {selected.chat_type})"
        )
        return 0
    except ChatDiscoveryError as exc:
        logger.error("Chat discovery failed: %s", exc)
        print(f"Chat discovery failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await manager.stop(client)


def main() -> None:
    """Run interactive chat discovery from the command line."""
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
