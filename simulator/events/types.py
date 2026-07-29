"""Event type definitions."""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    MESSAGE_PROCESSED = "MessageProcessed"
    KEYWORD_DETECTED = "KeywordDetected"
    RISK_CALCULATED = "RiskCalculated"
    BEHAVIOR_UPDATED = "BehaviorUpdated"
    ALERT_GENERATED = "AlertGenerated"
    CASE_CREATED = "CaseCreated"
    SIMULATION_STARTED = "SimulationStarted"
    SIMULATION_PAUSED = "SimulationPaused"
    SIMULATION_STOPPED = "SimulationStopped"
    SIMULATION_COMPLETED = "SimulationCompleted"
    DASHBOARD_UPDATED = "DashboardUpdated"
    METRICS_UPDATED = "MetricsUpdated"
