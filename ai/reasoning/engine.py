"""Reasoning Engine — prepares structured analysis for the LLM."""

from __future__ import annotations

from typing import Any


class ReasoningEngine:
    """Deterministic reasoning over investigation context — never queries databases."""

    def prepare(self, ctx: Any, *, evidence: list[Any] | None = None) -> dict[str, Any]:
        """Build reasoning package for LLM grounding."""
        package = {
            "summary_points": self._summary_points(ctx),
            "timeline_analysis": self._timeline_analysis(ctx),
            "relationship_analysis": self._relationship_analysis(ctx),
            "behavior_analysis": self._behavior_analysis(ctx),
            "risk_explanation": self._risk_explanation(ctx),
            "gaps": self._detect_gaps(ctx, evidence or []),
            "contradictions": self._detect_contradictions(ctx),
            "patterns": self._detect_patterns(ctx),
        }
        return package

    def _summary_points(self, ctx: Any) -> list[str]:
        points = []
        for finding in ctx.findings or []:
            points.append(f"{finding.title}: {finding.summary}")
        return points[:12]

    def _timeline_analysis(self, ctx: Any) -> dict[str, Any]:
        events = ctx.timeline or []
        if not events:
            return {"available": False}
        return {
            "available": True,
            "event_count": len(events),
            "first": events[0] if events else None,
            "last": events[-1] if events else None,
        }

    def _relationship_analysis(self, ctx: Any) -> dict[str, Any]:
        edges = ctx.relationships or []
        return {
            "edge_count": len(edges),
            "sample": edges[:5],
        }

    def _behavior_analysis(self, ctx: Any) -> dict[str, Any]:
        behavior = ctx.behavior or {}
        if not behavior:
            return {"available": False}
        return {
            "available": True,
            "behavior_score": behavior.get("behavior_score"),
            "behavior_status": behavior.get("behavior_status"),
            "trend": behavior.get("trend"),
            "metrics": behavior.get("metrics") or {},
        }

    def _risk_explanation(self, ctx: Any) -> dict[str, Any]:
        risk = ctx.risk or {}
        if not risk:
            return {"available": False}
        factors = list(risk.get("factors") or [])[:8]
        return {
            "available": True,
            "risk_score": risk.get("risk_score"),
            "risk_level": risk.get("risk_level"),
            "factors": factors,
            "explanation": (
                f"Risk level {risk.get('risk_level')} "
                f"(score {risk.get('risk_score')}) "
                f"with {len(factors)} contributing factor(s)."
                if risk.get("risk_score") is not None
                else "Risk data unavailable."
            ),
        }

    def _detect_gaps(self, ctx: Any, evidence: list[Any]) -> list[str]:
        gaps = []
        if ctx.has_target() and not evidence:
            gaps.append("No retrieved message evidence for target.")
        if ctx.has_target() and not ctx.timeline:
            gaps.append("Timeline data unavailable.")
        if ctx.has_target() and not ctx.relationships:
            gaps.append("Relationship graph data limited.")
        if not ctx.risk and "risk" in (ctx.tools_requested or []):
            gaps.append("Risk assessment tool returned no data.")
        return gaps

    def _detect_contradictions(self, ctx: Any) -> list[str]:
        contradictions = []
        risk = ctx.risk or {}
        behavior = ctx.behavior or {}
        rs = risk.get("risk_score")
        bs = behavior.get("behavior_score")
        if rs is not None and bs is not None:
            if rs >= 70 and bs < 30:
                contradictions.append(
                    "High risk score with low behavior score — review contributing factors."
                )
            if rs < 30 and bs >= 70:
                contradictions.append(
                    "Low risk score with elevated behavior score — possible emerging pattern."
                )
        return contradictions

    def _detect_patterns(self, ctx: Any) -> list[str]:
        patterns = []
        metrics = (ctx.behavior or {}).get("metrics") or {}
        if metrics.get("night_activity_ratio", 0) > 0.5:
            patterns.append("Elevated night-time activity ratio.")
        if metrics.get("forward_rate", 0) > 0.3:
            patterns.append("High message forwarding rate.")
        if len(ctx.alerts or []) >= 3:
            patterns.append("Multiple active alerts on subject.")
        return patterns
