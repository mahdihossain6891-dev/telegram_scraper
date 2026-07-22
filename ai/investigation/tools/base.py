"""Investigation tools — read-only orchestration wrappers.

Each tool has one responsibility. Tools never call the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolResult:
    name: str
    ok: bool
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class InvestigationTool(Protocol):
    name: str

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult: ...


class ToolRegistry:
    """Named registry of investigation tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def register(self, tool: Any) -> None:
        name = getattr(tool, "name", None)
        if not name:
            raise ValueError("Tool must have a name")
        self._tools[str(name)] = tool

    def get(self, name: str) -> Any | None:
        return self._tools.get(name)

    def run(self, name: str, *, ctx: Any, **kwargs: Any) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(name=name, ok=False, error=f"Unknown tool: {name}")
        try:
            return tool.run(ctx=ctx, **kwargs)
        except Exception as exc:  # noqa: BLE001 — fail closed per tool
            return ToolResult(name=name, ok=False, error=str(exc), summary="Tool failed")

    def list_tools(self) -> list[str]:
        return sorted(self._tools)
