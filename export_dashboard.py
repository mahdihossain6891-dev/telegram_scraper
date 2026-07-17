"""Load exported JSON for Streamlit Cloud and export-only dashboard mode."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import Settings
from entity_extractor import CONTENT_ENTITY_TYPES

EXPORT_FILENAMES: tuple[str, ...] = ("export.json", "export.sample.json")


@dataclass(frozen=True)
class ExportDashboardData:
    """Dashboard-ready data loaded from export.json."""

    exported_at: str
    source_path: str
    chat_summaries: tuple[dict[str, Any], ...]
    messages: tuple[dict[str, Any], ...]
    entities: tuple[dict[str, Any], ...]
    category_counts: tuple[dict[str, Any], ...]


def find_export_file(settings: Settings) -> Path | None:
    """Return the first export JSON file available for dashboard viewing."""
    candidates = [
        settings.project_root / "demo" / "export.json",
        settings.exports_dir / "export.json",
        settings.project_root / "demo" / "export.sample.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_export_dashboard(path: Path) -> ExportDashboardData:
    """Parse export.json into dashboard tables."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    chats = {int(item["id"]): item for item in payload.get("chats", [])}
    entities = payload.get("entities", [])
    messages = payload.get("messages", [])

    entities_by_message: dict[int, list[dict[str, Any]]] = {}
    category_counts: dict[str, int] = {}
    chat_summaries: dict[int, dict[str, Any]] = {}

    for chat in payload.get("chats", []):
        chat_id = int(chat["id"])
        chat_summaries[chat_id] = {
            "chat_id": chat_id,
            "title": chat.get("title") or f"Chat {chat_id}",
            "chat_type": chat.get("chat_type") or "unknown",
            "messages": 0,
            "entities": 0,
            "narcotics": 0,
            "human_trafficking": 0,
            "firearms": 0,
        }

    for entity in entities:
        message_row_id = int(entity["message_row_id"])
        bucket = entities_by_message.setdefault(message_row_id, [])
        bucket.append(entity)
        entity_type = str(entity["entity_type"])
        if entity_type in CONTENT_ENTITY_TYPES:
            continue
        category_counts[entity_type] = category_counts.get(entity_type, 0) + 1

    message_rows: list[dict[str, Any]] = []
    for message in messages:
        chat_id = int(message["chat_id"])
        chat = chats.get(chat_id, {})
        summary = chat_summaries.setdefault(
            chat_id,
            {
                "chat_id": chat_id,
                "title": chat.get("title") or f"Chat {chat_id}",
                "chat_type": chat.get("chat_type") or "unknown",
                "messages": 0,
                "entities": 0,
                "narcotics": 0,
                "human_trafficking": 0,
                "firearms": 0,
            },
        )
        summary["messages"] += 1

        message_entities = entities_by_message.get(int(message["id"]), [])
        summary["entities"] += len(message_entities)
        keywords: list[str] = []
        for entity in message_entities:
            entity_type = str(entity["entity_type"])
            if entity_type == "narcotics":
                summary["narcotics"] += 1
            elif entity_type == "human_trafficking":
                summary["human_trafficking"] += 1
            elif entity_type == "firearms":
                summary["firearms"] += 1
            if entity_type not in CONTENT_ENTITY_TYPES:
                keywords.append(str(entity["entity_value"]))

        message_rows.append(
            {
                "chat_id": chat_id,
                "chat": chat.get("title") or f"Chat {chat_id}",
                "chat_type": chat.get("chat_type") or "unknown",
                "message_id": message.get("message_id"),
                "timestamp": message.get("timestamp") or "",
                "keywords": ", ".join(keywords),
                "entities": len(message_entities),
                "text": message.get("text") or "",
            }
        )

    entity_rows = []
    for entity in entities:
        message = next((item for item in messages if int(item["id"]) == int(entity["message_row_id"])), None)
        chat_id = int(message["chat_id"]) if message else None
        chat = chats.get(chat_id or -1, {})
        entity_rows.append(
            {
                "entity_type": entity.get("entity_type"),
                "entity_value": entity.get("entity_value"),
                "message_id": message.get("message_id") if message else "",
                "chat_id": chat_id,
                "chat": chat.get("title") or "",
                "chat_type": chat.get("chat_type") or "",
                "timestamp": message.get("timestamp") if message else "",
            }
        )

    summaries = tuple(
        summary
        for summary in sorted(
            chat_summaries.values(),
            key=lambda item: (-int(item["messages"]), str(item["title"])),
        )
        if int(summary["messages"]) > 0
    )

    return ExportDashboardData(
        exported_at=str(payload.get("exported_at", "")),
        source_path=str(path),
        chat_summaries=summaries,
        messages=tuple(message_rows),
        entities=tuple(entity_rows),
        category_counts=tuple(
            {"category": key, "count": value}
            for key, value in sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
    )
