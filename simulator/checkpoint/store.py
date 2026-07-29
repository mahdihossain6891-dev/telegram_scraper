"""Simulation checkpoint model and storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class SimulationCheckpoint:
    """Point-in-time snapshot for future resume support."""

    checkpoint_id: UUID
    session_id: UUID
    created_at: datetime
    current_tick: int
    scheduler_state: dict[str, Any]
    conversation_state: dict[str, Any]
    scenario_state: dict[str, Any]
    metrics: dict[str, Any]
    statistics: dict[str, Any]
    session_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": str(self.checkpoint_id),
            "session_id": str(self.session_id),
            "created_at": self.created_at.isoformat(),
            "current_tick": self.current_tick,
            "scheduler_state": dict(self.scheduler_state),
            "conversation_state": dict(self.conversation_state),
            "scenario_state": dict(self.scenario_state),
            "metrics": dict(self.metrics),
            "statistics": dict(self.statistics),
            "session_metadata": dict(self.session_metadata),
        }


class CheckpointStore:
    """In-memory checkpoint storage (Phase 7 — no persistence backend)."""

    def __init__(self) -> None:
        self._checkpoints: dict[UUID, list[SimulationCheckpoint]] = {}

    def save(self, checkpoint: SimulationCheckpoint) -> SimulationCheckpoint:
        bucket = self._checkpoints.setdefault(checkpoint.session_id, [])
        bucket.append(checkpoint)
        return checkpoint

    def latest(self, session_id: UUID) -> SimulationCheckpoint | None:
        bucket = self._checkpoints.get(session_id, [])
        return bucket[-1] if bucket else None

    def all_for_session(self, session_id: UUID) -> list[SimulationCheckpoint]:
        return list(self._checkpoints.get(session_id, []))

    @staticmethod
    def create(
        *,
        session_id: UUID,
        current_tick: int,
        scheduler_state: dict[str, Any],
        conversation_state: dict[str, Any],
        scenario_state: dict[str, Any],
        metrics: dict[str, Any],
        statistics: dict[str, Any],
        session_metadata: dict[str, Any],
    ) -> SimulationCheckpoint:
        return SimulationCheckpoint(
            checkpoint_id=uuid4(),
            session_id=session_id,
            created_at=datetime.utcnow(),
            current_tick=current_tick,
            scheduler_state=scheduler_state,
            conversation_state=conversation_state,
            scenario_state=scenario_state,
            metrics=metrics,
            statistics=statistics,
            session_metadata=session_metadata,
        )
