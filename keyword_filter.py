"""Keyword detection for flagging messages of analytical interest."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Category = Literal["narcotics", "human_trafficking", "firearms"]

# OSINT-oriented terms for analyst review. Extend via future configuration if needed.
KEYWORDS_BY_CATEGORY: dict[Category, tuple[str, ...]] = {
    "narcotics": (
        "cocaine",
        "heroin",
        "fentanyl",
        "methamphetamine",
        "meth",
        "opioid",
        "narcotic",
        "narcotics",
        "drug trafficking",
        "drug smuggling",
        "drug deal",
        "drug dealer",
        "smuggling drugs",
        "illicit drugs",
        "synthetic drugs",
    ),
    "human_trafficking": (
        "human trafficking",
        "sex trafficking",
        "trafficking victims",
        "trafficking ring",
        "forced labor",
        "forced labour",
        "modern slavery",
        "smuggling persons",
        "child exploitation",
        "labor trafficking",
        "labour trafficking",
        "human smuggling",
    ),
    "firearms": (
        "illegal gun",
        "illegal guns",
        "firearms trafficking",
        "gun smuggling",
        "weapons trafficking",
        "weapon smuggling",
        "ghost gun",
        "ghost guns",
        "untraceable gun",
        "ammunition deal",
        "illegal weapons",
        "assault rifle sale",
        "arms trafficking",
        "gun running",
    ),
}


@dataclass(frozen=True)
class KeywordHit:
    """A keyword match within message text."""

    category: Category
    keyword: str


@dataclass(frozen=True)
class KeywordScanResult:
    """All keyword matches found in a message."""

    hits: tuple[KeywordHit, ...]

    @property
    def matched(self) -> bool:
        return bool(self.hits)

    @property
    def categories(self) -> tuple[Category, ...]:
        seen: list[Category] = []
        for hit in self.hits:
            if hit.category not in seen:
                seen.append(hit.category)
        return tuple(seen)


def _compile_patterns() -> dict[Category, list[tuple[str, re.Pattern[str]]]]:
    """Build regex patterns for each category keyword."""
    compiled: dict[Category, list[tuple[str, re.Pattern[str]]]] = {}
    for category, keywords in KEYWORDS_BY_CATEGORY.items():
        compiled[category] = []
        for keyword in keywords:
            if " " in keyword:
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            else:
                pattern = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
            compiled[category].append((keyword, pattern))
    return compiled


_PATTERNS = _compile_patterns()


def scan_message_text(text: str | None) -> KeywordScanResult:
    """Return keyword hits for narcotics, human trafficking, or firearms terms."""
    if not text or not text.strip():
        return KeywordScanResult(hits=())

    hits: list[KeywordHit] = []
    for category, patterns in _PATTERNS.items():
        for keyword, pattern in patterns:
            if pattern.search(text):
                hits.append(KeywordHit(category=category, keyword=keyword))

    return KeywordScanResult(hits=tuple(hits))
