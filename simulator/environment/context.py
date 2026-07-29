"""Environment metadata helpers."""

from __future__ import annotations

from typing import Any

from simulator.constants import META_ENVIRONMENT_KEY, META_ISOLATION_KEY, META_VERSION_KEY, PACKAGE_VERSION
from simulator.enums import EnvironmentType, MessageSourceKind
from simulator.models.message_event import EnvironmentInformation

_ENV_DESCRIPTIONS: dict[EnvironmentType, str] = {
    EnvironmentType.LIVE: (
        "Production Telegram monitoring — Telethon active, live database and indexes."
    ),
    EnvironmentType.SIMULATION: (
        "Synthetic traffic — Telethon inactive, isolated simulation storage and indexes."
    ),
    EnvironmentType.PLAYBACK: "Replay captured datasets (future phase).",
    EnvironmentType.OFFLINE_IMPORT: "Batch import of offline captures (future phase).",
}

_SOURCE_BY_ENVIRONMENT: dict[EnvironmentType, MessageSourceKind] = {
    EnvironmentType.LIVE: MessageSourceKind.TELETHON,
    EnvironmentType.SIMULATION: MessageSourceKind.SIMULATION,
    EnvironmentType.PLAYBACK: MessageSourceKind.PLAYBACK,
    EnvironmentType.OFFLINE_IMPORT: MessageSourceKind.OFFLINE_IMPORT,
}


def environment_description(environment: EnvironmentType) -> str:
    return _ENV_DESCRIPTIONS.get(environment, "")


def message_source_kind_for(environment: EnvironmentType) -> MessageSourceKind:
    return _SOURCE_BY_ENVIRONMENT[environment]


def build_environment_information(
    *,
    environment: EnvironmentType,
    active: bool,
    selectable: bool,
    metadata: dict[str, Any] | None = None,
) -> EnvironmentInformation:
    return EnvironmentInformation(
        environment=environment,
        active=active,
        selectable=selectable,
        description=environment_description(environment),
        metadata=metadata or {},
    )


def base_environment_metadata(
    *,
    environment: EnvironmentType,
    strict_isolation: bool,
    live_database_name: str,
    simulation_database_name: str,
    message_source_kind: MessageSourceKind,
) -> dict[str, Any]:
    return {
        META_VERSION_KEY: PACKAGE_VERSION,
        META_ENVIRONMENT_KEY: environment.value,
        META_ISOLATION_KEY: strict_isolation,
        "live_database_name": live_database_name,
        "simulation_database_name": simulation_database_name,
        "message_source_kind": message_source_kind.value,
    }
