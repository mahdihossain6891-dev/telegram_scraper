"""Tool capability metadata — registered dynamically, zero orchestrator edits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class ToolCapability:
    """Describes one Sébastien tool for discovery and routing."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    intents: tuple[str, ...] = ()
    environment: Literal["live", "simulation", "both"] = "both"
    read_only: bool = True


# Built-in capability declarations — tools self-register via CapabilityRegistry.
BUILTIN_CAPABILITIES: tuple[ToolCapability, ...] = (
    ToolCapability(
        name="resolve_entity",
        description="Resolve username, display name, or Telegram ID to a monitored subject.",
        intents=(),
        input_schema={"query": "string"},
        output_schema={"status": "string", "subject": "object"},
    ),
    ToolCapability(
        name="behavior",
        description="Retrieve behavioral analytics profile for a user.",
        intents=(
            "analyze_behavior",
            "investigate_user",
            "dashboard_summary",
            "find_similar_users",
            "risk_assessment",
            "summarize_case",
        ),
        input_schema={"user_id": "integer"},
        output_schema={"behavior_score": "number", "metrics": "object"},
    ),
    ToolCapability(
        name="risk",
        description="Retrieve risk score and contributing factors.",
        intents=(
            "investigate_user",
            "analyze_behavior",
            "compare_two_users",
            "risk_assessment",
            "summarize_case",
        ),
        input_schema={"user_id": "integer"},
        output_schema={"risk_score": "number", "risk_level": "string"},
    ),
    ToolCapability(
        name="alerts",
        description="Retrieve alerts associated with a user or alert ID.",
        intents=(
            "explain_alert",
            "analyze_behavior",
            "investigate_user",
            "keyword_analysis",
            "risk_assessment",
            "summarize_case",
        ),
        input_schema={"user_id": "integer", "alert_id": "string"},
        output_schema={"alerts": "array"},
    ),
    ToolCapability(
        name="personnel",
        description="Retrieve personnel dossier and activity summary.",
        intents=(
            "investigate_user",
            "generate_report",
            "generate_timeline",
            "find_similar_users",
            "summarize_case",
        ),
        input_schema={"user_id": "integer"},
        output_schema={"display_name": "string", "message_count": "integer"},
    ),
    ToolCapability(
        name="timeline",
        description="Build chronological activity timeline.",
        intents=("generate_timeline", "investigate_user"),
        input_schema={"user_id": "integer"},
        output_schema={"events": "array"},
    ),
    ToolCapability(
        name="relationship",
        description="Analyze shared groups and relationship edges.",
        intents=(
            "relationship_analysis",
            "investigate_user",
            "compare_two_users",
            "find_similar_users",
        ),
        input_schema={"user_id": "integer"},
        output_schema={"edges": "array"},
    ),
    ToolCapability(
        name="search",
        description="Semantic search over monitored messages (RAG).",
        intents=(
            "semantic_search",
            "investigate_user",
            "analyze_behavior",
            "keyword_analysis",
            "search_conversations",
        ),
        input_schema={"question": "string", "filters": "object"},
        output_schema={"evidence": "array", "citations": "array"},
    ),
    ToolCapability(
        name="dashboard",
        description="Orchestrate dashboard module navigation.",
        intents=("open_dashboard_page", "dashboard_summary"),
        input_schema={"query": "string"},
        output_schema={"modules": "array"},
    ),
    ToolCapability(
        name="report",
        description="Orchestrate structured report generation.",
        intents=("generate_report",),
        input_schema={"user_id": "integer", "report_type": "string"},
        output_schema={"report_endpoint": "string"},
    ),
)
