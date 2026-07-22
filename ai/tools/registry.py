"""Capability registry — dynamic tool discovery without orchestrator changes."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools.base import ToolRegistry
from ai.tools.capabilities import BUILTIN_CAPABILITIES, ToolCapability


class CapabilityRegistry:
    """Registers tools with capabilities; orchestrator discovers tools dynamically."""

    def __init__(self) -> None:
        self._capabilities: dict[str, ToolCapability] = {}
        self._tools: dict[str, Any] = {}
        for cap in BUILTIN_CAPABILITIES:
            self._capabilities[cap.name] = cap

    def register(self, tool: Any, capability: ToolCapability | None = None) -> None:
        name = str(getattr(tool, "name", ""))
        if not name:
            raise ValueError("Tool must have a name attribute.")
        self._tools[name] = tool
        if capability is not None:
            self._capabilities[name] = capability
        elif name not in self._capabilities:
            self._capabilities[name] = ToolCapability(
                name=name,
                description=getattr(tool, "__doc__", "") or f"Tool {name}",
            )

    def get_tool(self, name: str) -> Any | None:
        return self._tools.get(name)

    def get_capability(self, name: str) -> ToolCapability | None:
        return self._capabilities.get(name)

    def list_capabilities(self) -> list[ToolCapability]:
        return [self._capabilities[n] for n in sorted(self._capabilities) if n in self._tools]

    def tools_for_intent(self, intent_key: str) -> list[str]:
        matched = [
            cap.name
            for cap in self._capabilities.values()
            if intent_key in cap.intents and cap.name in self._tools
        ]
        return sorted(matched)

    def to_tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        for name, tool in self._tools.items():
            registry.register(tool)
        return registry

    @classmethod
    def from_investigation_tools(cls, tools: ToolRegistry) -> "CapabilityRegistry":
        """Wrap an existing ToolRegistry with capability metadata."""
        cap_reg = cls()
        for name in tools.list_tools():
            tool = tools.get(name)
            if tool is not None:
                cap_reg.register(tool)
        return cap_reg
