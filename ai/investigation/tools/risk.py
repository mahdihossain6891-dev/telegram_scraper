"""RiskTool — wraps risk_scoring / stored personnel risk."""

from __future__ import annotations

from typing import Any

from ai.investigation.tools._session import as_mongo_session, user_id_from_subject
from ai.investigation.tools.base import ToolResult


class RiskTool:
    name = "risk"

    def run(self, *, ctx: Any, **kwargs: Any) -> ToolResult:
        db = getattr(ctx, "db", None)
        session = as_mongo_session(db)
        uid = user_id_from_subject(getattr(ctx, "subject", {}))
        if uid is None:
            return ToolResult(
                name=self.name,
                ok=False,
                error="No user_id for risk assessment",
                summary="Risk requires a resolved user.",
            )

        # Prefer stored activity risk; fall back to score_user if possible.
        risk_score = None
        risk_level = None
        factors: list[str] = []
        if session is not None:
            from personnel import get_personnel_detail

            detail = get_personnel_detail(session, uid)
            if detail:
                risk_score = detail.get("risk_score")
                risk_level = detail.get("risk_level")
                factors = list(detail.get("risk_factors") or [])[:20]

        if risk_score is None and session is not None:
            try:
                from risk_scoring import classify_risk, score_user

                detail = None
                try:
                    from personnel import get_personnel_detail

                    detail = get_personnel_detail(session, uid)
                except Exception:  # noqa: BLE001
                    detail = None
                if detail:
                    assessment = score_user(
                        message_count=int(detail.get("message_count") or 0),
                        chat_ids=[
                            int(g.get("chat_id"))
                            for g in (detail.get("groups") or [])
                            if g.get("chat_id") is not None
                        ],
                        keywords=detail.get("keywords") or {},
                        categories=detail.get("categories") or {},
                    )
                    risk_score = assessment.score
                    risk_level = assessment.level
                    factors = list(assessment.factors)[:20]
            except Exception:  # noqa: BLE001
                pass

        if risk_score is None:
            subject = getattr(ctx, "subject", {}) or {}
            risk_score = subject.get("risk_score")
            if risk_score is not None:
                from risk_scoring import classify_risk

                risk_level = classify_risk(int(risk_score))

        if risk_score is None:
            return ToolResult(
                name=self.name,
                ok=False,
                error="Unable to compute risk",
                summary="No risk data available for this user.",
            )

        return ToolResult(
            name=self.name,
            ok=True,
            summary=f"Risk score={risk_score} ({risk_level}) for user {uid}.",
            data={
                "user_id": uid,
                "risk_score": int(risk_score),
                "risk_level": risk_level,
                "factors": factors,
            },
        )
