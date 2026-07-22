"""JSON serializers for AI API responses (no DB handles / mongo docs)."""

from __future__ import annotations

from typing import Any

from ai.investigation.assistant import AssistantTurnResult
from ai.models.schemas import Citation, QueryResponse, RetrievalHit
from ai.reports.models import GeneratedReport


_SAFE_META_KEYS = frozenset(
    {
        "source_type",
        "source_id",
        "citation_label",
        "chat_id",
        "message_id",
        "sender_id",
        "message_row_id",
        "risk_score",
        "risk_level",
        "timestamp",
        "sender_display_name",
        "sender_username",
        "sender_first_name",
        "sender_last_name",
        "sender_risk_score",
        "sender_risk_level",
        "sender_behavior_score",
        "sender_user",
    }
)


def citation_dict(citation: Citation) -> dict[str, Any]:
    return {
        "source_type": citation.source_type,
        "source_id": citation.source_id,
        "label": citation.label,
        "snippet": (citation.snippet or "")[:500],
    }


def retrieval_hit_dict(hit: RetrievalHit) -> dict[str, Any]:
    meta = {
        k: v
        for k, v in dict(hit.metadata or {}).items()
        if k in _SAFE_META_KEYS and v is not None
    }
    return {
        "chunk_id": hit.chunk_id,
        "score": float(hit.score),
        "text": (hit.text or "")[:500],
        "metadata": meta,
    }


def retrieved_item_dict(item: Any, *, index: int = 0) -> dict[str, Any]:
    """Serialize investigation evidence or RAG hits for the UI."""
    if isinstance(item, RetrievalHit):
        return retrieval_hit_dict(item)

    if isinstance(item, dict):
        text = str(item.get("text") or item.get("snippet") or "")[:500]
        chunk_id = str(
            item.get("chunk_id")
            or item.get("source_id")
            or item.get("label")
            or item.get("id")
            or ""
        ).strip()
        if not chunk_id:
            chunk_id = f"ev-{index}"
        meta = {
            k: v
            for k, v in item.items()
            if k in _SAFE_META_KEYS and v is not None
        }
        for key in ("source_type", "source_id", "timestamp", "chat_id", "sender_id"):
            if item.get(key) is not None and key not in meta:
                meta[key] = item[key]
        score_raw = item.get("score")
        try:
            score = float(score_raw) if score_raw is not None else 0.0
        except (TypeError, ValueError):
            score = 0.0
        return {
            "chunk_id": chunk_id,
            "score": score,
            "text": text,
            "metadata": meta,
        }

    return {
        "chunk_id": f"raw-{index}",
        "score": 0.0,
        "text": str(item)[:500],
        "metadata": {},
    }


def query_response_dict(result: QueryResponse) -> dict[str, Any]:
    """Serialize RAG output without evidence mongo records."""
    return {
        "answer": result.answer,
        "citations": [citation_dict(c) for c in result.citations],
        "confidence": result.confidence,
        "model": result.model,
        "retrieved": [retrieval_hit_dict(h) for h in result.retrieved],
        "metadata": dict(result.metadata or {}),
    }


def assistant_turn_dict(result: AssistantTurnResult) -> dict[str, Any]:
    return {
        "session_id": result.session_id,
        "intent": result.intent,
        "intent_label": result.intent_label,
        "answer": result.answer,
        "citations": [citation_dict(c) for c in result.citations],
        "confidence": result.confidence,
        "model": result.model,
        "refused": result.refused,
        "retrieved": [retrieved_item_dict(h, index=i) for i, h in enumerate(result.retrieved)],
        "metadata": {
            k: v
            for k, v in dict(result.metadata or {}).items()
            if k not in {"mongo", "db"}
        },
    }


def report_dict(report: GeneratedReport) -> dict[str, Any]:
    return {
        "report_id": report.report_id,
        "report_type": report.report_type,
        "title": report.title,
        "subject_type": report.subject_type,
        "subject_id": report.subject_id,
        "sections": [
            {
                "section_id": s.section_id,
                "title": s.title,
                "body": s.body,
                "citation_labels": list(s.citation_labels),
            }
            for s in report.sections
        ],
        "citations": [citation_dict(c) for c in report.citations],
        "confidence": report.confidence,
        "model": report.model,
        "body_markdown": report.body_markdown,
        "refused": report.refused,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "metadata": dict(report.metadata or {}),
    }
