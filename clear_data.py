"""Clear runtime data and remove private chats from the database."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from config import Settings, ensure_directories, load_settings
from database import get_session, init_db, reset_engine_cache
from utils import get_logger, setup_logging

logger = get_logger("clear_data")

PRIVATE_CHAT_TYPE = "private chat"
CREDENTIAL_KEYS: tuple[str, ...] = (
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_PHONE",
)


@dataclass(frozen=True)
class ClearResult:
    """Summary of cleanup actions."""

    private_chats_removed: int
    messages_removed: int
    entities_removed: int
    files_removed: tuple[str, ...]
    credentials_cleared: bool


def _release_open_resources() -> None:
    """Close logging handlers and database connections before deleting files."""
    logging.shutdown()
    reset_engine_cache()


def _delete_if_exists(path: Path) -> bool:
    """Delete a file if it exists, truncating it when deletion is blocked."""
    if not path.is_file():
        return False
    try:
        path.unlink()
        return True
    except PermissionError:
        try:
            path.write_text("", encoding="utf-8")
            return True
        except OSError:
            print(f"Warning: could not clear file: {path}", file=sys.stderr)
            return False


def _clear_directory_contents(directory: Path) -> list[str]:
    """Delete all files inside a directory, keeping the directory itself."""
    removed: list[str] = []
    if not directory.is_dir():
        return removed

    for item in directory.iterdir():
        if item.is_file():
            if _delete_if_exists(item):
                removed.append(str(item))
        elif item.is_dir():
            for nested in item.rglob("*"):
                if nested.is_file():
                    _delete_if_exists(nested)
            for nested in sorted(item.rglob("*"), reverse=True):
                if nested.is_dir():
                    nested.rmdir()
            item.rmdir()
            removed.append(str(item))
    return removed


def remove_private_chats(settings: Settings | None = None) -> tuple[int, int, int]:
    """Delete private chats and their related messages/entities."""
    cfg = ensure_directories(settings)
    init_db(cfg)

    with get_session(cfg) as session:
        result = session.delete_private_chats()
        if result["chats"] == 0:
            logger.info("No private chats found in database")
            return 0, 0, 0
        logger.info(
            "Removed private chats=%d messages=%d entities=%d",
            result["chats"],
            result["messages"],
            result["entities"],
        )
        return result["chats"], result["messages"], result["entities"]


def clear_runtime_files(settings: Settings | None = None) -> tuple[str, ...]:
    """Delete session files, logs, and exports; drop Mongo collections."""
    cfg = ensure_directories(settings)
    _release_open_resources()

    targets = [
        cfg.session_path.with_suffix(".session"),
        cfg.session_path.with_suffix(".session-journal"),
        cfg.log_file,
    ]

    removed: list[str] = []
    for path in targets:
        if _delete_if_exists(path):
            removed.append(str(path))

    # Drop MongoDB application data
    try:
        init_db(cfg)
        with get_session(cfg) as session:
            session.drop_all_data()
        removed.append("mongodb://collections (chats, users, messages, entities, counters)")
    except Exception as exc:
        print(f"Warning: could not clear MongoDB data: {exc}", file=sys.stderr)

    # Remove legacy SQLite files if present
    legacy_db = cfg.data_dir / "telegram_scraper.db"
    for path in (
        legacy_db,
        Path(f"{legacy_db}-journal"),
        legacy_db.with_suffix(".db-journal"),
        cfg.data_dir / "test.db",
    ):
        if _delete_if_exists(path):
            removed.append(str(path))

    if cfg.log_file.parent.is_dir():
        for log_file in cfg.log_file.parent.glob("*.log"):
            if _delete_if_exists(log_file):
                removed.append(str(log_file))

    removed.extend(_clear_directory_contents(cfg.exports_dir))

    print(f"Cleared {len(removed)} runtime item(s)")
    return tuple(removed)


def clear_env_credentials(settings: Settings | None = None) -> bool:
    """Remove Telegram API credentials from the local .env file."""
    cfg = settings or load_settings()
    env_path = cfg.project_root / ".env"
    if not env_path.is_file():
        print("No .env file found; nothing to clear.")
        return False

    updated = False
    new_lines: list[str] = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in CREDENTIAL_KEYS:
                new_lines.append(f"{key}=")
                updated = True
                continue
        new_lines.append(line)

    if updated:
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print("Cleared Telegram credentials from .env")
    else:
        print("No Telegram credentials found in .env")

    return updated


def run_clear(
    settings: Settings | None = None,
    *,
    private_chats: bool = False,
    runtime: bool = False,
) -> ClearResult:
    """Run selected cleanup actions."""
    if not private_chats and not runtime:
        raise ValueError("Select at least one cleanup action.")

    cfg = ensure_directories(settings)
    chats_removed = messages_removed = entities_removed = 0
    files_removed: tuple[str, ...] = ()
    credentials_cleared = False

    if private_chats:
        chats_removed, messages_removed, entities_removed = remove_private_chats(cfg)

    if runtime:
        _release_open_resources()
        files_removed = clear_runtime_files(cfg)
        credentials_cleared = clear_env_credentials(cfg)

    return ClearResult(
        private_chats_removed=chats_removed,
        messages_removed=messages_removed,
        entities_removed=entities_removed,
        files_removed=files_removed,
        credentials_cleared=credentials_cleared,
    )


def _prompt_yes_no(question: str) -> bool:
    """Ask the user for yes/no confirmation."""
    answer = input(f"{question} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def main() -> None:
    """CLI entry point for data cleanup."""
    parser = argparse.ArgumentParser(description="Clear runtime data and private chats.")
    parser.add_argument(
        "--private-chats",
        action="store_true",
        help="Remove private chat records from the database.",
    )
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="Delete session, database, logs, exports, and Telegram credentials in .env.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Remove private chats, runtime files, and Telegram credentials.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts.",
    )
    args = parser.parse_args()

    cfg = ensure_directories()
    setup_logging(cfg)

    private_chats = args.private_chats or args.all
    runtime = args.runtime or args.all

    if not private_chats and not runtime:
        print("Choose what to clear:")
        print("  1. Private chats only")
        print("  2. All runtime data (session, database, logs, exports, .env credentials)")
        print("  3. Both")
        choice = input("Enter 1, 2, or 3: ").strip()
        if choice == "1":
            private_chats = True
        elif choice == "2":
            runtime = True
        elif choice == "3":
            private_chats = True
            runtime = True
        else:
            print("No cleanup option selected.")
            raise SystemExit(1)

    if not args.yes:
        print("\nCleanup plan:")
        if private_chats:
            print("  - Remove private chats from MongoDB")
        if runtime:
            print("  - Delete Telegram session, logs, exports, and MongoDB collections")
            print("  - Clear TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE from .env")
        if not _prompt_yes_no("\nProceed?"):
            print("Cancelled.")
            raise SystemExit(0)

    result = run_clear(cfg, private_chats=private_chats, runtime=runtime)

    print("\nCleanup complete")
    print("================")
    if private_chats:
        print(f"  Private chats removed: {result.private_chats_removed}")
        print(f"  Messages removed:      {result.messages_removed}")
        print(f"  Entities removed:      {result.entities_removed}")
    if runtime:
        print(f"  Credentials cleared:   {'yes' if result.credentials_cleared else 'no'}")
        print(f"  Files removed:         {len(result.files_removed)}")
        for path in result.files_removed:
            print(f"    - {path}")

    if runtime:
        print("\nAdd new Telegram credentials to .env, then run auth.bat before scraping.")
    elif private_chats:
        print("\nChannels/groups kept. You can export or analyze remaining data safely.")


if __name__ == "__main__":
    main()
