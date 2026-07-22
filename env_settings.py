"""Read and update project ``.env`` values from the dashboard settings UI."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from config import PROJECT_ROOT

ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

SECRET_KEYS: frozenset[str] = frozenset(
    {
        "TELEGRAM_API_HASH",
        "TELEGRAM_BOT_TOKEN",
        "AI_API_KEY",
        "OPENROUTER_API_KEY",
    }
)

MANAGED_KEYS: tuple[str, ...] = (
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_PHONE",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALERT_CHAT_ID",
    "AI_ENABLED",
    "AI_CHAT_PROVIDER",
    "AI_CHAT_MODEL",
    "AI_EMBEDDING_PROVIDER",
    "AI_EMBEDDING_MODEL",
    "AI_API_BASE_URL",
    "AI_API_KEY",
    "OPENROUTER_API_KEY",
    "AI_OLLAMA_BASE_URL",
)

PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {
        "",
        "your_api_hash_here",
        "12345678",
    }
)


@dataclass(frozen=True, slots=True)
class EnvSettingsSnapshot:
    """Dashboard-friendly view of managed ``.env`` keys."""

    values: dict[str, str]
    configured: dict[str, bool]
    env_path: str
    env_exists: bool


def _ensure_env_file() -> Path:
    if ENV_PATH.is_file():
        return ENV_PATH
    if ENV_EXAMPLE_PATH.is_file():
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        return ENV_PATH
    ENV_PATH.write_text("", encoding="utf-8")
    return ENV_PATH


def _is_configured(key: str, value: str | None) -> bool:
    raw = (value or "").strip()
    if not raw:
        return False
    if key == "TELEGRAM_API_ID" and raw in PLACEHOLDER_VALUES:
        return False
    if key in SECRET_KEYS and raw in PLACEHOLDER_VALUES:
        return False
    return True


def _mask_secret(value: str) -> str:
    return ""


def load_env_settings() -> EnvSettingsSnapshot:
    """Return managed keys with secrets omitted from ``values``."""
    path = _ensure_env_file()
    merged = {**dotenv_values(path), **os.environ}
    values: dict[str, str] = {}
    configured: dict[str, bool] = {}
    for key in MANAGED_KEYS:
        raw = str(merged.get(key, "") or "").strip()
        configured[key] = _is_configured(key, raw)
        if key in SECRET_KEYS:
            values[key] = _mask_secret(raw)
        else:
            values[key] = raw
    return EnvSettingsSnapshot(
        values=values,
        configured=configured,
        env_path=str(path),
        env_exists=path.is_file(),
    )


def _normalize_updates(updates: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in updates.items():
        if key not in MANAGED_KEYS:
            continue
        if value is None:
            continue
        normalized[key] = str(value).strip()
    return normalized


def _should_skip_secret_update(key: str, new_value: str, current_value: str) -> bool:
    if key not in SECRET_KEYS:
        return False
    if new_value:
        return False
    return _is_configured(key, current_value)


def update_env_settings(updates: dict[str, Any]) -> EnvSettingsSnapshot:
    """Merge updates into ``.env`` without overwriting secrets when left blank."""
    path = _ensure_env_file()
    current = {k: str(v or "").strip() for k, v in dotenv_values(path).items()}
    incoming = _normalize_updates(updates)

    for key, new_value in incoming.items():
        if _should_skip_secret_update(key, new_value, current.get(key, "")):
            continue
        current[key] = new_value

    if incoming.get("AI_API_KEY") and not incoming.get("OPENROUTER_API_KEY"):
        current["OPENROUTER_API_KEY"] = incoming["AI_API_KEY"]
    if incoming.get("OPENROUTER_API_KEY") and not incoming.get("AI_API_KEY"):
        current["AI_API_KEY"] = incoming["OPENROUTER_API_KEY"]

    # Settings page collects OpenRouter only — enable Sébastien defaults when a key is set.
    openrouter = (current.get("OPENROUTER_API_KEY") or current.get("AI_API_KEY") or "").strip()
    if openrouter and (incoming.get("OPENROUTER_API_KEY") or incoming.get("AI_API_KEY")):
        current["AI_ENABLED"] = "true"
        current["AI_CHAT_PROVIDER"] = incoming.get("AI_CHAT_PROVIDER") or "openrouter"
        current["AI_API_BASE_URL"] = (
            incoming.get("AI_API_BASE_URL")
            or current.get("AI_API_BASE_URL")
            or "https://openrouter.ai/api/v1"
        )
        current["AI_CHAT_MODEL"] = (
            incoming.get("AI_CHAT_MODEL")
            or current.get("AI_CHAT_MODEL")
            or "openai/gpt-4o-mini"
        )

    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    output: list[str] = []

    assignment = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=")
    for line in lines:
        match = assignment.match(line.strip())
        if not match:
            output.append(line)
            continue
        key = match.group(1)
        if key in current:
            output.append(f"{key}={current[key]}")
            seen.add(key)
        else:
            output.append(line)

    for key in MANAGED_KEYS:
        if key in current and key not in seen:
            output.append(f"{key}={current[key]}")

    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    return load_env_settings()


def env_settings_payload() -> dict[str, Any]:
    snapshot = load_env_settings()
    return {
        "values": snapshot.values,
        "configured": snapshot.configured,
        "env_path": snapshot.env_path,
        "env_exists": snapshot.env_exists,
        "managed_keys": list(MANAGED_KEYS),
        "secret_keys": sorted(SECRET_KEYS),
    }
