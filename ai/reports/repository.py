"""Persistence for AI reports (``ai_reports`` only).

Never writes messages, user_activity, behavioral_analytics, or other
operational intelligence collections.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo.database import Database as MongoDatabase

from ai.reports.models import GeneratedReport, report_from_document

logger = logging.getLogger("ai.reports.repository")

COLLECTION = "ai_reports"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReportRepository:
    """Store generated reports separately from operational intel."""

    def __init__(
        self,
        db: MongoDatabase | None = None,
        *,
        collection_name: str = COLLECTION,
    ) -> None:
        self.db = db
        self.collection_name = collection_name
        self._memory: dict[str, dict[str, Any]] = {}
        if db is not None:
            self.collection = db[collection_name]
        else:
            self.collection = None

    def ensure_indexes(self) -> None:
        if self.collection is None:
            return
        self.collection.create_index(
            [("subject_type", 1), ("subject_id", 1), ("report_type", 1)],
            name="ix_ai_reports_subject_type",
        )
        self.collection.create_index(
            [("created_at", -1)],
            name="ix_ai_reports_created",
        )
        self.collection.create_index(
            [("report_type", 1)],
            name="ix_ai_reports_type",
        )

    def save(self, report: GeneratedReport) -> GeneratedReport:
        """Insert or replace a report document."""
        if report.created_at is None:
            report.created_at = _utcnow()
        doc = report.to_document()
        doc["updated_at"] = _utcnow()
        if self.collection is not None:
            self.collection.replace_one({"_id": report.report_id}, doc, upsert=True)
        else:
            self._memory[report.report_id] = dict(doc)
        logger.info(
            "ai_report_saved",
            extra={
                "ai_report_id": report.report_id,
                "ai_report_type": report.report_type,
                "ai_refused": report.refused,
            },
        )
        return report

    def get(self, report_id: str) -> GeneratedReport | None:
        if self.collection is not None:
            doc = self.collection.find_one({"_id": report_id})
            return report_from_document(doc) if doc else None
        doc = self._memory.get(report_id)
        return report_from_document(doc) if doc else None

    def list_for_subject(
        self,
        *,
        subject_type: str,
        subject_id: str,
        report_type: str | None = None,
        limit: int = 50,
    ) -> list[GeneratedReport]:
        query: dict[str, Any] = {
            "subject_type": subject_type,
            "subject_id": str(subject_id),
        }
        if report_type:
            query["report_type"] = report_type
        if self.collection is not None:
            cursor = (
                self.collection.find(query)
                .sort([("created_at", -1)])
                .limit(max(1, int(limit)))
            )
            return [report_from_document(d) for d in cursor]
        rows = [
            d
            for d in self._memory.values()
            if d.get("subject_type") == subject_type
            and str(d.get("subject_id")) == str(subject_id)
            and (not report_type or d.get("report_type") == report_type)
        ]
        rows.sort(key=lambda d: d.get("created_at") or datetime.min, reverse=True)
        return [report_from_document(d) for d in rows[: max(1, int(limit))]]

    def count(self) -> int:
        if self.collection is not None:
            return int(self.collection.count_documents({}))
        return len(self._memory)
