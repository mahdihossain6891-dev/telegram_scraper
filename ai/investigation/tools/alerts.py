"""AlertTool — read-only alerts from behavioral profiles / subject."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools._session import as_mongo_session, user_id_from_subject
from ai.investigation.tools.base import ToolResult
from ai.investigation.validators import extract_alert_id


class AlertTool:
    name = "alerts"

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        db = getattr(ctx, "db", None)
        session = as_mongo_session(db)
        subject = getattr(ctx, "subject", {}) or {}
        question = getattr(ctx, "question", "") or ""
        alert_id = subject.get("alert_id") or extract_alert_id(question)
        uid = user_id_from_subject(subject)

        alerts: list[dict[str, Any]] = []
        if session is not None and uid is not None:
            from behavioral_analytics import get_behavioral_profile

            profile = get_behavioral_profile(session, uid)
            if profile:
                alerts = list(profile.get("alerts") or [])

        if alert_id:
            matched = [
                a
                for a in alerts
                if str(a.get("id") or a.get("alert_id") or a.get("type") or "")
                == str(alert_id)
                or str(alert_id) in str(a)
            ]
            if matched:
                return ToolResult(
                    name=self.name,
                    ok=True,
                    summary=f"Found alert matching '{alert_id}'.",
                    data={"alert_id": alert_id, "alerts": matched, "user_id": uid},
                )
            if uid is None and not alerts:
                return ToolResult(
                    name=self.name,
                    ok=False,
                    error=f"Alert '{alert_id}' not found in monitored data",
                    summary="No matching alert found.",
                    data={"alert_id": alert_id},
                )
            # Alert ID provided but only user-level alerts available.
            return ToolResult(
                name=self.name,
                ok=True,
                summary=(
                    f"No exact alert id match for '{alert_id}'. "
                    f"Returning {len(alerts)} profile alert(s)."
                ),
                data={"alert_id": alert_id, "alerts": alerts[:20], "user_id": uid},
            )

        return ToolResult(
            name=self.name,
            ok=True,
            summary=f"{len(alerts)} alert(s) for bound subject.",
            data={"alerts": alerts[:20], "user_id": uid},
        )
