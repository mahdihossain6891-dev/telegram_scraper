"""RelationshipTool — shared chats / connection edges from personnel."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools._session import as_mongo_session, user_id_from_subject
from ai.investigation.tools.base import ToolResult


class RelationshipTool:
    name = "relationship"

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        db = getattr(ctx, "db", None)
        session = as_mongo_session(db)
        uid = user_id_from_subject(getattr(ctx, "subject", {}))
        if session is None or uid is None:
            return ToolResult(
                name=self.name,
                ok=False,
                error="Relationships require database + user_id",
                summary="No relationship data available.",
            )

        from personnel import get_personnel_detail

        detail = get_personnel_detail(session, uid)
        if not detail:
            return ToolResult(
                name=self.name,
                ok=False,
                error="No personnel dossier for relationships",
                summary="No relationships found.",
            )

        groups = list(detail.get("groups") or [])
        edges = []
        for g in groups[:25]:
            edges.append(
                {
                    "type": "shared_chat",
                    "chat_id": g.get("chat_id"),
                    "title": g.get("group_name"),
                    "message_count": g.get("message_count"),
                    "suspicious_count": g.get("suspicious_count"),
                    "confidence": _edge_confidence(g),
                }
            )

        # Forward edges from recent messages when present.
        for m in list(detail.get("messages") or detail.get("history") or [])[:50]:
            # personnel history may not include forward fields; skip if absent
            if m.get("forward_from_chat_id") or m.get("forward_from"):
                edges.append(
                    {
                        "type": "forward",
                        "chat_id": m.get("chat_id"),
                        "forward_from_chat_id": m.get("forward_from_chat_id"),
                        "timestamp": m.get("timestamp"),
                        "confidence": 0.6,
                    }
                )

        return ToolResult(
            name=self.name,
            ok=True,
            summary=f"{len(edges)} relationship edge(s) for user {uid}.",
            data={"user_id": uid, "edges": edges[:40], "group_count": len(groups)},
        )


def _edge_confidence(group: dict[str, Any]) -> float:
    msgs = int(group.get("message_count") or 0)
    sus = int(group.get("suspicious_count") or 0)
    if msgs <= 0:
        return 0.2
    ratio = sus / max(msgs, 1)
    return round(min(0.95, 0.35 + min(msgs, 50) / 100 + ratio * 0.4), 2)
