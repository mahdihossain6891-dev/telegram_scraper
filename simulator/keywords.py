"""Bridge simulator content to production OSINT keyword lists (keyword_filter.py)."""

from __future__ import annotations

import random
from typing import Literal

from keyword_filter import KEYWORDS_BY_CATEGORY, Category, scan_message_text

ConsoleKeywordFilter = Literal["narcotics", "firearms", "human_trafficking", "trafficking"]

_FILTER_TO_CATEGORY: dict[str, Category] = {
    "narcotics": "narcotics",
    "firearms": "firearms",
    "human_trafficking": "human_trafficking",
    "trafficking": "human_trafficking",
}

_SCENARIO_TO_CATEGORY: dict[str, Category] = {
    "synthetic_narcotics_indicator": "narcotics",
    "synthetic_counterfeit_docs": "human_trafficking",
    "synthetic_financial_fraud": "fraud",
}

_FILTER_TO_SCENARIO: dict[str, str] = {
    "narcotics": "synthetic_narcotics_indicator",
    "human_trafficking": "synthetic_counterfeit_docs",
    "trafficking": "synthetic_counterfeit_docs",
}


def category_for_filter(name: str | None) -> Category | None:
    if not name:
        return None
    return _FILTER_TO_CATEGORY.get(name.strip().lower())


def scenario_for_filter(name: str | None) -> str | None:
    if not name:
        return None
    return _FILTER_TO_SCENARIO.get(name.strip().lower())


def category_for_scenario(scenario_id: str) -> Category | None:
    return _CATEGORY_TO_SCENARIO.get(scenario_id)


def sample_keywords(
    category: Category,
    rng: random.Random,
    *,
    count: int = 4,
) -> tuple[str, ...]:
    pool = list(KEYWORDS_BY_CATEGORY.get(category, ()))
    if not pool:
        return ()
    take = min(count, len(pool))
    return tuple(rng.sample(pool, take))


def keywords_for_category(category: Category | None, rng: random.Random) -> tuple[str, ...]:
    if not category:
        return ()
    return sample_keywords(category, rng, count=5)


def enrich_text_with_keyword(
    text: str,
    keywords: tuple[str, ...],
    rng: random.Random,
    *,
    probability: float = 0.5,
) -> str:
    """Weave an OSINT keyword into synthetic message text when appropriate."""
    if not keywords or rng.random() > probability:
        return text
    kw = rng.choice(keywords)
    lowered = text.lower()
    if kw.lower() in lowered:
        return text
    templates = (
        f"{text} Also seeing talk about {kw}.",
        f"{text} ({kw})",
        f"Re: {kw} — {text}",
        f"{text} Anyone know more about {kw}?",
    )
    return rng.choice(templates)


def scan_simulation_text(text: str | None) -> tuple[list[str], list[str]]:
    """Return matched keywords and categories for pipeline stages."""
    result = scan_message_text(text)
    keywords = [hit.keyword for hit in result.hits]
    categories = list(result.categories)
    return keywords, categories
