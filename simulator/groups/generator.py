"""Fictional group generation engine."""

from __future__ import annotations

import random
from datetime import date, timedelta
from uuid import UUID, uuid5

from simulator.constants import SIM_TELEGRAM_CHAT_ID_BASE
from simulator.generation_config import GenerationConfig
from simulator.groups.categories import ALL_CATEGORIES, GROUP_CATEGORY_TOPICS, GroupCategory
from simulator.groups.profiles import Group
from simulator.logger import get_prefixed_logger
from simulator.personas.dataset_loader import supported_languages

_log = get_prefixed_logger("group", name="generator")

_NS_GROUP = UUID("b4c6d8e0-2222-4333-8444-555566667777")

_PRIVACY_LEVELS = ("public", "private", "restricted")
_ACTIVITY_LEVELS = ("low", "moderate", "high", "very_high")


class GroupGenerator:
    """Generates deterministic fictional Telegram groups."""

    def __init__(self, config: GenerationConfig) -> None:
        self._config = config
        self._rng = random.Random(
            (config.random_seed or 0) + 10_000
        )  # offset seed from personas

    def generate(self, count: int) -> list[Group]:
        groups: list[Group] = []
        for index in range(count):
            group = self.generate_one(index)
            groups.append(group)
            _log.info("Created Group %s", group.name)
        return groups

    def generate_one(self, index: int) -> Group:
        category = ALL_CATEGORIES[index % len(ALL_CATEGORIES)]
        language = self._pick_language()
        region = self._pick_region(language)
        name = self._group_name(category, language, index)
        tags = list(GROUP_CATEGORY_TOPICS.get(category, (category.value,)))
        topic_tags = self._rng.sample(tags, k=min(len(tags), self._rng.randint(2, len(tags))))

        max_members = self._rng.choice([200, 500, 1000, 5000, 10000, 50000])
        activity = self._rng.choice(_ACTIVITY_LEVELS)
        avg_daily = {
            "low": (5, 40),
            "moderate": (40, 200),
            "high": (200, 800),
            "very_high": (800, 3000),
        }[activity]

        group_id = uuid5(_NS_GROUP, f"{self._config.random_seed}:group:{index}")

        return Group(
            id=group_id,
            telegram_chat_id=SIM_TELEGRAM_CHAT_ID_BASE - index,
            name=name,
            description=self._description(category, region),
            category=category.value,
            language=language,
            region=region,
            privacy=self._rng.choice(_PRIVACY_LEVELS),
            maximum_members=max_members,
            current_members=0,
            creation_date=date.today() - timedelta(days=30 + (index * 23) % 1200),
            owner_id="",
            moderator_ids=[],
            activity_level=activity,
            average_daily_messages=round(
                self._rng.uniform(avg_daily[0], avg_daily[1]), 1
            ),
            topic_tags=topic_tags,
            member_ids=[],
        )

    def _pick_language(self) -> str:
        dist = self._config.language_distribution
        keys = list(dist.keys())
        weights = [dist[k] for k in keys]
        return self._rng.choices(keys, weights=weights, k=1)[0]

    def _pick_region(self, language: str) -> str:
        for entry in supported_languages():
            if entry["code"] == language:
                return self._rng.choice(entry["countries"])
        return "Global"

    def _group_name(self, category: GroupCategory, language: str, index: int) -> str:
        prefixes = {
            GroupCategory.PROGRAMMING: ("Dev", "Code", "Hack"),
            GroupCategory.CRYPTO: ("Crypto", "Coin", "DeFi"),
            GroupCategory.GAMING: ("Game", "GG", "Play"),
            GroupCategory.FOOD: ("Foodie", "Taste", "Kitchen"),
        }
        prefix_pool = prefixes.get(category, ("TG", "Chat", "Hub"))
        prefix = self._rng.choice(prefix_pool)
        suffix = category.value.replace("_", " ").title().replace(" ", "")
        lang_tag = language[:2].upper()
        return f"{prefix} {suffix} {lang_tag} {index + 1}"

    def _description(self, category: GroupCategory, region: str) -> str:
        return (
            f"Fictional {category.value.replace('_', ' ')} community for {region}. "
            "Simulation-only group — not a real Telegram channel."
        )
