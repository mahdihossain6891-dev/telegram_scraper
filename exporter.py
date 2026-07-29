"""Export stored Telegram data to CSV and JSON."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config import Settings, ensure_directories, load_settings
from database import MongoSession, get_session, init_db
from models import Chat, ExtractedEntity, Message, User
from personnel import ensure_user_activity, list_personnel
from utils import get_logger, setup_logging

logger = get_logger("exporter")


class ExportError(Exception):
    """Raised when export fails."""


@dataclass(frozen=True)
class ExportResult:
    """Summary of exported files and record counts."""

    csv_files: tuple[Path, ...]
    json_file: Path
    chat_count: int
    user_count: int
    message_count: int
    entity_count: int


def _iso(value: datetime | None) -> str | None:
    """Return an ISO timestamp string when available."""
    return value.isoformat() if value is not None else None


def _chat_rows(chats: list[Chat]) -> list[dict[str, Any]]:
    return [
        {
            "id": chat.id,
            "title": chat.title,
            "username": chat.username,
            "chat_type": chat.chat_type,
            "created_at": _iso(chat.created_at),
            "updated_at": _iso(chat.updated_at),
            "risk_score": chat.risk_score,
            "risk_level": chat.risk_level,
            "risk_factors": chat.risk_factors,
        }
        for chat in chats
    ]


def _user_rows(users: list[User]) -> list[dict[str, Any]]:
    return [
        {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "created_at": _iso(user.created_at),
            "updated_at": _iso(user.updated_at),
        }
        for user in users
    ]


def _message_rows(messages: list[Message]) -> list[dict[str, Any]]:
    return [
        {
            "id": message.id,
            "message_id": message.message_id,
            "chat_id": message.chat_id,
            "sender_id": message.sender_id,
            "timestamp": _iso(message.timestamp),
            "text": message.text,
            "media_type": message.media_type,
            "reply_to_message_id": message.reply_to_message_id,
            "forward_from_chat_id": message.forward_from_chat_id,
            "forward_from_message_id": message.forward_from_message_id,
            "views": message.views,
            "scraped_at": _iso(message.scraped_at),
            "risk_score": message.risk_score,
            "risk_level": message.risk_level,
            "risk_factors": message.risk_factors,
        }
        for message in messages
    ]


def _entity_rows(entities: list[ExtractedEntity]) -> list[dict[str, Any]]:
    return [
        {
            "id": entity.id,
            "message_row_id": entity.message_row_id,
            "entity_type": entity.entity_type,
            "entity_value": entity.entity_value,
            "start_offset": entity.start_offset,
            "end_offset": entity.end_offset,
            "created_at": _iso(entity.created_at),
        }
        for entity in entities
    ]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON document to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


class DataExporter:
    """Load database records and export them to CSV and JSON."""

    def __init__(self, session: MongoSession) -> None:
        self.session = session

    def load_records(
        self,
    ) -> tuple[list[Chat], list[User], list[Message], list[ExtractedEntity]]:
        """Load all exportable records from the database."""
        return (
            self.session.list_chats(),
            self.session.list_users(),
            self.session.list_messages(),
            self.session.list_entities(),
        )

    def build_payload(self) -> dict[str, Any]:
        """Build the export.json-shaped payload from the current database."""
        chats, users, messages, entities = self.load_records()
        chat_rows = _chat_rows(chats)
        user_rows = _user_rows(users)
        message_rows = _message_rows(messages)
        entity_rows = _entity_rows(entities)
        ensure_user_activity(self.session)
        personnel_rows = list_personnel(self.session, sort_by="suspicious_count")
        return {
            "exported_at": datetime.now().astimezone().isoformat(),
            "counts": {
                "chats": len(chat_rows),
                "users": len(user_rows),
                "messages": len(message_rows),
                "entities": len(entity_rows),
                "personnel": len(personnel_rows),
            },
            "chats": chat_rows,
            "users": user_rows,
            "messages": message_rows,
            "entities": entity_rows,
            "personnel": personnel_rows,
        }

    def export_all(self, exports_dir: Path) -> ExportResult:
        """Export chats, users, messages, and entities to CSV and JSON."""
        exports_dir.mkdir(parents=True, exist_ok=True)
        chats, users, messages, entities = self.load_records()

        chat_rows = _chat_rows(chats)
        user_rows = _user_rows(users)
        message_rows = _message_rows(messages)
        entity_rows = _entity_rows(entities)

        csv_paths = (
            exports_dir / "chats.csv",
            exports_dir / "users.csv",
            exports_dir / "messages.csv",
            exports_dir / "entities.csv",
        )
        _write_csv(csv_paths[0], chat_rows)
        _write_csv(csv_paths[1], user_rows)
        _write_csv(csv_paths[2], message_rows)
        _write_csv(csv_paths[3], entity_rows)

        json_path = exports_dir / "export.json"
        payload = self.build_payload()
        _write_json(json_path, payload)

        logger.info(
            "Exported chats=%d users=%d messages=%d entities=%d to %s",
            len(chat_rows),
            len(user_rows),
            len(message_rows),
            len(entity_rows),
            exports_dir,
        )

        return ExportResult(
            csv_files=csv_paths,
            json_file=json_path,
            chat_count=len(chat_rows),
            user_count=len(user_rows),
            message_count=len(message_rows),
            entity_count=len(entity_rows),
        )


def run_export(settings: Settings | None = None) -> ExportResult:
    """Export all stored data using configured settings."""
    cfg = ensure_directories(settings)
    init_db(cfg)

    with get_session(cfg) as session:
        exporter = DataExporter(session)
        return exporter.export_all(cfg.exports_dir)


def build_export_payload(
    settings: Settings | None = None,
    *,
    database_name: str | None = None,
) -> dict[str, Any]:
    """Return the live export.json-shaped payload from MongoDB without writing files."""
    cfg = ensure_directories(settings)
    if database_name:
        from database import get_db_by_name, get_session_for_database

        with get_session_for_database(database_name, cfg) as session:
            payload = DataExporter(session).build_payload()
    else:
        init_db(cfg)
        with get_session(cfg) as session:
            payload = DataExporter(session).build_payload()
    if database_name:
        payload["simulation"] = {
            "database": database_name,
            "environment": "simulation",
            "isolated": True,
        }
    return payload


def print_export_summary(result: ExportResult, exports_dir: Path) -> None:
    """Print export results to stdout."""
    print("\nExport complete")
    print("==============")
    print(f"Directory: {exports_dir}")
    print(f"  Chats:     {result.chat_count}")
    print(f"  Users:     {result.user_count}")
    print(f"  Messages:  {result.message_count}")
    print(f"  Entities:  {result.entity_count}")
    print("\nCSV files:")
    for path in result.csv_files:
        print(f"  - {path.name}")
    print(f"\nJSON file:")
    print(f"  - {result.json_file.name}")


def main() -> None:
    """CLI entry point for data export."""
    cfg = ensure_directories()
    setup_logging(cfg)

    try:
        result = run_export(cfg)
    except OSError as exc:
        logger.error("Export failed: %s", exc)
        print(f"Export failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print_export_summary(result, cfg.exports_dir)

    if result.message_count == 0:
        print("\nNo messages exported. Run scrape.bat first to collect flagged messages.")


if __name__ == "__main__":
    main()
