"""Evidence Engine — collect, score, rank, dedupe, cite."""

from __future__ import annotations

from typing import Any

from ai.evidence.models import Evidence


class EvidenceEngine:
    """Transforms raw retrieval into ranked, deduplicated evidence packages."""

    def __init__(self, *, min_confidence: float = 0.0, max_items: int = 24) -> None:
        self._min_confidence = min_confidence
        self._max_items = max_items

    def collect(self, ctx: Any, *, environment: str = "live") -> list[Evidence]:
        """Collect evidence from investigation context and tool outputs."""
        items: list[Evidence] = []

        for raw in ctx.evidence or []:
            items.append(Evidence.from_retrieved(raw, environment=environment))

        # Structured findings with citation labels become evidence.
        for finding in ctx.findings or []:
            labels = getattr(finding, "citation_labels", None) or []
            if labels:
                for label in labels[:6]:
                    items.append(
                        Evidence(
                            id=f"finding:{finding.key}:{label}",
                            source="finding",
                            environment=environment,
                            citation=str(label),
                            confidence=0.6,
                            text=f"{finding.title}: {finding.summary}",
                            metadata={"finding_key": finding.key},
                        )
                    )

        # Risk / behavior as structured evidence when present.
        if ctx.risk:
            items.append(
                Evidence(
                    id="structured:risk",
                    source="risk_engine",
                    environment=environment,
                    risk=dict(ctx.risk),
                    confidence=0.85,
                    citation="[RISK]",
                    text=str(ctx.risk.get("risk_level") or ""),
                    metadata={"risk_score": ctx.risk.get("risk_score")},
                )
            )
        if ctx.behavior:
            items.append(
                Evidence(
                    id="structured:behavior",
                    source="behavior_engine",
                    environment=environment,
                    behavior=dict(ctx.behavior),
                    confidence=0.8,
                    citation="[BEHAVIOR]",
                    text=str(ctx.behavior.get("behavior_status") or ""),
                )
            )

        for alert in (ctx.alerts or [])[:8]:
            items.append(
                Evidence(
                    id=f"alert:{alert.get('type', 'unknown')}",
                    source="alert",
                    environment=environment,
                    confidence=0.75,
                    citation="[ALERT]",
                    text=str(alert.get("message") or alert.get("type") or ""),
                    metadata=dict(alert),
                )
            )

        return self.process(items)

    def process(self, items: list[Evidence]) -> list[Evidence]:
        """Score, dedupe, rank, and assign confidence."""
        deduped = self._deduplicate(items)
        scored = [self._score(item) for item in deduped]
        filtered = [e for e in scored if e.confidence >= self._min_confidence]
        ranked = sorted(filtered, key=lambda e: e.confidence, reverse=True)
        return ranked[: self._max_items]

    def build_citations(self, items: list[Evidence]) -> list[dict[str, Any]]:
        citations = []
        for item in items:
            if not item.citation and not item.text:
                continue
            citations.append(
                {
                    "label": item.citation or f"[{item.source}]",
                    "source_type": item.source,
                    "source_id": item.message_id or item.id,
                    "snippet": item.text[:240],
                    "confidence": item.confidence,
                }
            )
        return citations

    def _deduplicate(self, items: list[Evidence]) -> list[Evidence]:
        seen: set[str] = set()
        out: list[Evidence] = []
        for item in items:
            key = item.citation or item.id or item.text[:80]
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    def _score(self, item: Evidence) -> Evidence:
        score = item.confidence
        if item.risk:
            score = max(score, 0.7)
        if item.timestamp:
            score += 0.05
        if item.text and len(item.text) > 40:
            score += 0.05
        item.confidence = round(min(1.0, score), 3)
        return item
