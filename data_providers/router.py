"""Route requests to production or simulation data providers."""

from __future__ import annotations

from typing import Any

from data_providers.base import DataProvider
from data_providers.state import ConsoleModeState, get_mode_state, reset_to_live, update_mode_state


def get_data_provider() -> DataProvider:
    """Return the active provider — simulation never falls through to production."""
    state = get_mode_state()
    from data_providers.simulation import provider_from_state

    sim = provider_from_state(state)
    if sim is not None:
        return sim
    from data_providers.production import ProductionDataProvider

    return ProductionDataProvider()


def start_simulation_mode(
    *,
    scenario: str | None = None,
    session_name: str | None = None,
    config: dict[str, Any] | None = None,
    auto_start: bool = True,
) -> ConsoleModeState:
    """Bind the console to simulation mode (isolated Mongo database)."""
    from database import get_session_for_database, get_simulation_database_name
    from config import load_settings

    cfg = dict(config or {})
    try:
        settings = load_settings()
        with get_session_for_database(get_simulation_database_name(), settings):
            pass
    except Exception:
        pass

    if auto_start:
        from scrape_jobs.simulation_runner import start_simulation_scrape_in_background

        start_simulation_scrape_in_background(
            scenario=scenario,
            limit=int(cfg.get("bootstrap_messages", 32)),
            model=str(cfg.get("ai_model") or "").strip() or None,
            reset_database=bool(cfg.get("reset_database", True)),
        )

    return update_mode_state(
        mode="simulation",
        simulation_active=True,
        scenario=scenario,
        session_id="sim-console",
        session_name=session_name or f"Console · {scenario or 'default'}",
    )


def end_simulation_mode(*, destroy_session: bool = True) -> ConsoleModeState:
    """Tear down simulation and return the console to live data."""
    try:
        from simulation_alerts import reset_simulation_alerts

        reset_simulation_alerts()
    except Exception:
        pass
    try:
        from database import clear_simulation_database

        clear_simulation_database()
    except Exception:
        pass
    return reset_to_live()


def set_simulation_mode(
    *,
    mode: str,
    scenario: str | None = None,
    session_id: str | None = None,
    session_name: str | None = None,
) -> ConsoleModeState:
    """Switch console mode explicitly."""
    normalized = (mode or "live").lower()
    if normalized == "live":
        return end_simulation_mode()
    if normalized != "simulation":
        raise ValueError(f"Invalid mode: {mode!r}")

    if session_id:
        return update_mode_state(
            mode="simulation",
            simulation_active=True,
            scenario=scenario,
            session_id=session_id,
            session_name=session_name,
        )
    return start_simulation_mode(scenario=scenario, session_name=session_name)
