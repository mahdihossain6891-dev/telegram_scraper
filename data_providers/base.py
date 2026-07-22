"""DataProvider contract — backend selects implementation per console mode."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class DataProvider(ABC):
    """Supplies dashboard / investigation data for the active console mode."""

    @property
    @abstractmethod
    def mode(self) -> str:
        """``live`` or ``simulation``."""

    @property
    @abstractmethod
    def source_label(self) -> str:
        """Provenance string returned to clients (e.g. ``mongodb``, ``simulation``)."""

    @abstractmethod
    def get_export_payload(self) -> dict[str, Any]:
        """ExportPayload-shaped document for the Threat Console."""

    def get_investigations(self) -> dict[str, Any]:
        """Investigation-oriented view of the current data set."""
        payload = self.get_export_payload()
        personnel = list(payload.get("personnel") or [])
        messages = list(payload.get("messages") or [])
        flagged = [
            m
            for m in messages
            if m.get("risk_score") or m.get("risk_level") or m.get("keywords")
        ]
        return {
            "mode": self.mode,
            "source": self.source_label,
            "counts": dict(payload.get("counts") or {}),
            "personnel": personnel,
            "flagged_messages": flagged[:200],
            "payload": payload,
        }

    def list_personnel(
        self,
        *,
        chat_id: int | None = None,
        suspicious_only: bool = False,
        keyword: str | None = None,
        query: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: str = "suspicious_count",
    ) -> list[dict[str, Any]]:
        rows = list(self.get_export_payload().get("personnel") or [])
        if suspicious_only:
            rows = [r for r in rows if int(r.get("suspicious_count") or 0) > 0]
        if chat_id is not None:
            rows = [
                r
                for r in rows
                if chat_id in (r.get("chat_ids") or [])
            ]
        if keyword:
            needle = keyword.lower()
            rows = [
                r
                for r in rows
                if any(needle in str(k).lower() for k in (r.get("keyword_list") or []))
            ]
        if query:
            q = query.lower().strip().lstrip("@")
            rows = [
                r
                for r in rows
                if q
                in " ".join(
                    str(x or "")
                    for x in (
                        r.get("display_name"),
                        r.get("username"),
                        r.get("user_id"),
                    )
                ).lower()
            ]
        reverse = True
        key = sort_by if (rows and sort_by in rows[0]) else "suspicious_count"
        try:
            rows.sort(key=lambda r: r.get(key) or 0, reverse=reverse)
        except TypeError:
            rows.sort(key=lambda r: str(r.get(key) or ""), reverse=reverse)
        return rows

    def get_personnel_detail(self, user_id: int) -> dict[str, Any] | None:
        payload = self.get_export_payload()
        for row in payload.get("personnel") or []:
            if int(row.get("user_id") or 0) == user_id:
                messages = [
                    m
                    for m in payload.get("messages") or []
                    if int(m.get("sender_id") or 0) == user_id
                ]
                groups = [
                    c
                    for c in payload.get("chats") or []
                    if c.get("id") in (row.get("chat_ids") or [])
                ]
                return {
                    **row,
                    "messages": messages[:50],
                    "groups": groups,
                    "history": messages[:50],
                }
        return None

    def behavioral_overview(self) -> dict[str, Any]:
        return {"profiles": 0, "mode": self.mode}

    def list_behavioral_profiles(self, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    def get_behavioral_profile(self, user_id: int) -> dict[str, Any] | None:
        return None

    def allows_live_operations(self) -> bool:
        """Scrape, Telegram alerts, etc. — disabled in simulation."""
        return self.mode == "live"

    def allows_simulation_scrape(self) -> bool:
        """AI dummy scrape into the simulation database."""
        return False
