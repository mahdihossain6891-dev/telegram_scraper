"""Dataclasses for generated AI reports (not operational intel)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ai.models.schemas import Citation, InsightRecord


@dataclass(slots=True)
class ReportSection:
    """One structured section of a generated report."""

    section_id: str
    title: str
    body: str
    citation_labels: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GeneratedReport:
    """Full AI report artifact (stored in ``ai_reports``)."""

    report_id: str
    report_type: str
    title: str
    subject_type: str
    subject_id: str
    sections: list[ReportSection] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    confidence: str = "low"
    model: str = ""
    body_markdown: str = ""
    refused: bool = False
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_insight_record(self) -> InsightRecord:
        """Compatibility shape for older insight APIs."""
        return InsightRecord(
            insight_id=self.report_id,
            subject_type=self.subject_type,
            subject_id=self.subject_id,
            title=self.title,
            body=self.body_markdown,
            citations=list(self.citations),
            created_at=self.created_at,
            metadata={
                **self.metadata,
                "report_type": self.report_type,
                "refused": self.refused,
                "confidence": self.confidence,
                "model": self.model,
                "sections": [
                    {
                        "section_id": s.section_id,
                        "title": s.title,
                        "body": s.body,
                        "citation_labels": list(s.citation_labels),
                    }
                    for s in self.sections
                ],
            },
        )

    def to_document(self) -> dict[str, Any]:
        """Mongo document for ``ai_reports``."""
        return {
            "_id": self.report_id,
            "report_type": self.report_type,
            "title": self.title,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "sections": [
                {
                    "section_id": s.section_id,
                    "title": s.title,
                    "body": s.body,
                    "citation_labels": list(s.citation_labels),
                }
                for s in self.sections
            ],
            "citations": [
                {
                    "source_type": c.source_type,
                    "source_id": c.source_id,
                    "label": c.label,
                    "snippet": c.snippet,
                }
                for c in self.citations
            ],
            "confidence": self.confidence,
            "model": self.model,
            "body_markdown": self.body_markdown,
            "refused": self.refused,
            "created_at": self.created_at,
            "metadata": dict(self.metadata or {}),
        }


def report_from_document(doc: dict[str, Any]) -> GeneratedReport:
    """Rehydrate a ``GeneratedReport`` from a Mongo document."""
    sections = [
        ReportSection(
            section_id=str(s.get("section_id") or ""),
            title=str(s.get("title") or ""),
            body=str(s.get("body") or ""),
            citation_labels=[str(x) for x in (s.get("citation_labels") or [])],
        )
        for s in (doc.get("sections") or [])
    ]
    citations = [
        Citation(
            source_type=str(c.get("source_type") or ""),
            source_id=str(c.get("source_id") or ""),
            label=str(c.get("label") or ""),
            snippet=str(c.get("snippet") or ""),
        )
        for c in (doc.get("citations") or [])
    ]
    return GeneratedReport(
        report_id=str(doc.get("_id") or doc.get("report_id") or ""),
        report_type=str(doc.get("report_type") or ""),
        title=str(doc.get("title") or ""),
        subject_type=str(doc.get("subject_type") or ""),
        subject_id=str(doc.get("subject_id") or ""),
        sections=sections,
        citations=citations,
        confidence=str(doc.get("confidence") or "low"),
        model=str(doc.get("model") or ""),
        body_markdown=str(doc.get("body_markdown") or ""),
        refused=bool(doc.get("refused", False)),
        created_at=doc.get("created_at"),
        metadata=dict(doc.get("metadata") or {}),
    )
