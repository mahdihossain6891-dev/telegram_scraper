"""Validate local .env before running Telegram tools."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
REQUIRED_KEYS = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH")


def validate_env_file() -> list[str]:
    """Return human-readable problems with the local .env file."""
    problems: list[str] = []

    if not ENV_PATH.is_file():
        problems.append(f"Missing file: {ENV_PATH}")
        problems.append("Run setup.bat or copy .env.example to .env")
        return problems

    values = dotenv_values(ENV_PATH)
    for key in REQUIRED_KEYS:
        if not str(values.get(key, "")).strip():
            problems.append(f"{key} is empty in .env")

    api_id = str(values.get("TELEGRAM_API_ID", "")).strip()
    if api_id and not api_id.isdigit():
        problems.append("TELEGRAM_API_ID must be digits only")

    return problems


def main() -> None:
    """Print env validation results and exit non-zero on failure."""
    problems = validate_env_file()
    if not problems:
        print("Environment OK")
        raise SystemExit(0)

    print("Environment check failed")
    print("======================")
    for problem in problems:
        print(f"  - {problem}")
    print("\nFix:")
    print(f"  1. Open {ENV_PATH}")
    print("  2. Paste API ID and hash from https://my.telegram.org/apps")
    print("  3. Save the file (Ctrl+S), then rerun scrape_all.bat")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
