"""Simulator configuration loaded from ``SIMULATION_*`` environment variables.

Settings are isolated from production ``config.Settings`` and ``AI_*`` keys.
The simulator remains dormant until ``SIMULATION_ENABLED`` is set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from simulator.constants import (
    DEFAULT_GROUP_COUNT,
    DEFAULT_LIVE_DATABASE_NAME,
    DEFAULT_LIVE_EXPORT_SUBDIR,
    DEFAULT_SIMULATION_DATABASE_NAME,
    DEFAULT_SIMULATION_EXPORT_SUBDIR,
    DEFAULT_SPEED,
    DEFAULT_USER_COUNT,
    ENV_PREFIX,
)
from simulator.enums import EnvironmentType, SimulationSpeed
from simulator.exceptions import ConfigurationError

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"{ENV_PREFIX}{key}", default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env(key, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = _env(key, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolve_path(raw: str, base: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else base / path


@dataclass(frozen=True, slots=True)
class SimulationSettings:
    """Immutable simulator and environment isolation settings."""

    enabled: bool
    auto_start: bool
    default_environment: EnvironmentType
    strict_isolation_enabled: bool
    allow_future_environments: bool
    live_database_name: str
    simulation_database_name: str
    live_export_path: Path
    simulation_export_path: Path
    random_seed: int | None
    log_level: str
    default_speed: SimulationSpeed
    default_users: int
    default_groups: int
    project_root: Path

    @property
    def database_name(self) -> str:
        """Backwards-compatible alias for simulation database name."""
        return self.simulation_database_name

    @property
    def export_path(self) -> Path:
        """Backwards-compatible alias for simulation export path."""
        return self.simulation_export_path

    def database_name_for(self, environment: EnvironmentType) -> str:
        """Return the isolated Mongo database name for an environment."""
        if environment == EnvironmentType.LIVE:
            return self.live_database_name
        if environment == EnvironmentType.SIMULATION:
            return self.simulation_database_name
        return f"{self.simulation_database_name}_{environment.value}"

    def export_path_for(self, environment: EnvironmentType) -> Path:
        """Return the isolated export directory for an environment."""
        if environment == EnvironmentType.LIVE:
            return self.live_export_path
        if environment == EnvironmentType.SIMULATION:
            return self.simulation_export_path
        return self.simulation_export_path / environment.value

    def to_configuration_dict(self) -> dict[str, object]:
        """Serialize settings for status / API responses (metadata only)."""
        return {
            "enabled": self.enabled,
            "auto_start": self.auto_start,
            "default_environment": self.default_environment.value,
            "strict_isolation_enabled": self.strict_isolation_enabled,
            "allow_future_environments": self.allow_future_environments,
            "live_database_name": self.live_database_name,
            "simulation_database_name": self.simulation_database_name,
            "live_export_path": str(self.live_export_path),
            "simulation_export_path": str(self.simulation_export_path),
            "random_seed": self.random_seed,
            "log_level": self.log_level,
            "default_speed": self.default_speed.value,
            "default_users": self.default_users,
            "default_groups": self.default_groups,
        }


def _parse_environment(raw: str, *, allow_future: bool) -> EnvironmentType:
    try:
        env = EnvironmentType(raw.lower())
    except ValueError as exc:
        raise ConfigurationError(f"Invalid default environment: {raw!r}") from exc
    active = EnvironmentType.active_types()
    if env not in active:
        if allow_future:
            return env
        raise ConfigurationError(
            f"Environment {env.value!r} is reserved for a future phase."
        )
    return env


def _parse_speed(raw: str) -> SimulationSpeed:
    try:
        return SimulationSpeed(raw.lower())
    except ValueError as exc:
        raise ConfigurationError(f"Invalid simulation speed: {raw!r}") from exc


@lru_cache(maxsize=1)
def load_simulation_settings() -> SimulationSettings:
    """Load and validate simulator settings from the environment."""
    root = _PROJECT_ROOT
    allow_future = _env_bool("ALLOW_FUTURE_ENVIRONMENTS", False)
    default_env_raw = _env("DEFAULT_ENVIRONMENT", EnvironmentType.LIVE.value)
    speed_raw = _env("DEFAULT_SPEED", DEFAULT_SPEED)

    seed_raw = _env("RANDOM_SEED", "")
    random_seed: int | None
    if seed_raw:
        try:
            random_seed = int(seed_raw)
        except ValueError as exc:
            raise ConfigurationError(
                f"SIMULATION_RANDOM_SEED must be an integer, got {seed_raw!r}"
            ) from exc
    else:
        random_seed = None

    live_db = _env("LIVE_DATABASE_NAME", DEFAULT_LIVE_DATABASE_NAME)
    sim_db = _env(
        "SIMULATION_DATABASE_NAME",
        _env("DATABASE_NAME", DEFAULT_SIMULATION_DATABASE_NAME),
    )
    if live_db == sim_db:
        raise ConfigurationError(
            "Live and simulation database names must differ for strict isolation."
        )

    live_export = _resolve_path(
        _env("LIVE_EXPORT_PATH", DEFAULT_LIVE_EXPORT_SUBDIR), root
    )
    sim_export = _resolve_path(
        _env("SIMULATION_EXPORT_PATH", _env("EXPORT_PATH", DEFAULT_SIMULATION_EXPORT_SUBDIR)),
        root,
    )

    users = _env_int("DEFAULT_USERS", DEFAULT_USER_COUNT)
    groups = _env_int("DEFAULT_GROUPS", DEFAULT_GROUP_COUNT)
    if users < 0 or groups < 0:
        raise ConfigurationError("User and group counts must be non-negative.")

    return SimulationSettings(
        enabled=_env_bool("ENABLED", False),
        auto_start=_env_bool("AUTO_START", False),
        default_environment=_parse_environment(
            default_env_raw, allow_future=allow_future
        ),
        strict_isolation_enabled=_env_bool("STRICT_ISOLATION_ENABLED", True),
        allow_future_environments=allow_future,
        live_database_name=live_db,
        simulation_database_name=sim_db,
        live_export_path=live_export,
        simulation_export_path=sim_export,
        random_seed=random_seed,
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        default_speed=_parse_speed(speed_raw),
        default_users=users,
        default_groups=groups,
        project_root=root,
    )
