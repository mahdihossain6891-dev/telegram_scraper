"""SearchTool — vector evidence retrieval (no LLM)."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools.base import ToolResult
from ai.investigation.tools import filters as filter_helpers


class SearchTool:
    name = "search"

    def __init__(self, retriever: Any | None = None) -> None:
        self.retriever = retriever

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        retriever = self.retriever or getattr(ctx, "retriever", None)
        if retriever is None:
            return ToolResult(
                name=self.name,
                ok=False,
                error="Retriever unavailable",
                summary="Evidence search unavailable.",
            )

        question = kwargs.get("question") or getattr(ctx, "question", "") or ""
        subject = getattr(ctx, "subject", {}) or {}
        extra_filters = getattr(ctx, "filters", None) or {}
        rag_filters = filter_helpers.build_rag_filters(
            subject=subject, extra=extra_filters
        )
        top_k = int(kwargs.get("top_k") or getattr(ctx, "top_k", 8) or 8)

        evidence_items = retriever.retrieve_evidence(
            question,
            top_k=top_k,
            filters=rag_filters or None,
        )

        # Deduplicate by source_id / chunk id.
        seen: set[str] = set()
        evidence: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        for i, item in enumerate(evidence_items, start=1):
            meta = dict(getattr(item, "metadata", None) or {})
            source_id = str(
                meta.get("source_id")
                or getattr(item, "source_id", None)
                or getattr(item, "chunk_id", i)
            )
            key = f"{meta.get('source_type', 'message')}:{source_id}"
            if key in seen:
                continue
            seen.add(key)
            label = str(meta.get("citation_label") or f"E{len(evidence) + 1}")
            text = (getattr(item, "text", None) or "")[:500]
            row = {
                "label": label if label.startswith("[") else f"[{label}]" if label.startswith("E") else f"[E{len(evidence) + 1}]",
                "source_type": meta.get("source_type") or "message",
                "source_id": source_id,
                "timestamp": meta.get("timestamp"),
                "snippet": text,
                "score": float(getattr(item, "score", 0) or meta.get("score") or 0),
                "sender_id": meta.get("sender_id"),
                "chat_id": meta.get("chat_id"),
            }
            # Normalize label to [E#]
            idx = len(evidence) + 1
            row["label"] = f"[E{idx}]"
            evidence.append(row)
            citations.append(
                {
                    "source_type": row["source_type"],
                    "source_id": source_id,
                    "label": row["label"],
                    "snippet": text[:240],
                }
            )

        return ToolResult(
            name=self.name,
            ok=True,
            summary=f"Retrieved {len(evidence)} unique evidence item(s).",
            data={
                "evidence": evidence,
                "citations": citations,
                "filters": rag_filters,
                "raw_count": len(evidence_items),
            },
        )
