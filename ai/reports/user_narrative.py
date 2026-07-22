"""User intelligence / narrative report wrapper."""

from __future__ import annotations

from typing import Any

from ai.reports.generator import ReportGenerator
from ai.reports.models import GeneratedReport
from ai.reports.types import ReportType


class UserNarrativeGenerator:
    """Builds a per-user intelligence or behavioral narrative via RAG."""

    def __init__(self, generator: ReportGenerator | None = None, **kwargs: Any) -> None:
        self.generator = generator or ReportGenerator.from_settings(**kwargs)

    def generate(
        self,
        user_id: int,
        *,
        context: dict[str, Any] | None = None,
        behavioral: bool = False,
        **kwargs: Any,
    ) -> GeneratedReport:
        """Generate a user intelligence (or behavioral) report."""
        context = context or {}
        notes = str(context.get("analyst_notes") or kwargs.pop("analyst_notes", "") or "")
        filters = context.get("filters")
        subject_label = context.get("subject_label") or kwargs.pop("subject_label", None)
        if behavioral or context.get("report_type") == ReportType.BEHAVIORAL_ANALYSIS.value:
            return self.generator.generate_behavioral_analysis(
                user_id,
                analyst_notes=notes,
                filters=filters,
                subject_label=subject_label,
                **kwargs,
            )
        return self.generator.generate_user_intelligence(
            user_id,
            analyst_notes=notes,
            filters=filters,
            subject_label=subject_label,
            **kwargs,
        )
