"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root is the directory containing this file.
PROJECT_ROOT: Path = Path(__file__).resolve().parent

# Load .env from project root if present.
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str | None
    telegram_session_name: str
    database_url: str
    log_level: str
    log_file: Path
    data_dir: Path
    exports_dir: Path
    project_root: Path

    @property
    def session_path(self) -> Path:
        """Absolute path to the Telethon session file (without extension)."""
        return self.data_dir / self.telegram_session_name

    @property
    def database_path(self) -> Path:
        """Legacy path helper — MongoDB has no local file; return data_dir marker."""
        return self.data_dir / "mongodb.url"

    @property
    def mongodb_uri(self) -> str:
        """Return the MongoDB connection URI."""
        return self.database_url


def _require_env(key: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.getenv(key)
    if value is None or value.strip() == "":
        env_path = PROJECT_ROOT / ".env"
        if env_path.is_file():
            raise ValueError(
                f"{key} is empty in .env. Open {env_path}, add your value from "
                f"https://my.telegram.org/apps, save the file, then retry."
            )
        raise ValueError(
            f"Missing required environment variable: {key}. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value.strip()


def _optional_env(key: str, default: str = "") -> str | None:
    """Return an optional environment variable, or None if empty."""
    value = os.getenv(key, default).strip()
    return value if value else None


def _resolve_path(raw: str, base: Path) -> Path:
    """Resolve a path relative to base if not already absolute."""
    path = Path(raw)
    return path if path.is_absolute() else base / path


def load_settings() -> Settings:
    """Load and validate settings from the environment.

    Returns:
        A validated Settings instance.

    Raises:
        ValueError: If required variables are missing or invalid.
    """
    api_id_raw = _require_env("TELEGRAM_API_ID")
    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise ValueError(
            f"TELEGRAM_API_ID must be an integer, got: {api_id_raw!r}"
        ) from exc

    api_hash = _require_env("TELEGRAM_API_HASH")
    phone = _optional_env("TELEGRAM_PHONE")
    session_name = os.getenv("TELEGRAM_SESSION_NAME", "telegram_scraper").strip()
    database_url = os.getenv(
        "MONGODB_URI",
        os.getenv("DATABASE_URL", "mongodb://127.0.0.1:27017/telegram_scraper"),
    ).strip()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    log_file = _resolve_path(
        os.getenv("LOG_FILE", "logs/app.log").strip(),
        PROJECT_ROOT,
    )
    data_dir = _resolve_path(
        os.getenv("DATA_DIR", "data").strip(),
        PROJECT_ROOT,
    )
    exports_dir = _resolve_path(
        os.getenv("EXPORTS_DIR", "exports").strip(),
        PROJECT_ROOT,
    )

    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level not in valid_levels:
        raise ValueError(
            f"LOG_LEVEL must be one of {sorted(valid_levels)}, got: {log_level!r}"
        )

    return Settings(
        telegram_api_id=api_id,
        telegram_api_hash=api_hash,
        telegram_phone=phone,
        telegram_session_name=session_name,
        database_url=database_url,
        log_level=log_level,
        log_file=log_file,
        data_dir=data_dir,
        exports_dir=exports_dir,
        project_root=PROJECT_ROOT,
    )


def load_minimal_settings() -> Settings:
    """Load path settings for export-only dashboard mode without Telegram credentials."""
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    log_file = _resolve_path(
        os.getenv("LOG_FILE", "logs/app.log").strip(),
        PROJECT_ROOT,
    )
    data_dir = _resolve_path(
        os.getenv("DATA_DIR", "data").strip(),
        PROJECT_ROOT,
    )
    exports_dir = _resolve_path(
        os.getenv("EXPORTS_DIR", "exports").strip(),
        PROJECT_ROOT,
    )
    database_url = os.getenv(
        "MONGODB_URI",
        os.getenv("DATABASE_URL", "mongodb://127.0.0.1:27017/telegram_scraper"),
    ).strip()
    session_name = os.getenv("TELEGRAM_SESSION_NAME", "telegram_scraper").strip()

    return Settings(
        telegram_api_id=0,
        telegram_api_hash="dashboard-only",
        telegram_phone=None,
        telegram_session_name=session_name,
        database_url=database_url,
        log_level=log_level,
        log_file=log_file,
        data_dir=data_dir,
        exports_dir=exports_dir,
        project_root=PROJECT_ROOT,
    )


def ensure_directories(settings: Settings | None = None) -> Settings:
    """Create required runtime directories and return settings.

    Args:
        settings: Optional pre-loaded settings. Loaded from env if omitted.

    Returns:
        The settings used to create directories.
    """
    cfg = settings or load_settings()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.exports_dir.mkdir(parents=True, exist_ok=True)
    cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
    return cfg
