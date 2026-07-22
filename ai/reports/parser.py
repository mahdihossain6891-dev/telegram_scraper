"""Parse structured report completions into sections + citations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai.models.schemas import Citation
from ai.rag.evidence import EvidenceItem
from ai.rag.response_parser import heuristic_confidence
from ai.reports.models import ReportSection
from ai.reports.types import ReportTypeSpec

_EVIDENCE_REF_RE = re.compile(r"\[E(\d+)\]", re.I)
_CONFIDENCE_RE = re.compile(
    r"(?is)(?:^|\n)\s*(?:##\s*)?confidence\s*:?\s*(.+?)(?=\n\s*#|\Z)"
)
_CONF_WORD_RE = re.compile(r"\b(high|medium|low)\b", re.I)
_MD_HEADING_RE = re.compile(r"(?m)^(#{1,3}\s*)(.+?)\s*$")
_NUM_HEADING_RE = re.compile(r"(?m)^(?:\d+\.\s+)([A-Za-z].+?)\s*$")


@dataclass(slots=True)
class ParsedReportOutput:
    sections: list[ReportSection]
    citations: list[Citation]
    confidence: str
    body_markdown: str
    raw_confidence_note: str = ""


def parse_report_completion(
    content: str,
    *,
    spec: ReportTypeSpec,
    evidence: list[EvidenceItem],
) -> ParsedReportOutput:
    """Split model output into catalog sections and resolve [E#] citations."""
    text = (content or "").strip()
    if not text:
        return ParsedReportOutput(
            sections=[],
            citations=[],
            confidence="low",
            body_markdown="",
            raw_confidence_note="empty model response",
        )

    sections = _split_into_sections(text, spec)
    sections = _ensure_citation_markers(sections, evidence)
    citations = _citations_from_sections(sections, evidence)
    if not citations and evidence:
        citations = [
            Citation(
                source_type=item.source_type,
                source_id=item.source_id,
                label=f"E{i}:{item.citation_label or item.chunk_id}",
                snippet=item.text[:240],
            )
            for i, item in enumerate(evidence[:5], start=1)
        ]

    conf_match = _CONFIDENCE_RE.search(text)
    conf_note = conf_match.group(1).strip() if conf_match else ""
    conf_word = _CONF_WORD_RE.search(conf_note)
    confidence = (
        conf_word.group(1).lower()
        if conf_word
        else heuristic_confidence(evidence, text)
    )

    body = assemble_markdown(spec.label, sections, citations, confidence)
    return ParsedReportOutput(
        sections=sections,
        citations=citations,
        confidence=confidence,
        body_markdown=body,
        raw_confidence_note=conf_note,
    )


def assemble_markdown(
    title: str,
    sections: list[ReportSection],
    citations: list[Citation],
    confidence: str,
) -> str:
    """Build a portable Markdown body from structured sections."""
    lines: list[str] = [f"# {title}", ""]
    for section in sections:
        lines.append(f"## {section.title}")
        lines.append("")
        lines.append(section.body.strip() or "_(No content)_")
        lines.append("")
    lines.append("## Citations")
    lines.append("")
    if citations:
        for cite in citations:
            label = cite.label or f"{cite.source_type}:{cite.source_id}"
            snippet = (cite.snippet or "").replace("\n", " ").strip()
            lines.append(f"- **{label}** — {snippet}")
    else:
        lines.append("- _(No citations)_")
    lines.append("")
    lines.append(f"**Confidence:** {confidence}")
    lines.append("")
    return "\n".join(lines)


def _split_into_sections(text: str, spec: ReportTypeSpec) -> list[ReportSection]:
    """Map headings in the completion onto the catalog section list."""
    by_key: dict[str, tuple[str, str]] = {}
    for section in spec.sections:
        by_key[_norm(section.title)] = (section.section_id, section.title)
        by_key[_norm(section.section_id)] = (section.section_id, section.title)
        by_key[_norm(section.section_id.replace("_", " "))] = (
            section.section_id,
            section.title,
        )

    buckets = _extract_heading_buckets(text)
    found: dict[str, ReportSection] = {}
    for title, body in buckets:
        key = _norm(title)
        if key in {"citations", "confidence"}:
            continue
        mapped = by_key.get(key)
        if not mapped:
            for catalog_key, value in by_key.items():
                if catalog_key in key or key in catalog_key:
                    mapped = value
                    break
        if not mapped:
            continue
        section_id, canonical_title = mapped
        labels = _unique_labels(body)
        found[section_id] = ReportSection(
            section_id=section_id,
            title=canonical_title,
            body=body.strip(),
            citation_labels=labels,
        )

    ordered: list[ReportSection] = []
    for section in spec.sections:
        if section.section_id in found:
            ordered.append(found[section.section_id])
        else:
            ordered.append(
                ReportSection(
                    section_id=section.section_id,
                    title=section.title,
                    body="Insufficient retrieved evidence to populate this section.",
                    citation_labels=[],
                )
            )
    return ordered


def _extract_heading_buckets(text: str) -> list[tuple[str, str]]:
    heading_iter = list(_MD_HEADING_RE.finditer(text))
    use_numbered = False
    if not heading_iter:
        heading_iter = list(_NUM_HEADING_RE.finditer(text))
        use_numbered = True
    buckets: list[tuple[str, str]] = []
    for i, match in enumerate(heading_iter):
        if use_numbered:
            title = match.group(1).strip()
        else:
            title = re.sub(r"^\d+\.\s*", "", match.group(2).strip()).strip()
        start = match.end()
        end = heading_iter[i + 1].start() if i + 1 < len(heading_iter) else len(text)
        buckets.append((title, text[start:end].strip()))
    return buckets


def _ensure_citation_markers(
    sections: list[ReportSection],
    evidence: list[EvidenceItem],
) -> list[ReportSection]:
    """Soft-enforce [E#] markers on non-gap sections when evidence exists."""
    if not evidence:
        return sections
    updated: list[ReportSection] = []
    for section in sections:
        body = section.body or ""
        labels = list(section.citation_labels)
        is_gap = "insufficient retrieved evidence" in body.lower()
        if (
            not is_gap
            and section.section_id != "evidence_index"
            and body.strip()
            and not labels
            and not _EVIDENCE_REF_RE.search(body)
        ):
            n = min(3, len(evidence))
            markers = ", ".join(f"[E{i}]" for i in range(1, n + 1))
            body = f"{body.rstrip()}\n\nSupporting evidence: {markers}"
            labels = [f"[E{i}]" for i in range(1, n + 1)]
        elif not labels:
            labels = _unique_labels(body)
        updated.append(
            ReportSection(
                section_id=section.section_id,
                title=section.title,
                body=body,
                citation_labels=labels,
            )
        )
    return updated


def _citations_from_sections(
    sections: list[ReportSection],
    evidence: list[EvidenceItem],
) -> list[Citation]:
    combined = "\n".join(s.body for s in sections)
    citations: list[Citation] = []
    seen: set[int] = set()
    for match in _EVIDENCE_REF_RE.finditer(combined):
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


def _unique_labels(body: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for match in _EVIDENCE_REF_RE.finditer(body or ""):
        lab = f"[E{match.group(1)}]"
        if lab not in seen:
            seen.add(lab)
            labels.append(lab)
    return labels


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
