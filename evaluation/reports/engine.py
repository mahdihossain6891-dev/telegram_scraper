"""Report generation engine."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


class ReportEngine:
    def generate(
        self,
        *,
        benchmark: dict[str, Any],
        regression: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        reports = [
            {"id": "benchmark", "title": "Benchmark Report", "format": "json", "data": benchmark},
            {"id": "pipeline", "title": "Pipeline Report", "format": "json", "data": self._pipeline_report(benchmark)},
            {"id": "sebastian", "title": "Sebastian Report", "format": "json", "data": self._sebastian_report(benchmark)},
            {"id": "performance", "title": "Performance Report", "format": "json", "data": benchmark.get("performance") or {}},
            {"id": "executive", "title": "Executive Summary", "format": "json", "data": self._executive(benchmark)},
        ]
        if regression:
            reports.append(
                {"id": "regression", "title": "Regression Report", "format": "json", "data": regression}
            )
        return reports

    def export(self, report: dict[str, Any], fmt: str) -> str:
        data = report.get("data") or {}
        title = str(report.get("title") or report.get("id") or "report")
        if fmt == "json":
            return json.dumps(data, indent=2, default=str)
        if fmt == "csv":
            return self._to_csv(data)
        if fmt == "md":
            return f"# {title}\n\n```json\n{json.dumps(data, indent=2, default=str)}\n```\n"
        return json.dumps(data, default=str)

    def _pipeline_report(self, benchmark: dict[str, Any]) -> dict[str, Any]:
        sub = (benchmark.get("subsystems") or {}).get("pipeline") or {}
        return sub.get("metrics") or {}

    def _sebastian_report(self, benchmark: dict[str, Any]) -> dict[str, Any]:
        sub = (benchmark.get("subsystems") or {}).get("sebastian") or {}
        return sub.get("metrics") or {}

    def _executive(self, benchmark: dict[str, Any]) -> dict[str, Any]:
        iqs = benchmark.get("iqs") or {}
        return {
            "intelligence_quality_score": iqs.get("iqs"),
            "detection_quality": iqs.get("detection_quality"),
            "alert_quality": iqs.get("alert_quality"),
            "ai_quality": iqs.get("ai_quality"),
            "performance_quality": iqs.get("performance_quality"),
            "samples_evaluated": benchmark.get("samples_evaluated"),
            "recommendation": self._recommendation(float(iqs.get("iqs") or 0)),
        }

    def _recommendation(self, iqs: float) -> str:
        if iqs >= 85:
            return "Platform quality is excellent — safe for deployment."
        if iqs >= 70:
            return "Platform quality is acceptable — review regressed subsystems before deployment."
        return "Platform quality needs improvement — do not deploy until benchmarks pass threshold."

    def _to_csv(self, data: dict[str, Any]) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["metric", "value"])
        for k, v in data.items():
            writer.writerow([k, json.dumps(v) if isinstance(v, (dict, list)) else v])
        return buf.getvalue()
