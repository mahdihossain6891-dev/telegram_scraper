"""Personnel / dossier tool."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools._session import as_mongo_session, user_id_from_subject
from ai.investigation.tools.base import ToolResult


class PersonnelTool:
    name = "personnel"

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        db = getattr(ctx, "db", None)
        session = as_mongo_session(db)
        uid = user_id_from_subject(getattr(ctx, "subject", {}))
        if session is None or uid is None:
            return ToolResult(
                name=self.name,
                ok=False,
                error="Personnel detail requires database + user_id",
                summary="No personnel dossier available.",
            )

        from personnel import get_personnel_detail

        detail = get_personnel_detail(session, uid)
        if not detail:
            return ToolResult(
                name=self.name,
                ok=False,
                error=f"No personnel record for user {uid}",
                summary="No personnel record found.",
            )

        history = list(detail.get("messages") or detail.get("history") or [])[:30]
        groups = list(detail.get("groups") or [])[:20]
        return ToolResult(
            name=self.name,
            ok=True,
            summary=(
                f"Dossier for user {uid}: messages={len(history)}, "
                f"groups={len(groups)}, risk={detail.get('risk_score')}."
            ),
            data={
                "user_id": uid,
                "display_name": detail.get("display_name") or detail.get("name"),
                "username": detail.get("username"),
                "risk_score": detail.get("risk_score"),
                "risk_level": detail.get("risk_level"),
                "message_count": detail.get("message_count"),
                "first_seen": detail.get("first_seen"),
                "last_seen": detail.get("last_seen"),
                "groups": groups,
                "recent_messages": [
                    {
                        "id": m.get("id") or m.get("message_id"),
                        "timestamp": m.get("timestamp"),
                        "chat_id": m.get("chat_id"),
                        "group_name": m.get("group_name"),
                        "text": (m.get("text") or "")[:240],
                        "keywords": m.get("keywords") or [],
                    }
                    for m in history[:15]
                ],
            },
        )
