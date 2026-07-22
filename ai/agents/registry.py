"""Future AI agent architecture — stubs only (Phase 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AgentRole = Literal[
    "investigator",
    "threat_analyst",
    "relationship_analyst",
    "behavior_analyst",
    "report_writer",
    "osint_assistant",
    "translator",
    "mitre_mapper",
]


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Describes a future specialized agent — not executed in Phase 8."""

    role: AgentRole
    name: str
    description: str
    tools: tuple[str, ...] = ()
    enabled: bool = False


class AgentRegistry:
    """Registry for future multi-agent Sébastien capabilities."""

    def __init__(self) -> None:
        self._agents: dict[AgentRole, AgentDefinition] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = (
            AgentDefinition(
                role="investigator",
                name="Investigator",
                description="Primary investigation workflow agent.",
                tools=("personnel", "search", "risk", "behavior", "timeline"),
            ),
            AgentDefinition(
                role="threat_analyst",
                name="Threat Analyst",
                description="Focus on risk, alerts, and threat indicators.",
                tools=("risk", "alerts", "search"),
            ),
            AgentDefinition(
                role="relationship_analyst",
                name="Relationship Analyst",
                description="Graph and co-occurrence analysis.",
                tools=("relationship", "personnel"),
            ),
            AgentDefinition(
                role="behavior_analyst",
                name="Behavior Analyst",
                description="Behavioral pattern analysis.",
                tools=("behavior", "timeline", "alerts"),
            ),
            AgentDefinition(
                role="report_writer",
                name="Report Writer",
                description="Structured report generation.",
                tools=("report", "personnel", "risk", "behavior"),
            ),
            AgentDefinition(
                role="osint_assistant",
                name="OSINT Assistant",
                description="Future external OSINT enrichment.",
                tools=(),
                enabled=False,
            ),
            AgentDefinition(
                role="translator",
                name="Translator",
                description="Future multilingual message translation.",
                tools=(),
                enabled=False,
            ),
            AgentDefinition(
                role="mitre_mapper",
                name="MITRE Mapper",
                description="Future ATT&CK technique mapping.",
                tools=(),
                enabled=False,
            ),
        )
        for agent in defaults:
            self._agents[agent.role] = agent

    def register(self, agent: AgentDefinition) -> None:
        self._agents[agent.role] = agent

    def get(self, role: AgentRole) -> AgentDefinition | None:
        return self._agents.get(role)

    def list_agents(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def list_enabled(self) -> list[AgentDefinition]:
        return [a for a in self._agents.values() if a.enabled]
