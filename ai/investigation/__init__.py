"""Investigation Assistant — multi-turn investigation orchestration."""

from __future__ import annotations

from .assistant import AssistantTurnResult, InvestigationAssistant
from .context import (
    ConfidenceAssessment,
    InvestigationContext,
    InvestigationFinding,
    NextAction,
)
from .entity_resolution import (
    EntityMention,
    EntityResolutionResult,
    EntityResolver,
    dedupe_entities,
    extract_entity_mentions,
)
from .intents import InvestigationIntent, classify_intent
from .orchestrator import InvestigationOrchestrator, OrchestratorDeps
from .session_store import SessionStore
from .tools import (
    DEFAULT_TOOL_POLICY,
    ReadOnlyToolRegistry,
    build_rag_filters,
    default_tool_registry,
    extract_subject_hints,
)

__all__ = [
    "AssistantTurnResult",
    "ConfidenceAssessment",
    "DEFAULT_TOOL_POLICY",
    "EntityMention",
    "EntityResolutionResult",
    "EntityResolver",
    "InvestigationAssistant",
    "InvestigationContext",
    "InvestigationFinding",
    "InvestigationIntent",
    "InvestigationOrchestrator",
    "NextAction",
    "OrchestratorDeps",
    "ReadOnlyToolRegistry",
    "SessionStore",
    "build_rag_filters",
    "classify_intent",
    "dedupe_entities",
    "default_tool_registry",
    "extract_entity_mentions",
    "extract_subject_hints",
]
