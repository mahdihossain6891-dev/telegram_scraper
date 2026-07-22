"""Dashboard / report / resolve helper tools."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools.base import ToolResult


class DashboardTool:
    name = "dashboard"

    MODULES = (
        {"id": "dashboard", "path": "/", "label": "Dashboard"},
        {"id": "personnel", "path": "/personnel", "label": "Personnel Activity"},
        {"id": "behavioral", "path": "/behavioral", "label": "Behavior Analytics"},
        {"id": "alerts", "path": "/alerts", "label": "Alerts"},
        {"id": "graph", "path": "/graph", "label": "Relationship Graph"},
        {"id": "threat_feed", "path": "/threat-feed", "label": "Threat Feed"},
        {"id": "reports", "path": "/ai", "label": "Reports / Sébastien"},
        {"id": "search", "path": "/search", "label": "Search"},
    )

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        question = (getattr(ctx, "question", "") or "").lower()
        matched = []
        for mod in self.MODULES:
            if mod["id"].replace("_", " ") in question or mod["label"].lower() in question:
                matched.append(mod)
        return ToolResult(
            name=self.name,
            ok=True,
            summary=(
                f"Matched {len(matched)} dashboard module(s)."
                if matched
                else "Dashboard module catalog available."
            ),
            data={
                "modules": list(self.MODULES),
                "matched": matched,
                "hint": (
                    "Open the matched dashboard module for interactive analysis "
                    "instead of duplicating it in chat."
                ),
            },
        )


class ReportTool:
    name = "report"

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        subject = getattr(ctx, "subject", {}) or {}
        uid = subject.get("user_id")
        if uid is None:
            return ToolResult(
                name=self.name,
                ok=False,
                error="Report requires a resolved investigation subject",
                summary="Cannot generate report without a subject.",
            )
        return ToolResult(
            name=self.name,
            ok=True,
            summary=(
                "Report generation is available via the Reports module / "
                f"/api/ai/report for subject {uid}. Structured findings below "
                "should ground any narrative."
            ),
            data={
                "subject_id": str(uid),
                "subject_type": subject.get("subject_type") or "user",
                "recommended_report_type": "user_intelligence",
                "endpoint": "/api/ai/report",
            },
        )


class ResolveEntityTool:
    """Thin wrapper — entity resolution is owned by the orchestrator gate."""

    name = "resolve_entity"

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        er = getattr(ctx, "entity_resolution", {}) or {}
        return ToolResult(
            name=self.name,
            ok=er.get("status") == "resolved",
            summary=str(er.get("message") or er.get("status") or "Entity resolution state"),
            data=dict(er),
        )
