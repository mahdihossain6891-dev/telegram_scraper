"""Investigation Context Builder — merge tool outputs for the LLM only.

The LLM never queries Mongo. It receives a compressed, validated evidence package.
"""

from __future__ import annotations

import json
from typing import Any

from ai.investigation.context import InvestigationContext


class InvestigationContextBuilder:
    """Merge, dedupe, prioritize, and compress investigation context."""

    def __init__(
        self,
        *,
        max_evidence: int = 12,
        max_context_chars: int = 12000,
        max_prompt_chars: int = 16000,
    ) -> None:
        self.max_evidence = max(1, int(max_evidence))
        self.max_context_chars = max(1000, int(max_context_chars))
        self.max_prompt_chars = max(2000, int(max_prompt_chars))

    def build(self, ctx: InvestigationContext) -> dict[str, Any]:
        evidence = self._rank_evidence(list(ctx.evidence or []))
        evidence = self._dedupe_evidence(evidence)[: self.max_evidence]

        package = {
            "intent": {"key": ctx.intent_key, "label": ctx.intent_label},
            "question": ctx.question,
            "target": {
                k: ctx.subject.get(k)
                for k in (
                    "subject_type",
                    "subject_id",
                    "user_id",
                    "chat_id",
                    "display_name",
                    "username",
                    "risk_score",
                    "behavior_score",
                )
                if ctx.subject.get(k) is not None
            },
            "findings": [
                {
                    "key": f.key,
                    "title": f.title,
                    "summary": f.summary,
                    "value": f.value,
                    "citations": list(f.citation_labels),
                }
                for f in ctx.findings
            ],
            "risk": dict(ctx.risk) if ctx.risk else {},
            "behavior": _shallow(ctx.behavior),
            "alerts": list(ctx.alerts[:12]),
            "timeline": self._sort_chrono(list(ctx.timeline[:20])),
            "relationships": list(ctx.relationships[:20]),
            "evidence": evidence,
            "tool_summaries": [
                {
                    "name": t.name,
                    "ok": t.ok,
                    "summary": t.summary,
                    "error": t.error,
                }
                for t in ctx.tool_results
            ],
            "confidence": (
                {
                    "score": ctx.confidence.score,
                    "label": ctx.confidence.label,
                    "reason": ctx.confidence.reason,
                }
                if ctx.confidence
                else None
            ),
            "next_actions": [
                {"id": a.id, "label": a.label, "reason": a.reason, "prompt": a.prompt}
                for a in ctx.next_actions
            ],
            "threat_report": dict(ctx.threat_report) if ctx.threat_report else {},
        }

        raw = json.dumps(package, ensure_ascii=False, default=str)
        compressed = False
        while len(raw) > self.max_context_chars and len(package["evidence"]) > 3:
            package["evidence"] = package["evidence"][:-1]
            compressed = True
            raw = json.dumps(package, ensure_ascii=False, default=str)
        if len(raw) > self.max_context_chars:
            package["timeline"] = package["timeline"][:8]
            package["relationships"] = package["relationships"][:8]
            package["alerts"] = package["alerts"][:6]
            compressed = True
            raw = json.dumps(package, ensure_ascii=False, default=str)

        return {
            "package": package,
            "context_chars": len(raw),
            "prompt_budget_chars": self.max_prompt_chars,
            "compressed": compressed,
            "evidence_count": len(package["evidence"]),
        }

    def apply_to_context(self, ctx: InvestigationContext) -> InvestigationContext:
        built = self.build(ctx)
        ctx.evidence = list(built["package"].get("evidence") or [])
        ctx.metadata["context_builder"] = {
            "context_chars": built["context_chars"],
            "compressed": built["compressed"],
            "evidence_count": built["evidence_count"],
        }
        # Replace grounding-facing evidence with ranked set.
        return ctx

    def _rank_evidence(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def score(item: dict[str, Any]) -> float:
            conf = item.get("confidence")
            base = float(conf) if isinstance(conf, (int, float)) else 0.5
            if item.get("timestamp"):
                base += 0.1
            if item.get("label"):
                base += 0.05
            # Prefer higher retrieval scores when present.
            rs = item.get("score")
            if isinstance(rs, (int, float)):
                base += min(0.3, float(rs))
            return base

        return sorted(items, key=score, reverse=True)

    def _dedupe_evidence(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[Any, Any, Any]] = set()
        out: list[dict[str, Any]] = []
        for item in items:
            key = (
                item.get("source_id") or item.get("chunk_id"),
                item.get("label"),
                (item.get("snippet") or "")[:80],
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @staticmethod
    def _sort_chrono(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def key_fn(row: dict[str, Any]) -> str:
            return str(row.get("timestamp") or row.get("ts") or row.get("time") or "")

        return sorted(items, key=key_fn)


def _shallow(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    out = {}
    for i, (k, v) in enumerate(value.items()):
        if i >= 20:
            break
        if isinstance(v, (dict, list)):
            out[str(k)] = f"<{type(v).__name__}>"
        else:
            out[str(k)] = v
    return out
