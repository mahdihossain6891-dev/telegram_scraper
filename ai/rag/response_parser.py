"""Parse structured fields from RAG LLM completions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai.models.schemas import Citation
from ai.rag.evidence import EvidenceItem

_ANSWER_RE = re.compile(
    r"(?is)^\s*(?:1\.\s*)?answer\s*:?\s*(.+?)(?=\n\s*(?:2\.\s*)?citations?\b|\n\s*(?:3\.\s*)?confidence\b|\Z)"
)
_CITATIONS_RE = re.compile(
    r"(?is)(?:2\.\s*)?citations?\s*:?\s*(.+?)(?=\n\s*(?:3\.\s*)?confidence\b|\Z)"
)
_CONFIDENCE_RE = re.compile(
    r"(?is)(?:3\.\s*)?confidence(?:\s+note)?\s*:?\s*(.+?)\s*$"
)
_CONF_WORD_RE = re.compile(r"\b(high|medium|low)\b", re.I)
_EVIDENCE_REF_RE = re.compile(r"\[E(\d+)\]", re.I)


@dataclass(slots=True)
class ParsedRAGOutput:
    answer: str
    citations: list[Citation]
    confidence: str
    raw_confidence_note: str = ""


def parse_rag_completion(
    content: str,
    evidence: list[EvidenceItem],
) -> ParsedRAGOutput:
    """Extract answer / citations / confidence from model text."""
    text = (content or "").strip()
    if not text:
        return ParsedRAGOutput(
            answer="No answer generated.",
            citations=[],
            confidence="low",
            raw_confidence_note="empty model response",
        )

    answer_match = _ANSWER_RE.search(text)
    citations_match = _CITATIONS_RE.search(text)
    confidence_match = _CONFIDENCE_RE.search(text)

    answer = (answer_match.group(1).strip() if answer_match else text).strip()
    conf_note = confidence_match.group(1).strip() if confidence_match else ""
    confidence = _normalize_confidence(conf_note, evidence, answer)

    citations = _citations_from_text(
        citations_match.group(1) if citations_match else text,
        evidence,
    )
    if not citations:
        citations = _citations_from_evidence_refs(answer + "\n" + text, evidence)
    if not citations and evidence:
        # Fall back to top evidence as supporting context references.
        citations = [
            Citation(
                source_type=item.source_type,
                source_id=item.source_id,
                label=item.citation_label or item.chunk_id,
                snippet=item.text[:240],
            )
            for item in evidence[:3]
        ]

    return ParsedRAGOutput(
        answer=answer,
        citations=citations,
        confidence=confidence,
        raw_confidence_note=conf_note,
    )


def heuristic_confidence(evidence: list[EvidenceItem], answer: str) -> str:
    """Score confidence without relying on model formatting."""
    lowered = (answer or "").lower()
    if not evidence:
        return "low"
    if any(
        phrase in lowered
        for phrase in (
            "cannot answer",
            "insufficient",
            "no evidence",
            "not enough",
            "unable to",
        )
    ):
        return "low"
    top = max(float(item.score) for item in evidence)
    if top >= 0.75 and len(evidence) >= 2:
        return "high"
    if top >= 0.45:
        return "medium"
    return "low"


def _normalize_confidence(
    note: str,
    evidence: list[EvidenceItem],
    answer: str,
) -> str:
    match = _CONF_WORD_RE.search(note or "")
    if match:
        return match.group(1).lower()
    return heuristic_confidence(evidence, answer)


def _citations_from_text(block: str, evidence: list[EvidenceItem]) -> list[Citation]:
    refs = _citations_from_evidence_refs(block, evidence)
    if refs:
        return refs
    # Bullet / line based fallback: keep labels that mention known cites.
    citations: list[Citation] = []
    seen: set[str] = set()
    for item in evidence:
        label = item.citation_label or item.chunk_id
        if label and label in block and label not in seen:
            seen.add(label)
            citations.append(
                Citation(
                    source_type=item.source_type,
                    source_id=item.source_id,
                    label=label,
                    snippet=item.text[:240],
                )
            )
    return citations


def _citations_from_evidence_refs(
    text: str,
    evidence: list[EvidenceItem],
) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[int] = set()
    for match in _EVIDENCE_REF_RE.finditer(text or ""):
        index = int(match.group(1))
        if index in seen or index < 1 or index > len(evidence):
            continue
        seen.add(index)
        item = evidence[index - 1]
        citations.append(
            Citation(
                source_type=item.source_type,
                source_id=item.source_id,
                label=f"E{index}:{item.citation_label or item.chunk_id}",
                snippet=item.text[:240],
            )
        )
    return citations
