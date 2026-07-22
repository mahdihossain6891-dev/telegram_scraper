"""Report type catalogs and section outlines for Phase 9."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReportType(str, Enum):
    """Supported AI report kinds."""

    USER_INTELLIGENCE = "user_intelligence"
    INVESTIGATION = "investigation"
    CASE_SUMMARY = "case_summary"
    BEHAVIORAL_ANALYSIS = "behavioral_analysis"


@dataclass(frozen=True, slots=True)
class SectionSpec:
    """Expected section in a structured report."""

    section_id: str
    title: str
    guidance: str


@dataclass(frozen=True, slots=True)
class ReportTypeSpec:
    """Catalog entry for one report type."""

    report_type: ReportType
    label: str
    title_template: str
    retrieval_question: str
    sections: tuple[SectionSpec, ...]


_REPORT_SPECS: dict[ReportType, ReportTypeSpec] = {
    ReportType.USER_INTELLIGENCE: ReportTypeSpec(
        report_type=ReportType.USER_INTELLIGENCE,
        label="User Intelligence Report",
        title_template="User Intelligence Report — {subject}",
        retrieval_question=(
            "User intelligence profile: identity signals, flagged messages, "
            "risk indicators, entities, and activity patterns for this subject."
        ),
        sections=(
            SectionSpec(
                "executive_summary",
                "Executive summary",
                "2–4 sentences grounded in evidence",
            ),
            SectionSpec(
                "identity_profile",
                "Identity & profile",
                "Identifiers and aliases only if evidenced",
            ),
            SectionSpec(
                "activity_overview",
                "Activity overview",
                "Observed messaging / chat activity",
            ),
            SectionSpec(
                "risk_indicators",
                "Risk indicators",
                "Why risk appears elevated, with cites",
            ),
            SectionSpec(
                "entities_of_interest",
                "Entities of interest",
                "Phones, wallets, URLs, orgs, etc.",
            ),
            SectionSpec(
                "evidence_index",
                "Evidence index",
                "List [E#] labels used with short labels",
            ),
        ),
    ),
    ReportType.INVESTIGATION: ReportTypeSpec(
        report_type=ReportType.INVESTIGATION,
        label="Investigation Report",
        title_template="Investigation Report — {subject}",
        retrieval_question=(
            "Investigation overview: key findings, subject relationships, "
            "timeline highlights, and evidence gaps for this investigation."
        ),
        sections=(
            SectionSpec(
                "executive_summary",
                "Executive summary",
                "Concise investigation status",
            ),
            SectionSpec("scope_subjects", "Scope & subjects", "Who/what is in scope"),
            SectionSpec(
                "key_findings",
                "Key findings",
                "Evidence-backed findings only",
            ),
            SectionSpec(
                "relationships",
                "Relationships",
                "Links between users/chats if evidenced",
            ),
            SectionSpec(
                "timeline_highlights",
                "Timeline highlights",
                "Ordered notable events",
            ),
            SectionSpec(
                "gaps_next_steps",
                "Gaps & next steps",
                "Missing data and suggested checks",
            ),
            SectionSpec("evidence_index", "Evidence index", "List [E#] labels used"),
        ),
    ),
    ReportType.CASE_SUMMARY: ReportTypeSpec(
        report_type=ReportType.CASE_SUMMARY,
        label="Case Summary",
        title_template="Case Summary — {subject}",
        retrieval_question=(
            "Case summary: case overview, subjects, chronology, findings, "
            "qualitative risk, and recommended follow-ups."
        ),
        sections=(
            SectionSpec("case_overview", "Case overview", "What the case covers"),
            SectionSpec("subjects", "Subjects", "Primary subjects with identifiers"),
            SectionSpec(
                "chronology",
                "Chronology",
                "Ordered events with timestamps when known",
            ),
            SectionSpec("findings", "Findings", "Evidence-backed conclusions"),
            SectionSpec(
                "risk_assessment",
                "Risk assessment",
                "Qualitative only — no invented scores",
            ),
            SectionSpec(
                "recommended_followups",
                "Recommended follow-ups",
                "Actionable next checks",
            ),
            SectionSpec("evidence_index", "Evidence index", "List [E#] labels used"),
        ),
    ),
    ReportType.BEHAVIORAL_ANALYSIS: ReportTypeSpec(
        report_type=ReportType.BEHAVIORAL_ANALYSIS,
        label="Behavioral Analysis Report",
        title_template="Behavioral Analysis Report — {subject}",
        retrieval_question=(
            "Behavioral analysis: baseline activity, anomalies, night spikes, "
            "forwarding/media/deletion patterns, and temporal behavior for this subject."
        ),
        sections=(
            SectionSpec("executive_summary", "Executive summary", "Behavior highlights"),
            SectionSpec(
                "baseline_behavior",
                "Baseline behavior",
                "Typical patterns if evidenced",
            ),
            SectionSpec(
                "anomalies",
                "Anomalies detected",
                "Spikes / outliers with cites",
            ),
            SectionSpec(
                "temporal_patterns",
                "Temporal patterns",
                "Time-of-day / day-of-week signals",
            ),
            SectionSpec(
                "implications",
                "Implications",
                "Cautious operational implications",
            ),
            SectionSpec("evidence_index", "Evidence index", "List [E#] labels used"),
        ),
    ),
}


def get_report_spec(report_type: ReportType | str) -> ReportTypeSpec:
    """Resolve a report type to its section catalog."""
    if isinstance(report_type, ReportType):
        return _REPORT_SPECS[report_type]
    key = str(report_type).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "user": ReportType.USER_INTELLIGENCE,
        "user_intel": ReportType.USER_INTELLIGENCE,
        "user_intelligence_report": ReportType.USER_INTELLIGENCE,
        "investigation_report": ReportType.INVESTIGATION,
        "case": ReportType.CASE_SUMMARY,
        "case_summary_report": ReportType.CASE_SUMMARY,
        "behavioral": ReportType.BEHAVIORAL_ANALYSIS,
        "behavioral_report": ReportType.BEHAVIORAL_ANALYSIS,
        "behavior": ReportType.BEHAVIORAL_ANALYSIS,
    }
    if key in aliases:
        return _REPORT_SPECS[aliases[key]]
    try:
        return _REPORT_SPECS[ReportType(key)]
    except ValueError as exc:
        raise ValueError(
            f"Unknown report type {report_type!r}. "
            f"Expected one of: {', '.join(t.value for t in ReportType)}."
        ) from exc


def format_section_outline(spec: ReportTypeSpec) -> str:
    """Render section headings + guidance for the prompt."""
    lines: list[str] = []
    for i, section in enumerate(spec.sections, start=1):
        lines.append(f"{i}. {section.title} (id={section.section_id})")
        lines.append(f"   Guidance: {section.guidance}")
    return "\n".join(lines)
