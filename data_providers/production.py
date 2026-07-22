"""Production data provider — MongoDB and export file fallbacks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT, ensure_directories, load_settings
from data_providers.base import DataProvider
from database import database_available, get_session, init_db
from exporter import build_export_payload
from behavioral_analytics import (
    behavioral_overview,
    get_behavioral_profile,
    list_behavioral_profiles,
)

DEMO_EXPORT = PROJECT_ROOT / "demo" / "export.json"
SAMPLE_EXPORT = PROJECT_ROOT / "demo" / "export.sample.json"
EXPORTS_JSON = PROJECT_ROOT / "exports" / "export.json"


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class ProductionDataProvider(DataProvider):
    """Live MongoDB + export fallbacks — never reads simulation sessions."""

    @property
    def mode(self) -> str:
        return "live"

    @property
    def source_label(self) -> str:
        return self._resolve()[0]

    def get_export_payload(self) -> dict[str, Any]:
        return self._resolve()[1]

    def _resolve(self) -> tuple[str, dict[str, Any]]:
        try:
            settings = ensure_directories(load_settings())
            if database_available(settings):
                return "mongodb", build_export_payload(settings)
        except Exception:
            pass

        for source, path in (
            ("exports", EXPORTS_JSON),
            ("demo", DEMO_EXPORT),
            ("sample", SAMPLE_EXPORT),
        ):
            payload = _load_json_file(path)
            if payload is not None:
                return source, payload

        return "empty", {
            "exported_at": "",
            "counts": {
                "chats": 0,
                "users": 0,
                "messages": 0,
                "entities": 0,
                "personnel": 0,
            },
            "chats": [],
            "users": [],
            "messages": [],
            "entities": [],
            "personnel": [],
        }

    def list_personnel(self, **kwargs: Any) -> list[dict[str, Any]]:
        settings = ensure_directories(load_settings())
        if not database_available(settings):
            return super().list_personnel(**kwargs)
        init_db(settings)
        from personnel import list_personnel

        with get_session(settings) as session:
            return list_personnel(session, **kwargs)

    def get_personnel_detail(self, user_id: int) -> dict[str, Any] | None:
        settings = ensure_directories(load_settings())
        if not database_available(settings):
            return super().get_personnel_detail(user_id)
        init_db(settings)
        from personnel import get_personnel_detail

        with get_session(settings) as session:
            return get_personnel_detail(session, user_id)

    def behavioral_overview(self) -> dict[str, Any]:
        settings = ensure_directories(load_settings())
        if not database_available(settings):
            return super().behavioral_overview()
        init_db(settings)
        with get_session(settings) as session:
            return behavioral_overview(session)

    def list_behavioral_profiles(self, **kwargs: Any) -> list[dict[str, Any]]:
        settings = ensure_directories(load_settings())
        if not database_available(settings):
            return []
        init_db(settings)
        with get_session(settings) as session:
            return list_behavioral_profiles(session, **kwargs)

    def get_behavioral_profile(self, user_id: int) -> dict[str, Any] | None:
        settings = ensure_directories(load_settings())
        if not database_available(settings):
            return None
        init_db(settings)
        with get_session(settings) as session:
            return get_behavioral_profile(session, user_id)
