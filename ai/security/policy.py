"""AI security — read-only policy and environment guards."""

from __future__ import annotations

from typing import Any

from ai.core.types import PlatformEnvironment


FORBIDDEN_WRITE_OPERATIONS = frozenset(
    {
        "insert",
        "update",
        "delete",
        "drop",
        "modify",
        "write",
        "patch",
        "upsert",
        "remove",
        "alter_risk",
        "alter_alert",
        "create_case",
        "send_alert",
    }
)


class ReadOnlyViolation(RuntimeError):
    """Raised when AI attempts a forbidden write operation."""


class ReadOnlyPolicy:
    """Sébastien is READ ONLY — never modify intelligence data."""

    @staticmethod
    def validate_tool_name(name: str) -> None:
        lowered = name.lower()
        for forbidden in FORBIDDEN_WRITE_OPERATIONS:
            if forbidden in lowered:
                raise ReadOnlyViolation(
                    f"Tool '{name}' implies write access — forbidden for AI."
                )

    @staticmethod
    def validate_request(payload: dict[str, Any]) -> None:
        for key in payload:
            if key.lower() in FORBIDDEN_WRITE_OPERATIONS:
                raise ReadOnlyViolation(f"Request field '{key}' implies write access.")

    @staticmethod
    def audit_log(action: str, *, session_id: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "action": action,
            "session_id": session_id,
            "read_only": True,
            "details": dict(details or {}),
        }


class EnvironmentGuard:
    """Enforces LIVE vs SIMULATION data isolation for AI retrieval."""

    @staticmethod
    def resolve(filters: dict[str, Any] | None) -> PlatformEnvironment:
        return PlatformEnvironment.from_filters(filters)

    @staticmethod
    def merge_filters(
        base: dict[str, Any] | None,
        environment: PlatformEnvironment,
    ) -> dict[str, Any]:
        merged = dict(base or {})
        merged["environment"] = environment.value
        return merged

    @staticmethod
    def validate_evidence_environment(
        evidence_environment: str | None,
        session_environment: PlatformEnvironment,
    ) -> None:
        if evidence_environment is None:
            return
        normalized = str(evidence_environment).lower()
        if normalized in {"sim", "simulation"}:
            normalized = PlatformEnvironment.SIMULATION.value
        if normalized != session_environment.value:
            raise EnvironmentIsolationError(
                f"Evidence environment '{evidence_environment}' does not match "
                f"session environment '{session_environment.value}'."
            )


from ai.memory.manager import EnvironmentIsolationError  # noqa: E402 — re-export
