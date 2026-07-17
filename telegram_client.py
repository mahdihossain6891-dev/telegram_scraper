"""Telegram client authentication and session management via Telethon."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeAlias

from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from config import Settings, ensure_directories, load_settings
from utils import get_logger, setup_logging

logger = get_logger("telegram_client")

CodeProvider: TypeAlias = Callable[[], str | Awaitable[str]]
PasswordProvider: TypeAlias = Callable[[], str | Awaitable[str]]
PhoneProvider: TypeAlias = Callable[[], str | Awaitable[str]]


class TelegramAuthError(Exception):
    """Raised when Telegram authentication fails or cannot proceed."""


@dataclass(frozen=True)
class AuthCallbacks:
    """Interactive or programmatic credentials for the login flow."""

    code: CodeProvider
    password: PasswordProvider | None = None
    phone: PhoneProvider | None = None


def _mask_phone(phone: str) -> str:
    """Return a partially redacted phone number for logs."""
    digits = phone.strip()
    if len(digits) <= 4:
        return "****"
    return f"{digits[:3]}***{digits[-2:]}"


async def _resolve_value(provider: Callable[[], str | Awaitable[str]]) -> str:
    """Call a sync or async provider and return a stripped string."""
    value = provider()
    if asyncio.iscoroutine(value):
        value = await value
    result = str(value).strip()
    if not result:
        raise TelegramAuthError("Authentication callback returned an empty value.")
    return result


def create_interactive_callbacks(settings: Settings) -> AuthCallbacks:
    """Build stdin-based callbacks for manual CLI authentication."""

    def phone_provider() -> str:
        if settings.telegram_phone:
            print(f"Using phone from TELEGRAM_PHONE: {_mask_phone(settings.telegram_phone)}")
            return settings.telegram_phone
        return input("Enter your phone number (international format, e.g. +1234567890): ").strip()

    def code_provider() -> str:
        return input("Enter the verification code sent by Telegram: ").strip()

    def password_provider() -> str:
        return input("Enter your two-factor authentication password: ").strip()

    return AuthCallbacks(
        phone=phone_provider,
        code=code_provider,
        password=password_provider,
    )


class TelegramClientManager:
    """Create, authenticate, and manage a Telethon client session."""

    def __init__(
        self,
        settings: Settings,
        callbacks: AuthCallbacks | None = None,
    ) -> None:
        self.settings = settings
        self.callbacks = callbacks or create_interactive_callbacks(settings)

    def create_client(self) -> TelegramClient:
        """Return an unconnected Telethon client bound to the configured session."""
        return TelegramClient(
            str(self.settings.session_path),
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
        )

    async def connect(self, client: TelegramClient | None = None) -> TelegramClient:
        """Connect to Telegram, returning the connected client."""
        tg = client or self.create_client()
        if not tg.is_connected():
            await tg.connect()
            logger.debug("Connected to Telegram")
        return tg

    async def disconnect(self, client: TelegramClient) -> None:
        """Disconnect an active client."""
        if client.is_connected():
            await client.disconnect()
            logger.debug("Disconnected from Telegram")

    async def is_authorized(self, client: TelegramClient) -> bool:
        """Return True if the session is already authenticated."""
        return await client.is_user_authorized()

    async def resolve_phone(self) -> str:
        """Return the phone number used for sign-in."""
        if self.callbacks.phone is not None:
            return await _resolve_value(self.callbacks.phone)
        if self.settings.telegram_phone:
            return self.settings.telegram_phone
        raise TelegramAuthError(
            "Phone number is required. Set TELEGRAM_PHONE in .env or provide a phone callback."
        )

    async def authenticate(self, client: TelegramClient) -> None:
        """Ensure the client session is authorized, prompting when needed."""
        if await self.is_authorized(client):
            me = await client.get_me()
            display = me.username or me.first_name or me.id
            logger.info("Existing session authorized for %s", display)
            return

        phone = await self.resolve_phone()
        logger.info("Requesting verification code for %s", _mask_phone(phone))
        await client.send_code_request(phone)

        code = await _resolve_value(self.callbacks.code)
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            if self.callbacks.password is None:
                raise TelegramAuthError(
                    "Two-factor authentication is enabled but no password callback was provided."
                ) from None
            password = await _resolve_value(self.callbacks.password)
            await client.sign_in(password=password)
        except PhoneCodeInvalidError as exc:
            raise TelegramAuthError("Invalid verification code.") from exc
        except PhoneCodeExpiredError as exc:
            raise TelegramAuthError("Verification code expired. Request a new code and retry.") from exc

        if not await self.is_authorized(client):
            raise TelegramAuthError("Authentication finished but the session is still unauthorized.")

        me = await client.get_me()
        display = me.username or me.first_name or me.id
        logger.info("Successfully authenticated as %s", display)

    async def start(self, client: TelegramClient | None = None) -> TelegramClient:
        """Connect and authenticate, returning a ready-to-use client."""
        tg = await self.connect(client)
        await self.authenticate(tg)
        return tg

    async def stop(self, client: TelegramClient) -> None:
        """Disconnect the client after use."""
        await self.disconnect(client)


def session_file_exists(settings: Settings) -> bool:
    """Return True if a Telethon session file exists on disk."""
    return settings.session_path.with_suffix(".session").is_file()


async def authenticate(settings: Settings | None = None, callbacks: AuthCallbacks | None = None) -> TelegramClient:
    """Connect, authenticate if needed, and return an authorized client."""
    cfg = ensure_directories(settings)
    manager = TelegramClientManager(cfg, callbacks)
    return await manager.start()


async def _async_main() -> int:
    """CLI entry point for initial Telegram login."""
    cfg = ensure_directories()
    setup_logging(cfg)

    manager = TelegramClientManager(cfg)
    client = manager.create_client()
    try:
        await manager.start(client)
        me = await client.get_me()
        username = f"@{me.username}" if me.username else "(no username)"
        print(f"Authenticated successfully as {me.first_name} {username}")
        return 0
    except TelegramAuthError as exc:
        logger.error("Authentication failed: %s", exc)
        print(f"Authentication failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await manager.stop(client)


def main() -> None:
    """Run interactive Telegram authentication from the command line."""
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
