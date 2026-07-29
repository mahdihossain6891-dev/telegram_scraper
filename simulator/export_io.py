"""JSON and CSV export helpers for simulator entities."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def export_records_json(records: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2, ensure_ascii=False)
    return path


def load_records_json(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of records.")
    return data


def export_records_csv(records: list[dict[str, Any]], path: Path) -> Path:
    if not records:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted(records[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = {key: _csv_value(record.get(key)) for key in fieldnames}
            writer.writerow(row)
    return path


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
