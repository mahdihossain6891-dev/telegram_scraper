"""Persist console live/simulation mode across uvicorn reloads."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT

_MODE_FILE = PROJECT_ROOT / "data" / "console_mode.json"
_file_lock = threading.Lock()


def load_persisted_mode() -> dict[str, Any] | None:
    with _file_lock:
        if not _MODE_FILE.is_file():
            return None
        try:
            raw = json.loads(_MODE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        return raw


def save_persisted_mode(payload: dict[str, Any]) -> None:
    with _file_lock:
        try:
            _MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _MODE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass


def clear_persisted_mode() -> None:
    with _file_lock:
        try:
            if _MODE_FILE.is_file():
                _MODE_FILE.unlink()
        except OSError:
            pass
