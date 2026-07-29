"""Background scrape + export loop to keep cloud dashboards in sync."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from config import Settings, ensure_directories, load_settings
from exporter import run_export
from utils import get_logger, setup_logging

logger = get_logger("auto_update")

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
MESSAGE_SCRAPER = PROJECT_ROOT / "message_scraper.py"
BOT_POST = PROJECT_ROOT / "bot_post_test.py"


@dataclass(frozen=True)
class AutoUpdateConfig:
    """Settings for the local auto-update loop."""

    scrape_target: str | None
    interval_seconds: int
    scrape_limit: int
    post_bot_messages: bool
    sync_vercel: bool
    git_push: bool


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def load_auto_update_config() -> AutoUpdateConfig:
    """Load auto-update settings from .env and environment."""
    values = {**dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    for key, value in values.items():
        if value is not None and str(value).strip():
            os.environ.setdefault(key, str(value).strip())

    interval_minutes = int(str(values.get("AUTO_UPDATE_INTERVAL_MINUTES", "5")).strip() or "5")
    scrape_limit = int(str(values.get("AUTO_UPDATE_SCRAPE_LIMIT", "1000")).strip() or "1000")
    scrape_target = str(values.get("AUTO_UPDATE_SCRAPE_TARGET", "")).strip() or None

    return AutoUpdateConfig(
        scrape_target=scrape_target,
        interval_seconds=max(60, interval_minutes * 60),
        scrape_limit=scrape_limit if scrape_limit in (100, 500, 1000) else 1000,
        post_bot_messages=_env_bool("AUTO_UPDATE_BOT_POST", False),
        sync_vercel=_env_bool("AUTO_UPDATE_SYNC_VERCEL", True),
        git_push=_env_bool("AUTO_UPDATE_GIT_PUSH", False),
    )


def run_subprocess(args: list[str]) -> int:
    """Run a subprocess and return its exit code."""
    logger.info("Running: %s", " ".join(args))
    completed = subprocess.run(args, cwd=PROJECT_ROOT, check=False)
    return int(completed.returncode)


def scrape_target(target: str, limit: int) -> int:
    """Scrape one chat index/scope using the existing CLI."""
    python_exe = str(PYTHON if PYTHON.is_file() else sys.executable)
    return run_subprocess(
        [python_exe, str(MESSAGE_SCRAPER), target, str(limit)],
    )


def post_bot_demo_messages() -> int:
    """Post built-in demo messages through the configured Telegram bot."""
    python_exe = str(PYTHON if PYTHON.is_file() else sys.executable)
    return run_subprocess([python_exe, str(BOT_POST), "--all"])


def copy_export(settings: Settings, config: AutoUpdateConfig) -> None:
    """Export MongoDB data and copy JSON to the Next.js public folder."""
    result = run_export(settings)
    logger.info(
        "Exported %s messages, %s chats, %s entities",
        result.message_count,
        result.chat_count,
        result.entity_count,
    )

    source = settings.exports_dir / "export.json"
    if not source.is_file():
        raise FileNotFoundError(f"Missing export file: {source}")

    if config.sync_vercel:
        vercel_dir = PROJECT_ROOT / "web" / "public" / "data"
        vercel_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, vercel_dir / "export.json")
        logger.info("Copied export to web/public/data/export.json")


def git_push_exports() -> int:
    """Commit and push export files for Vercel redeploy."""
    commands = [
        ["git", "add", "-f", "web/public/data/export.json"],
        ["git", "commit", "-m", "Auto-update dashboard export data"],
        ["git", "push", "origin", "HEAD"],
    ]
    for args in commands:
        code = run_subprocess(args)
        if code != 0:
            return code
    return 0


def run_cycle(settings: Settings, config: AutoUpdateConfig) -> None:
    """Run one scrape/export/sync cycle."""
    if config.post_bot_messages:
        post_bot_demo_messages()

    if config.scrape_target:
        scrape_target(config.scrape_target, config.scrape_limit)

    copy_export(settings, config)

    if config.git_push:
        git_push_exports()


def main() -> int:
    """Run the auto-update loop until interrupted."""
    setup_logging()
    config = load_auto_update_config()

    try:
        settings = ensure_directories(load_settings())
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        print("Fill TELEGRAM_API_ID and TELEGRAM_API_HASH in .env before running auto_update.bat")
        return 1

    print("Auto-update loop started")
    print(f"  Interval:        every {config.interval_seconds // 60} minute(s)")
    print(f"  Scrape target:     {config.scrape_target or '(export only)'}")
    print(f"  Bot demo posts:    {config.post_bot_messages}")
    print(f"  Sync Vercel:       {config.sync_vercel}")
    print(f"  Git push:          {config.git_push}")
    print("Press Ctrl+C to stop.\n")

    while True:
        started = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{started}] Running update cycle...")
        try:
            run_cycle(settings, config)
            print(f"[{started}] Cycle complete.\n")
        except Exception as exc:
            logger.exception("Auto-update cycle failed")
            print(f"[{started}] Cycle failed: {exc}\n")

        time.sleep(config.interval_seconds)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nAuto-update stopped.")
        raise SystemExit(0)
