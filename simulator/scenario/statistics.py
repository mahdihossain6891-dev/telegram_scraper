"""Scenario execution statistics and history."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from simulator.scenario.labels import ScenarioCategory


@dataclass(slots=True)
class ScenarioRunRecord:
    """One completed or in-progress scenario run."""

    scenario_id: str
    scenario_name: str
    category: str
    started_at: datetime
    completed_at: datetime | None = None
    participant_ids: list[str] = field(default_factory=list)
    message_count: int = 0
    reply_count: int = 0
    average_replies: float = 0.0
    duration_seconds: float = 0.0
    completed: bool = False
    success: bool = False
    synthetic_evaluation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "category": self.category,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "participant_ids": list(self.participant_ids),
            "message_count": self.message_count,
            "reply_count": self.reply_count,
            "average_replies": self.average_replies,
            "duration_seconds": self.duration_seconds,
            "completed": self.completed,
            "success": self.success,
            "synthetic_evaluation": self.synthetic_evaluation,
        }


@dataclass
class ScenarioStatistics:
    """Aggregated scenario metrics."""

    scenario_usage: dict[str, int] = field(default_factory=dict)
    average_duration_seconds: float = 0.0
    most_active_scenario: str | None = None
    average_participants: float = 0.0
    average_messages: float = 0.0
    scenario_distribution: dict[str, float] = field(default_factory=dict)
    synthetic_evaluation_distribution: dict[str, int] = field(default_factory=dict)
    total_runs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_usage": dict(self.scenario_usage),
            "average_duration_seconds": self.average_duration_seconds,
            "most_active_scenario": self.most_active_scenario,
            "average_participants": self.average_participants,
            "average_messages": self.average_messages,
            "scenario_distribution": dict(self.scenario_distribution),
            "synthetic_evaluation_distribution": dict(self.synthetic_evaluation_distribution),
            "total_runs": self.total_runs,
        }


class ScenarioHistory:
    """Tracks scenario runs over time."""

    def __init__(self) -> None:
        self._runs: list[ScenarioRunRecord] = []

    @property
    def runs(self) -> list[ScenarioRunRecord]:
        return list(self._runs)

    def start_run(
        self,
        *,
        scenario_id: str,
        scenario_name: str,
        category: str,
        participant_ids: list[str],
        started_at: datetime,
        synthetic_evaluation: bool,
    ) -> ScenarioRunRecord:
        record = ScenarioRunRecord(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            category=category,
            started_at=started_at,
            participant_ids=participant_ids,
            synthetic_evaluation=synthetic_evaluation,
        )
        self._runs.append(record)
        return record

    def complete_run(
        self,
        record: ScenarioRunRecord,
        *,
        message_count: int,
        reply_count: int,
        completed_at: datetime,
        success: bool = True,
    ) -> None:
        record.message_count = message_count
        record.reply_count = reply_count
        record.completed_at = completed_at
        record.duration_seconds = (completed_at - record.started_at).total_seconds()
        record.average_replies = reply_count / message_count if message_count else 0.0
        record.completed = True
        record.success = success

    def statistics(self) -> ScenarioStatistics:
        if not self._runs:
            return ScenarioStatistics()

        usage = Counter(run.scenario_id for run in self._runs)
        synthetic = Counter(
            run.scenario_id
            for run in self._runs
            if run.synthetic_evaluation or run.category == ScenarioCategory.SYNTHETIC_THREAT_EVALUATION.value
        )
        total = len(self._runs)
        durations = [run.duration_seconds for run in self._runs if run.completed]
        participants = [len(run.participant_ids) for run in self._runs]
        messages = [run.message_count for run in self._runs]

        distribution = {sid: count / total for sid, count in usage.items()}
        return ScenarioStatistics(
            scenario_usage=dict(usage),
            average_duration_seconds=round(sum(durations) / len(durations), 2) if durations else 0.0,
            most_active_scenario=usage.most_common(1)[0][0] if usage else None,
            average_participants=round(sum(participants) / total, 2),
            average_messages=round(sum(messages) / total, 2),
            scenario_distribution=distribution,
            synthetic_evaluation_distribution=dict(synthetic),
            total_runs=total,
        )
