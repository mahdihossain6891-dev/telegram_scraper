"""Dynamic risk scoring for messages, users, and channels."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

RiskLevel = Literal["Low", "Medium", "High", "Critical"]

# Higher = more severe. Matched case-insensitively against keyword hits / text.
KEYWORD_RISK_WEIGHTS: dict[str, int] = {
    # Critical phrases / weapons
    "passport for sale": 50,
    "passports for sale": 50,
    "fake passport": 48,
    "ak-47": 40,
    "ak47": 40,
    "assault rifle sale": 42,
    "ghost gun": 38,
    "ghost guns": 38,
    "untraceable gun": 40,
    "illegal gun": 36,
    "illegal guns": 36,
    "arms trafficking": 40,
    "firearms trafficking": 38,
    "weapons trafficking": 38,
    "gun smuggling": 35,
    "weapon smuggling": 35,
    "gun running": 34,
    # Narcotics (high)
    "fentanyl": 40,
    "heroin": 36,
    "cocaine": 35,
    "methamphetamine": 34,
    "meth": 32,
    "opioid": 30,
    "drug trafficking": 38,
    "drug smuggling": 36,
    "drug dealer": 32,
    "illicit drugs": 30,
    "synthetic drugs": 30,
    "narcotics": 28,
    "narcotic": 26,
    "drug deal": 28,
    "smuggling drugs": 34,
    # Trafficking
    "human trafficking": 45,
    "sex trafficking": 45,
    "child exploitation": 48,
    "trafficking ring": 40,
    "trafficking victims": 38,
    "forced labor": 36,
    "forced labour": 36,
    "modern slavery": 38,
    "labor trafficking": 36,
    "labour trafficking": 36,
    "human smuggling": 34,
    "smuggling persons": 34,
    # Mid / generic terms (still flagged by keyword filter)
    "trafficking": 22,
    "firearm": 18,
    "firearms": 18,
    "weapon": 16,
    "weapons": 16,
    "gun": 14,
    "guns": 14,
    "ammunition deal": 28,
    "illegal weapons": 32,
    "drug": 12,
    "drugs": 12,
    "smuggling": 14,
    "smuggle": 14,
}

# Behavioral bonuses (applied to users / channels, not raw message keyword sum)
REPEAT_OFFENSE_BONUS = 20  # user with 3+ flagged messages
MULTI_GROUP_BONUS = 30  # user observed in 2+ monitored chats
NEW_ACCOUNT_BONUS = 15  # first_seen within NEW_ACCOUNT_DAYS
NEW_ACCOUNT_DAYS = 14
MULTI_CATEGORY_MESSAGE_BONUS = 15  # single message hits 2+ categories
CHAT_VOLUME_BONUS = 10  # chat with 10+ flagged messages
CHAT_MULTI_SENDER_BONUS = 15  # chat with 3+ distinct senders

LEVEL_THRESHOLDS: tuple[tuple[int, RiskLevel], ...] = (
    (71, "Critical"),
    (41, "High"),
    (21, "Medium"),
    (0, "Low"),
)


@dataclass(frozen=True)
class RiskAssessment:
    """Scored risk with human-readable level and factor breakdown."""

    score: int
    level: RiskLevel
    factors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "factors": list(self.factors),
        }


def classify_risk(score: int) -> RiskLevel:
    """Map a 0–100 score to Low / Medium / High / Critical."""
    capped = max(0, min(100, int(score)))
    for threshold, level in LEVEL_THRESHOLDS:
        if capped >= threshold:
            return level
    return "Low"


def _clamp(score: int) -> int:
    return max(0, min(100, int(score)))


def keyword_weight(keyword: str) -> int:
    """Return the configured weight for a keyword (default modest score)."""
    key = keyword.strip().lower()
    if key in KEYWORD_RISK_WEIGHTS:
        return KEYWORD_RISK_WEIGHTS[key]
    # Unknown flagged term still contributes lightly
    return 10


def score_message(
    *,
    keywords: list[str] | tuple[str, ...],
    categories: list[str] | tuple[str, ...] | None = None,
    text: str | None = None,
) -> RiskAssessment:
    """Score a single flagged message from keyword hits and optional text phrases."""
    factors: list[str] = []
    total = 0
    seen: set[str] = set()

    for raw in keywords:
        key = str(raw).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        weight = keyword_weight(key)
        total += weight
        factors.append(f"keyword:{key}+{weight}")

    # Catch high-value phrases that may appear in text even if not listed as hits
    lowered = (text or "").lower()
    for phrase, weight in KEYWORD_RISK_WEIGHTS.items():
        if " " not in phrase and "-" not in phrase:
            continue
        if phrase in seen:
            continue
        if phrase in lowered:
            seen.add(phrase)
            total += weight
            factors.append(f"phrase:{phrase}+{weight}")

    cats = {str(c) for c in (categories or []) if c}
    if len(cats) >= 2:
        total += MULTI_CATEGORY_MESSAGE_BONUS
        factors.append(f"multi_category+{MULTI_CATEGORY_MESSAGE_BONUS}")

    score = _clamp(total)
    return RiskAssessment(score=score, level=classify_risk(score), factors=tuple(factors))


def score_user(
    *,
    message_count: int,
    chat_ids: list[int] | tuple[int, ...],
    keywords: dict[str, int] | None = None,
    categories: dict[str, int] | None = None,
    first_seen: datetime | None = None,
    max_message_score: int | None = None,
    now: datetime | None = None,
) -> RiskAssessment:
    """Score a sender from activity rollups + behavioral signals."""
    factors: list[str] = []
    total = 0

    # Base from strongest keyword weights observed (scaled by frequency lightly)
    keyword_scores = []
    for key, count in (keywords or {}).items():
        if key == "(flagged)":
            continue
        w = keyword_weight(key)
        keyword_scores.append(w + min(10, max(0, int(count) - 1) * 2))
        factors.append(f"keyword:{key}×{count}→{keyword_scores[-1]}")
    if keyword_scores:
        total += max(keyword_scores)
    elif max_message_score:
        total += max_message_score
        factors.append(f"max_message_score+{max_message_score}")

    if len({str(c) for c in (categories or {}) if c}) >= 2:
        total += MULTI_CATEGORY_MESSAGE_BONUS
        factors.append(f"multi_category+{MULTI_CATEGORY_MESSAGE_BONUS}")

    if message_count >= 3:
        total += REPEAT_OFFENSE_BONUS
        factors.append(f"repeated_offenses+{REPEAT_OFFENSE_BONUS}")

    if len(set(chat_ids)) >= 2:
        total += MULTI_GROUP_BONUS
        factors.append(f"multiple_groups+{MULTI_GROUP_BONUS}")

    current = now or datetime.now(timezone.utc)
    if first_seen is not None:
        fs = first_seen
        if fs.tzinfo is None:
            fs = fs.replace(tzinfo=timezone.utc)
        if current - fs <= timedelta(days=NEW_ACCOUNT_DAYS):
            total += NEW_ACCOUNT_BONUS
            factors.append(f"new_account+{NEW_ACCOUNT_BONUS}")

    score = _clamp(total)
    return RiskAssessment(score=score, level=classify_risk(score), factors=tuple(factors))


def score_chat(
    *,
    message_count: int,
    sender_count: int,
    keywords: dict[str, int] | None = None,
    categories: dict[str, int] | None = None,
    max_message_score: int | None = None,
) -> RiskAssessment:
    """Score a monitored group/channel from aggregate flagged activity."""
    factors: list[str] = []
    total = 0

    keyword_scores = [keyword_weight(k) for k in (keywords or {}) if k != "(flagged)"]
    if keyword_scores:
        total += max(keyword_scores)
        top = max(keywords or {}, key=lambda k: keyword_weight(k))
        factors.append(f"top_keyword:{top}+{keyword_weight(top)}")
    elif max_message_score:
        total += max_message_score
        factors.append(f"max_message_score+{max_message_score}")

    if len({str(c) for c in (categories or {}) if c}) >= 2:
        total += MULTI_CATEGORY_MESSAGE_BONUS
        factors.append(f"multi_category+{MULTI_CATEGORY_MESSAGE_BONUS}")

    if message_count >= 10:
        total += CHAT_VOLUME_BONUS
        factors.append(f"high_volume+{CHAT_VOLUME_BONUS}")
    elif message_count >= 3:
        total += 8
        factors.append("volume+8")

    if sender_count >= 3:
        total += CHAT_MULTI_SENDER_BONUS
        factors.append(f"multiple_senders+{CHAT_MULTI_SENDER_BONUS}")

    score = _clamp(total)
    return RiskAssessment(score=score, level=classify_risk(score), factors=tuple(factors))
