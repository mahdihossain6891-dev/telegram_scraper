"""Memory manager — session, investigation, pinned evidence; LIVE/SIMULATION isolated."""

from __future__ import annotations

from typing import Any

from ai.core.types import PlatformEnvironment
from ai.memory.types import MemoryEntry


class MemoryManager:
    """Manages AI memory layers with strict environment isolation."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, MemoryEntry]] = {
            PlatformEnvironment.LIVE.value: {},
            PlatformEnvironment.SIMULATION.value: {},
        }

    def _bucket(self, environment: PlatformEnvironment) -> dict[str, MemoryEntry]:
        return self._store[environment.value]

    def put(
        self,
        *,
        kind: str,
        key: str,
        value: Any,
        environment: PlatformEnvironment,
    ) -> None:
        bucket = self._bucket(environment)
        bucket[f"{kind}:{key}"] = MemoryEntry(
            kind=kind,  # type: ignore[arg-type]
            key=key,
            value=value,
            environment=environment.value,
        )

    def get(
        self,
        *,
        kind: str,
        key: str,
        environment: PlatformEnvironment,
    ) -> Any | None:
        entry = self._bucket(environment).get(f"{kind}:{key}")
        return entry.value if entry else None

    def pin_evidence(
        self,
        session_id: str,
        evidence: dict[str, Any],
        *,
        environment: PlatformEnvironment,
    ) -> None:
        pinned = list(self.get(kind="pinned_evidence", key=session_id, environment=environment) or [])
        pinned.append(evidence)
        self.put(
            kind="pinned_evidence",
            key=session_id,
            value=pinned[-50:],
            environment=environment,
        )

    def load_session_context(
        self,
        session_doc: dict[str, Any],
        *,
        environment: PlatformEnvironment,
    ) -> dict[str, Any]:
        """Merge session store doc with investigation memory — same environment only."""
        return {
            "session_id": str(session_doc.get("_id") or ""),
            "subject": dict(session_doc.get("subject") or {}),
            "messages": list(session_doc.get("messages") or []),
            "environment": environment.value,
            "pinned": list(
                self.get(
                    kind="pinned_evidence",
                    key=str(session_doc.get("_id") or ""),
                    environment=environment,
                )
                or []
            ),
        }

    def assert_environment_match(
        self,
        requested: PlatformEnvironment,
        data_environment: str | None,
    ) -> None:
        """Raise if memory/data environment would cross LIVE/SIMULATION boundary."""
        if data_environment is None:
            return
        normalized = str(data_environment).lower()
        if normalized in {"simulation", "sim"}:
            normalized = PlatformEnvironment.SIMULATION.value
        elif normalized not in {PlatformEnvironment.LIVE.value, PlatformEnvironment.SIMULATION.value}:
            normalized = PlatformEnvironment.LIVE.value
        if normalized != requested.value:
            raise EnvironmentIsolationError(
                f"Cannot mix {requested.value} session with {normalized} data."
            )


class EnvironmentIsolationError(RuntimeError):
    """Raised when LIVE and SIMULATION memory would be mixed."""
