"""Input validation for investigation intents — fail closed, never invent."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ai.investigation.intents import InvestigationIntent


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    message: str = ""
    suggestions: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


_ALERT_ID_RE = re.compile(
    r"\b(?:alert(?:\s*id)?|alert_id)\s*[:=#]?\s*([A-Za-z0-9_-]+)\b",
    re.I,
)


def extract_alert_id(question: str) -> str | None:
    m = _ALERT_ID_RE.search(question or "")
    if m:
        return m.group(1)
    # Bare "alert 12345"
    m2 = re.search(r"\balert\s+(\d{3,})\b", question or "", re.I)
    return m2.group(1) if m2 else None


def validate_intent_inputs(
    intent: InvestigationIntent,
    *,
    question: str,
    subject: dict[str, Any] | None,
    entity_status: str | None = None,
) -> ValidationResult:
    """Check whether required inputs exist before tools / LLM run."""
    subject = dict(subject or {})
    requires = set(intent.requires or ())

    if intent.key == "unknown" or intent.block_llm and intent.key == "unknown":
        return ValidationResult(
            ok=False,
            message=(
                "I could not determine a clear investigation intent. "
                "Please choose an investigation type and provide a monitored target."
            ),
            suggestions=[
                "Investigate a user by @username, display name, or Telegram ID",
                "Analyze behavior for a resolved user",
                "Explain an alert by alert ID",
            ],
            missing=["intent"],
        )

    if "none" in requires and not requires - {"none"}:
        return ValidationResult(ok=True)

    missing: list[str] = []
    suggestions: list[str] = []

    if "user" in requires:
        if subject.get("user_id") is None and entity_status != "resolved":
            missing.append("user")
            suggestions.extend(
                [
                    "Enter a username, display name, or Telegram ID",
                    "Select a monitored user from search results",
                ]
            )

    if "chat" in requires:
        if subject.get("chat_id") is None and entity_status != "resolved":
            missing.append("chat")
            suggestions.extend(
                [
                    "Enter a group/channel title or Telegram chat ID",
                    "Select a monitored group or channel",
                ]
            )

    if "alert" in requires:
        alert_id = subject.get("alert_id") or extract_alert_id(question)
        if not alert_id and subject.get("user_id") is None:
            missing.append("alert")
            suggestions.extend(
                [
                    "Provide an alert ID (e.g. alert 12345)",
                    "Or select the user associated with the alert",
                ]
            )
        elif alert_id:
            subject["alert_id"] = alert_id

    if "dual_user" in requires:
        # Need at least one resolved user; second may be in question.
        if subject.get("user_id") is None:
            missing.append("users")
            suggestions.append("Provide two usernames or Telegram IDs to compare")

    if "case" in requires:
        if subject.get("case_id") is None and subject.get("user_id") is None:
            missing.append("case")
            suggestions.append("Provide a case ID or select a completed investigation")

    if not missing:
        return ValidationResult(ok=True)

    label = intent.label or intent.key
    return ValidationResult(
        ok=False,
        message=(
            f"Cannot start “{label}” — required investigation target is missing.\n\n"
            "Please search for and select a monitored entity before continuing."
        ),
        suggestions=suggestions or ["Search for a monitored user"],
        missing=missing,
    )
