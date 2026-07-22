"""Case / investigation report wrappers."""

from __future__ import annotations

from typing import Any

from ai.reports.generator import ReportGenerator
from ai.reports.models import GeneratedReport
from ai.reports.types import ReportType


class CaseBriefGenerator:
    """Builds structured case summaries or investigation reports via RAG."""

    def __init__(self, generator: ReportGenerator | None = None, **kwargs: Any) -> None:
        self.generator = generator or ReportGenerator.from_settings(**kwargs)

    def generate(
        self,
        subject_id: str,
        *,
        context: dict[str, Any] | None = None,
        report_type: ReportType | str = ReportType.CASE_SUMMARY,
        **kwargs: Any,
    ) -> GeneratedReport:
        """Generate a case summary or investigation report."""
        context = context or {}
        notes = str(context.get("analyst_notes") or kwargs.pop("analyst_notes", "") or "")
        filters = context.get("filters")
        subject_label = context.get("subject_label") or kwargs.pop("subject_label", None)
        subject_type = str(
            context.get("subject_type") or kwargs.pop("subject_type", "case")
        )
        kind = report_type
        if context.get("report_type"):
            kind = context["report_type"]
        resolved = kind.value if isinstance(kind, ReportType) else str(kind)
        if resolved in {
            ReportType.INVESTIGATION.value,
            "investigation",
            "investigation_report",
        }:
            return self.generator.generate_investigation(
                subject_id,
                subject_type=subject_type if subject_type != "case" else "investigation",
                analyst_notes=notes,
                filters=filters,
                subject_label=subject_label,
                **kwargs,
            )
        return self.generator.generate_case_summary(
            subject_id,
            subject_type=subject_type,
            analyst_notes=notes,
            filters=filters,
            subject_label=subject_label,
            **kwargs,
        )
