"""Post demo keyword test messages to a monitored Telegram channel via Bot API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

from dotenv import dotenv_values

from utils import get_logger, setup_logging

logger = get_logger("bot_post_test")

# Clearly fake OSINT lab messages for keyword-filter testing only.
DEFAULT_TEST_MESSAGES: tuple[str, ...] = (
    "[TEST] Demo alert: cocaine shipment update for monitoring dashboard.",
    "[TEST] Sample post mentioning ghost gun for firearms keyword detection.",
    "[TEST] Exercise message about human trafficking ring (demo only).",
    "[TEST] Keyword check: meth distribution chatter — not real intelligence.",
    "[TEST] Firearms flag test: illegal gun sale mention for scraper lab.",
    "[TEST] Narcotics flag test: fentanyl shipment phrase for dashboard QA.",
)


@dataclass(frozen=True)
class BotPostConfig:
    """Settings required to post through the Telegram Bot API."""

    bot_token: str
    channel: str


@dataclass(frozen=True)
class PostResult:
    """Outcome of a single Bot API sendMessage call."""

    message_text: str
    message_id: int | None
    ok: bool
    error: str | None = None


class BotPostError(Exception):
    """Raised when bot posting cannot proceed."""


def load_bot_post_config() -> BotPostConfig:
    """Load bot token and target channel from environment variables."""
    values = {**dotenv_values(".env"), **os.environ}
    token = str(values.get("TELEGRAM_BOT_TOKEN", "")).strip()
    channel = str(values.get("TEST_CHANNEL_USERNAME", "")).strip()

    if not token:
        raise BotPostError(
            "TELEGRAM_BOT_TOKEN is missing. Create a bot with @BotFather and add the token to .env"
        )
    if not channel:
        raise BotPostError(
            "TEST_CHANNEL_USERNAME is missing. Set it to your public channel username, e.g. osint_test_lab"
        )

    if channel.startswith("https://t.me/"):
        channel = channel.removeprefix("https://t.me/").strip("/")
    channel = channel.removeprefix("@")

    return BotPostConfig(bot_token=token, channel=f"@{channel}")


def send_channel_message(config: BotPostConfig, text: str) -> PostResult:
    """Send one message to the configured channel using Telegram Bot API."""
    url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": config.channel,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return PostResult(message_text=text, message_id=None, ok=False, error=detail or str(exc))
    except urllib.error.URLError as exc:
        return PostResult(message_text=text, message_id=None, ok=False, error=str(exc))

    if not body.get("ok"):
        return PostResult(
            message_text=text,
            message_id=None,
            ok=False,
            error=str(body.get("description", "Unknown Bot API error")),
        )

    message_id = body.get("result", {}).get("message_id")
    return PostResult(message_text=text, message_id=int(message_id) if message_id else None, ok=True)


def post_test_messages(
    config: BotPostConfig,
    messages: tuple[str, ...],
) -> list[PostResult]:
    """Post each message in order."""
    results: list[PostResult] = []
    for text in messages:
        logger.info("Posting test message to %s", config.channel)
        result = send_channel_message(config, text)
        results.append(result)
        if not result.ok:
            logger.error("Failed to post message: %s", result.error)
        else:
            logger.info("Posted message_id=%s", result.message_id)
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(
        description="Post demo suspicious keyword messages to a Telegram test channel.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Send all built-in demo test messages.",
    )
    parser.add_argument(
        "--index",
        type=int,
        help="Send one built-in message by 1-based index.",
    )
    parser.add_argument(
        "--message",
        "-m",
        help="Send a custom message (wrap in quotes).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List built-in demo messages and exit.",
    )
    return parser.parse_args(argv)


def select_messages(args: argparse.Namespace) -> tuple[str, ...]:
    """Return the message batch selected on the command line."""
    if args.list:
        return ()

    if args.message:
        return (args.message.strip(),)

    if args.index is not None:
        if args.index < 1 or args.index > len(DEFAULT_TEST_MESSAGES):
            raise BotPostError(
                f"--index must be between 1 and {len(DEFAULT_TEST_MESSAGES)}"
            )
        return (DEFAULT_TEST_MESSAGES[args.index - 1],)

    if args.all:
        return DEFAULT_TEST_MESSAGES

    # Default: send the first demo message only.
    return (DEFAULT_TEST_MESSAGES[0],)


def print_message_list() -> None:
    """Print numbered demo messages."""
    print("Built-in demo test messages:")
    for index, message in enumerate(DEFAULT_TEST_MESSAGES, start=1):
        print(f"  {index}. {message}")


def print_results(config: BotPostConfig, results: list[PostResult]) -> None:
    """Print a human-readable summary."""
    print(f"\nTarget channel: {config.channel}")
    success_count = sum(1 for item in results if item.ok)
    print(f"Posted {success_count}/{len(results)} message(s)")
    for result in results:
        status = "OK" if result.ok else "FAILED"
        preview = result.message_text[:80].replace("\n", " ")
        if result.ok:
            print(f"  [{status}] message_id={result.message_id} :: {preview}")
        else:
            print(f"  [{status}] {preview}")
            print(f"         {result.error}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    setup_logging()
    args = parse_args(argv)

    if args.list:
        print_message_list()
        return 0

    try:
        config = load_bot_post_config()
        messages = select_messages(args)
    except BotPostError as exc:
        print(f"Error: {exc}")
        print("\nSetup checklist:")
        print("  1. Message @BotFather -> /newbot -> copy token to TELEGRAM_BOT_TOKEN in .env")
        print("  2. Open your channel -> Manage -> Administrators -> Add bot -> allow Post messages")
        print("  3. Set TEST_CHANNEL_USERNAME=osint_test_lab in .env (no @ needed)")
        return 1

    if not messages:
        print("No messages selected.")
        return 1

    results = post_test_messages(config, messages)
    print_results(config, results)

    if not all(item.ok for item in results):
        print(
            "\nIf posting failed, confirm the bot is an admin in the channel "
            "with permission to post messages."
        )
        return 1

    print("\nNext steps:")
    print("  1. Run scrape on the test channel")
    print("  2. Run .\\dashboard.bat for live local Next.js (Mongo via FastAPI)")
    print("  3. Or run export.bat + vercel_export.bat and push for Vercel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
