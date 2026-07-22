"""Default investigation tool registry + legacy helpers."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools.alerts import AlertTool
from ai.investigation.tools.base import ToolRegistry, ToolResult
from ai.investigation.tools.behavior import BehaviorTool
from ai.investigation.tools.dashboard import DashboardTool, ReportTool, ResolveEntityTool
from ai.investigation.tools.filters import (
    build_rag_filters,
    enrich_subject_identity,
    extract_subject_hints,
)
from ai.investigation.tools.personnel import PersonnelTool
from ai.investigation.tools.relationships import RelationshipTool
from ai.investigation.tools.risk import RiskTool
from ai.investigation.tools.search import SearchTool
from ai.investigation.tools.timeline import TimelineTool

# Backwards-compatible alias used by assistant imports.
ReadOnlyToolRegistry = ToolRegistry

DEFAULT_TOOL_POLICY = (
    "Tools are read-only. They retrieve and analyze monitored intelligence only. "
    "They must not send Telegram alerts, change scrape targets, or write intelligence "
    "collections. The model must explain tool findings — never invent missing evidence."
)


def build_investigation_tools(*, retriever: Any | None = None) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (
        ResolveEntityTool(),
        BehaviorTool(),
        RiskTool(),
        AlertTool(),
        PersonnelTool(),
        TimelineTool(),
        RelationshipTool(),
        SearchTool(retriever=retriever),
        DashboardTool(),
        ReportTool(),
    ):
        registry.register(tool)
    return registry


def default_tool_registry(retriever: Any | None = None) -> ToolRegistry:
    """Create the default Sébastien investigation tool registry."""
    return build_investigation_tools(retriever=retriever)


__all__ = [
    "DEFAULT_TOOL_POLICY",
    "ReadOnlyToolRegistry",
    "ToolRegistry",
    "ToolResult",
    "build_investigation_tools",
    "build_rag_filters",
    "default_tool_registry",
    "enrich_subject_identity",
    "extract_subject_hints",
]
