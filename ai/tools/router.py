"""Tool Router — intent to tool selection (never LLM-decided data access)."""

from __future__ import annotations

from ai.investigation.intents import InvestigationIntent, tools_for_intent
from ai.tools.registry import CapabilityRegistry


class ToolRouter:
    """Selects which tools execute for a given intent."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def route(self, intent: InvestigationIntent) -> list[str]:
        """Return ordered tool names for an intent.

        Uses intent.tools as primary plan; enriches from capability registry
        when capabilities declare additional intent mappings.
        """
        planned = list(tools_for_intent(intent))
        discovered = self._registry.tools_for_intent(intent.key)
        merged: list[str] = []
        seen: set[str] = set()
        for name in (*planned, *discovered):
            if name not in seen and self._registry.get_tool(name) is not None:
                merged.append(name)
                seen.add(name)
        return merged

    def validate_tools(self, names: list[str]) -> list[str]:
        """Filter to registered tools only."""
        return [n for n in names if self._registry.get_tool(n) is not None]
