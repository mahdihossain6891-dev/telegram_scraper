"""Participant and scenario selection logic."""

from __future__ import annotations

import random

from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona
from simulator.scenario.labels import ScenarioCategory
from simulator.scenario.templates import ScenarioDefinition


_CATEGORY_GROUP_MAP: dict[str, tuple[ScenarioCategory, ...]] = {
    "programming": (ScenarioCategory.PROGRAMMING, ScenarioCategory.TECHNOLOGY),
    "technology": (ScenarioCategory.TECHNOLOGY, ScenarioCategory.PROGRAMMING),
    "artificial_intelligence": (ScenarioCategory.ARTIFICIAL_INTELLIGENCE, ScenarioCategory.TECHNOLOGY),
    "cybersecurity": (ScenarioCategory.CYBERSECURITY, ScenarioCategory.TECHNOLOGY),
    "gaming": (ScenarioCategory.GAMING,),
    "marketplace": (ScenarioCategory.MARKETPLACE,),
    "news": (ScenarioCategory.NEWS,),
    "university": (ScenarioCategory.UNIVERSITY,),
    "finance": (ScenarioCategory.FINANCE,),
    "crypto": (ScenarioCategory.FINANCE, ScenarioCategory.MARKETPLACE),
}


def scenario_matches_group(scenario: ScenarioDefinition, group: Group) -> bool:
    preferred = _CATEGORY_GROUP_MAP.get(group.category, ())
    if preferred and scenario.category in preferred:
        return True
    if scenario.category == ScenarioCategory.GENERAL_CHAT:
        return True
    return group.category in {tag.lower().replace(" ", "_") for tag in scenario.typical_topics}


def score_persona_for_scenario(persona: Persona, scenario: ScenarioDefinition, group: Group) -> float:
    score = 0.5
    if scenario.preferred_personality_types and persona.personality_type in scenario.preferred_personality_types:
        score += 2.0
    overlap = set(persona.interests) & set(scenario.typical_topics)
    score += len(overlap) * 0.8
    topic_overlap = set(persona.favorite_topics) & set(scenario.vocabulary.topic_keywords)
    score += len(topic_overlap) * 0.5
    if persona.language in scenario.languages:
        score += 0.4
    if str(group.id) in persona.group_memberships:
        score += 0.3
    if scenario.category == ScenarioCategory.SYNTHETIC_THREAT_EVALUATION:
        if persona.personality_type in {"spam_bot", "marketplace_seller", "crypto_trader"}:
            score += 1.5
        if persona.risk_profile in {"high", "critical", "elevated"}:
            score += 0.5
    return score


def select_participants(
    scenario: ScenarioDefinition,
    group: Group,
    candidates: list[Persona],
    rng: random.Random,
) -> list[Persona]:
    """Intelligently choose participants for a scenario."""
    member_ids = set(group.member_ids)
    pool = [persona for persona in candidates if str(persona.id) in member_ids]
    if not pool:
        pool = list(candidates)
    low, high = scenario.expected_participants
    cap_high = min(high, len(pool))
    cap_low = min(low, cap_high)
    if cap_low < 1:
        return []
    if cap_high < cap_low:
        cap_high = cap_low
    target = rng.randint(cap_low, cap_high) if cap_high > cap_low else cap_low
    if target < 2 and len(pool) >= 2:
        target = 2
    if target < 1:
        return []

    scored = sorted(
        ((score_persona_for_scenario(persona, scenario, group), persona) for persona in pool),
        key=lambda item: (item[0], str(item[1].id)),
        reverse=True,
    )
    top_pool = [persona for _, persona in scored[: max(target * 2, target)]]
    if len(top_pool) <= target:
        return top_pool
    weights = [max(0.1, score_persona_for_scenario(persona, scenario, group)) for persona in top_pool]
    return rng.choices(top_pool, weights=weights, k=target)
