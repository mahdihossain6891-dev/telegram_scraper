"""TimelineTool — chronological activity from personnel / messages."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools._session import as_mongo_session, user_id_from_subject
from ai.investigation.tools.base import ToolResult


class TimelineTool:
    name = "timeline"

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        db = getattr(ctx, "db", None)
        session = as_mongo_session(db)
        uid = user_id_from_subject(getattr(ctx, "subject", {}))
        if session is None or uid is None:
            return ToolResult(
                name=self.name,
                ok=False,
                error="Timeline requires database + user_id",
                summary="No timeline available.",
            )

        from personnel import get_personnel_detail

        detail = get_personnel_detail(session, uid)
        if not detail:
            return ToolResult(
                name=self.name,
                ok=False,
                error="No messages for timeline",
                summary="No timeline events found.",
            )

        history = list(detail.get("messages") or detail.get("history") or [])
        events = []
        for m in sorted(history, key=lambda x: str(x.get("timestamp") or ""))[:40]:
            events.append(
                {
                    "timestamp": m.get("timestamp"),
                    "chat_id": m.get("chat_id"),
                    "group_name": m.get("group_name"),
                    "message_id": m.get("message_id") or m.get("id"),
                    "snippet": (m.get("text") or "")[:200],
                    "keywords": m.get("keywords") or [],
                    "categories": m.get("categories") or [],
                }
            )

        return ToolResult(
            name=self.name,
            ok=True,
            summary=f"Timeline with {len(events)} event(s) for user {uid}.",
            data={
                "user_id": uid,
                "first_seen": detail.get("first_seen"),
                "last_seen": detail.get("last_seen"),
                "events": events,
            },
        )
