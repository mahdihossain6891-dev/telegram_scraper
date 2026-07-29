"""Membership engine — assign realistic multi-group memberships."""

from __future__ import annotations

import random
from collections import defaultdict

from simulator.generation_config import GenerationConfig
from simulator.groups.categories import GroupCategory
from simulator.groups.profiles import Group
from simulator.logger import get_prefixed_logger
from simulator.personas.profiles import Persona
from simulator.personas.templates import PersonalityType

_log = get_prefixed_logger("group", name="membership")

_PERSONALITY_GROUP_AFFINITY: dict[PersonalityType, tuple[GroupCategory, ...]] = {
    PersonalityType.STUDENT: (
        GroupCategory.UNIVERSITY,
        GroupCategory.PROGRAMMING,
        GroupCategory.GAMING,
    ),
    PersonalityType.DEVELOPER: (
        GroupCategory.PROGRAMMING,
        GroupCategory.TECHNOLOGY,
        GroupCategory.ARTIFICIAL_INTELLIGENCE,
    ),
    PersonalityType.CYBERSECURITY_RESEARCHER: (
        GroupCategory.CYBERSECURITY,
        GroupCategory.TECHNOLOGY,
        GroupCategory.PROGRAMMING,
    ),
    PersonalityType.CRYPTO_TRADER: (
        GroupCategory.CRYPTO,
        GroupCategory.FINANCE,
        GroupCategory.NEWS,
    ),
    PersonalityType.BUSINESS_OWNER: (
        GroupCategory.BUSINESS,
        GroupCategory.FINANCE,
        GroupCategory.MARKETPLACE,
    ),
    PersonalityType.TEACHER: (
        GroupCategory.UNIVERSITY,
        GroupCategory.BOOKS,
        GroupCategory.SCIENCE,
    ),
    PersonalityType.JOURNALIST: (
        GroupCategory.NEWS,
        GroupCategory.BUSINESS,
        GroupCategory.GENERAL_DISCUSSION,
    ),
    PersonalityType.CONTENT_CREATOR: (
        GroupCategory.PHOTOGRAPHY,
        GroupCategory.MUSIC,
        GroupCategory.MOVIES,
    ),
    PersonalityType.MARKETPLACE_SELLER: (
        GroupCategory.MARKETPLACE,
        GroupCategory.BUSINESS,
        GroupCategory.GENERAL_DISCUSSION,
    ),
    PersonalityType.MODERATOR: (
        GroupCategory.GENERAL_DISCUSSION,
        GroupCategory.TECHNOLOGY,
    ),
    PersonalityType.NEWS_CHANNEL: (GroupCategory.NEWS,),
    PersonalityType.CASUAL_USER: (
        GroupCategory.FOOD,
        GroupCategory.TRAVEL,
        GroupCategory.MOVIES,
        GroupCategory.GAMING,
    ),
    PersonalityType.BOT: (GroupCategory.TECHNOLOGY,),
    PersonalityType.SPAM_BOT: (
        GroupCategory.MARKETPLACE,
        GroupCategory.CRYPTO,
    ),
}


class MembershipEngine:
    """Assigns users to multiple groups based on interests and personality."""

    def __init__(self, config: GenerationConfig) -> None:
        self._config = config
        self._rng = random.Random((config.random_seed or 0) + 20_000)

    def assign(
        self,
        personas: list[Persona],
        groups: list[Group],
    ) -> dict[str, list[str]]:
        """Return persona_id -> list[group_id] and mutate group membership fields."""
        if not personas or not groups:
            return {}

        groups_by_category: dict[str, list[Group]] = defaultdict(list)
        groups_by_language: dict[str, list[Group]] = defaultdict(list)
        for group in groups:
            groups_by_category[group.category].append(group)
            groups_by_language[group.language].append(group)

        persona_memberships: dict[str, list[str]] = {}

        for persona in personas:
            if persona.bot and persona.personality_type == PersonalityType.SPAM_BOT.value:
                target_count = self._rng.randint(1, 3)
            else:
                target_count = self._rng.randint(
                    self._config.min_groups_per_user,
                    min(self._config.max_groups_per_user, len(groups)),
                )
            target_count = min(target_count, len(groups))

            chosen: list[Group] = []
            personality = PersonalityType(persona.personality_type)
            affinities = _PERSONALITY_GROUP_AFFINITY.get(personality, ())

            for category in affinities:
                pool = [
                    g
                    for g in groups_by_category.get(category.value, [])
                    if g.language == persona.language or self._rng.random() < 0.3
                ]
                if pool and len(chosen) < target_count:
                    candidate = self._rng.choice(pool)
                    if candidate not in chosen:
                        chosen.append(candidate)

            while len(chosen) < target_count:
                available = [g for g in groups if g not in chosen]
                if not available:
                    break
                lang_matches = [g for g in available if g.language == persona.language]
                pool = lang_matches if lang_matches else available
                chosen.append(self._rng.choice(pool))

            group_ids = [str(g.id) for g in chosen]
            persona_memberships[str(persona.id)] = group_ids
            persona.group_memberships = group_ids
            persona.preferred_groups = group_ids

        self._assign_group_rosters(personas, groups, persona_memberships)
        return persona_memberships

    def _assign_group_rosters(
        self,
        personas: list[Persona],
        groups: list[Group],
        memberships: dict[str, list[str]],
    ) -> None:
        persona_by_id = {str(p.id): p for p in personas}
        group_members: dict[str, list[str]] = defaultdict(list)

        for persona_id, group_ids in memberships.items():
            for gid in group_ids:
                group_members[gid].append(persona_id)

        for group in groups:
            gid = str(group.id)
            members = group_members.get(gid, [])
            if not members:
                fallback = self._rng.choice(personas)
                members = [str(fallback.id)]
                memberships[str(fallback.id)].append(gid)
                fallback.group_memberships.append(gid)
                fallback.preferred_groups.append(gid)

            group.member_ids = members
            group.current_members = len(members)
            owner_id = self._pick_owner(members, persona_by_id)
            group.owner_id = owner_id
            group.moderator_ids = self._pick_moderators(members, owner_id)
            _log.info(
                "Group %s: %d members, owner=%s",
                group.name,
                group.current_members,
                owner_id[:8],
            )

    def _pick_owner(
        self, member_ids: list[str], persona_by_id: dict[str, Persona]
    ) -> str:
        candidates = [
            mid
            for mid in member_ids
            if persona_by_id[mid].personality_type
            in {
                PersonalityType.MODERATOR.value,
                PersonalityType.BUSINESS_OWNER.value,
                PersonalityType.CONTENT_CREATOR.value,
                PersonalityType.DEVELOPER.value,
            }
        ]
        return self._rng.choice(candidates or member_ids)

    def _pick_moderators(self, member_ids: list[str], owner_id: str) -> list[str]:
        others = [mid for mid in member_ids if mid != owner_id]
        if not others:
            return []
        count = min(len(others), self._rng.randint(0, 3))
        return self._rng.sample(others, k=count) if count else []
