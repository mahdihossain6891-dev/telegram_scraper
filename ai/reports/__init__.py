"""AI report generation — structured, RAG-grounded, stored in ``ai_reports``."""

from __future__ import annotations

from .case_brief import CaseBriefGenerator
from .exporters import ReportExporter
from .generator import ReportGenerator
from .models import GeneratedReport, ReportSection, report_from_document
from .repository import COLLECTION as REPORT_COLLECTION
from .repository import ReportRepository
from .types import ReportType, ReportTypeSpec, SectionSpec, get_report_spec
from .user_narrative import UserNarrativeGenerator

__all__ = [
    "REPORT_COLLECTION",
    "CaseBriefGenerator",
    "GeneratedReport",
    "ReportExporter",
    "ReportGenerator",
    "ReportRepository",
    "ReportSection",
    "ReportType",
    "ReportTypeSpec",
    "SectionSpec",
    "UserNarrativeGenerator",
    "get_report_spec",
    "report_from_document",
]
