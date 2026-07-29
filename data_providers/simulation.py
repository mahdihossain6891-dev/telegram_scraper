"""Simulation data provider — isolated synthetic console data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from config import ensure_directories, load_settings
from data_providers.base import DataProvider
from data_providers.state import ConsoleModeState
from database import database_available, get_simulation_database_name
from exporter import build_export_payload


class SimulationDataProvider(DataProvider):
    """Serves synthetic data from the simulation MongoDB."""

    def __init__(self, *, session_id: str, scenario: str | None = None) -> None:
        self._session_id = session_id
        self._scenario = scenario

    @property
    def mode(self) -> str:
        return "simulation"

    @property
    def source_label(self) -> str:
        if self._mongo_has_messages():
            return "simulation_mongodb"
        return "simulation"

    @property
    def session_id(self) -> str:
        return self._session_id

    def _mongo_available(self) -> bool:
        try:
            return database_available(load_settings())
        except Exception:
            return False

    def _mongo_has_messages(self) -> bool:
        if not self._mongo_available():
            return False
        try:
            payload = build_export_payload(
                database_name=get_simulation_database_name(),
            )
            return int((payload.get("counts") or {}).get("messages") or 0) > 0
        except Exception:
            return False

    def get_export_payload(self) -> dict[str, Any]:
        if self._mongo_has_messages():
            payload = build_export_payload(database_name=get_simulation_database_name())
        else:
            payload = {
                "exported_at": datetime.utcnow().isoformat(),
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
        payload.setdefault("simulation", {})
        payload["simulation"].update(
            {
                "session_id": self._session_id,
                "scenario": self._scenario,
                "environment": "simulation",
                "isolated": True,
                "database": get_simulation_database_name(),
            }
        )
        return payload

    def behavioral_overview(self) -> dict[str, Any]:
        if not self._mongo_has_messages():
            return {
                "total_users": 0,
                "distribution": {
                    "Normal": 0,
                    "Unusual": 0,
                    "Suspicious": 0,
                    "High Risk": 0,
                },
                "avg_messages_per_day": 0,
                "avg_active_hour": None,
                "top_outliers": [],
                "recent_behavior_changes": [],
                "highest_forwarding": [],
                "highest_media": [],
                "activity_spikes": [],
            }
        from behavioral_analytics import behavioral_overview
        from database import get_session_for_database

        settings = ensure_directories(load_settings())
        with get_session_for_database(get_simulation_database_name(), settings) as session:
            return behavioral_overview(session)

    def list_behavioral_profiles(self, **kwargs: Any) -> list[dict[str, Any]]:
        if not self._mongo_has_messages():
            return []
        from behavioral_analytics import list_behavioral_profiles
        from database import get_session_for_database

        settings = ensure_directories(load_settings())
        with get_session_for_database(get_simulation_database_name(), settings) as session:
            return list_behavioral_profiles(session, **kwargs)

    def get_behavioral_profile(self, user_id: int) -> dict[str, Any] | None:
        if not self._mongo_has_messages():
            return None
        from behavioral_analytics import get_behavioral_profile
        from database import get_session_for_database

        settings = ensure_directories(load_settings())
        with get_session_for_database(get_simulation_database_name(), settings) as session:
            return get_behavioral_profile(session, user_id)

    def list_personnel(self, **kwargs: Any) -> list[dict[str, Any]]:
        if not self._mongo_has_messages():
            return super().list_personnel(**kwargs)
        from database import get_session_for_database
        from personnel import list_personnel

        settings = ensure_directories(load_settings())
        with get_session_for_database(get_simulation_database_name(), settings) as session:
            return list_personnel(session, **kwargs)

    def get_personnel_detail(self, user_id: int) -> dict[str, Any] | None:
        if not self._mongo_has_messages():
            return super().get_personnel_detail(user_id)
        from database import get_session_for_database
        from personnel import get_personnel_detail

        settings = ensure_directories(load_settings())
        with get_session_for_database(get_simulation_database_name(), settings) as session:
            return get_personnel_detail(session, user_id)

    def allows_live_operations(self) -> bool:
        return False

    def allows_simulation_scrape(self) -> bool:
        return True


def provider_from_state(state: ConsoleModeState) -> SimulationDataProvider | None:
    if state.mode != "simulation" or not state.simulation_active or not state.session_id:
        return None
    return SimulationDataProvider(
        session_id=state.session_id,
        scenario=state.scenario,
    )
