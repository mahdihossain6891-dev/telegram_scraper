"""Shared test fixtures for the simulator package."""

from __future__ import annotations

from pathlib import Path

from simulator.config import SimulationSettings
from simulator.enums import EnvironmentType, SimulationSpeed


def make_settings(
    *,
    enabled: bool = False,
    auto_start: bool = False,
    default_environment: EnvironmentType = EnvironmentType.LIVE,
    strict_isolation_enabled: bool = True,
    allow_future_environments: bool = False,
    live_database_name: str = "telegram_scraper",
    simulation_database_name: str = "test_simulation_db",
    live_export_path: Path | None = None,
    simulation_export_path: Path | None = None,
    random_seed: int | None = 42,
    log_level: str = "DEBUG",
    default_speed: SimulationSpeed = SimulationSpeed.REALTIME,
    default_users: int = 10,
    default_groups: int = 2,
    project_root: Path | None = None,
) -> SimulationSettings:
    root = project_root or Path(".")
    return SimulationSettings(
        enabled=enabled,
        auto_start=auto_start,
        default_environment=default_environment,
        strict_isolation_enabled=strict_isolation_enabled,
        allow_future_environments=allow_future_environments,
        live_database_name=live_database_name,
        simulation_database_name=simulation_database_name,
        live_export_path=live_export_path or Path("/tmp/live-export"),
        simulation_export_path=simulation_export_path or Path("/tmp/sim-export"),
        random_seed=random_seed,
        log_level=log_level,
        default_speed=default_speed,
        default_users=default_users,
        default_groups=default_groups,
        project_root=root,
    )
