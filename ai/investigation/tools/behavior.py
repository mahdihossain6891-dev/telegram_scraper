"""BehaviorTool — wraps behavioral_analytics module."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools._session import as_mongo_session, user_id_from_subject
from ai.investigation.tools.base import ToolResult


class BehaviorTool:
    name = "behavior"

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        db = getattr(ctx, "db", None)
        session = as_mongo_session(db)
        if session is None:
            return ToolResult(name=self.name, ok=False, error="Database unavailable")

        from behavioral_analytics import (
            behavioral_overview,
            get_behavioral_profile,
        )

        uid = user_id_from_subject(getattr(ctx, "subject", {}))
        if uid is None:
            overview = behavioral_overview(session)
            return ToolResult(
                name=self.name,
                ok=True,
                summary="Fleet behavioral overview (no user bound).",
                data={"overview": overview},
            )

        profile = get_behavioral_profile(session, uid)
        if not profile:
            return ToolResult(
                name=self.name,
                ok=False,
                error=f"No behavioral profile for user {uid}",
                summary="No behavioral profile found.",
            )
        alerts = list(profile.get("alerts") or [])
        score = profile.get("behavior_score")
        status = profile.get("behavior_status") or profile.get("status")
        forwarding = profile.get("forwarding_rate") or {}
        forward_ratio = (
            forwarding.get("forward_ratio") if isinstance(forwarding, dict) else None
        )
        night_pct = profile.get("night_activity_percentage")
        return ToolResult(
            name=self.name,
            ok=True,
            summary=(
                f"Behavior score={score}, status={status}, "
                f"alerts={len(alerts)} for user {uid}."
            ),
            data={
                "user_id": uid,
                "behavior_score": score,
                "behavior_status": status,
                "trend": profile.get("behavior_trend") or profile.get("trend"),
                "behavior_trend": profile.get("behavior_trend"),
                "first_seen": profile.get("first_seen"),
                "last_seen": profile.get("last_seen"),
                "alerts": alerts[:20],
                "metrics": {
                    k: v
                    for k, v in {
                        "message_count": profile.get("message_count"),
                        "night_activity_ratio": night_pct,
                        "night_activity_percentage": night_pct,
                        "forward_rate": forward_ratio,
                        "forwarding_rate": forwarding,
                        "media_share": profile.get("non_text_percentage"),
                        "deletion_rate": profile.get("deletion_rate"),
                        "language_switches": profile.get("language_switch_count"),
                    }.items()
                    if v is not None
                },
            },
        )
