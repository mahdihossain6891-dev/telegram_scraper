"""World generation statistics for personas and groups."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from simulator.groups.profiles import Group
from simulator.personas.profiles import Persona


@dataclass(frozen=True, slots=True)
class WorldStatistics:
    """Aggregated metrics for a generated simulation world."""

    total_users: int
    total_groups: int
    language_distribution: dict[str, int]
    activity_distribution: dict[str, int]
    risk_distribution: dict[str, int]
    profession_distribution: dict[str, int]
    average_group_size: float
    most_common_interests: list[tuple[str, int]]
    bot_count: int
    verified_count: int
    total_memberships: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_users": self.total_users,
            "total_groups": self.total_groups,
            "language_distribution": dict(self.language_distribution),
            "activity_distribution": dict(self.activity_distribution),
            "risk_distribution": dict(self.risk_distribution),
            "profession_distribution": dict(self.profession_distribution),
            "average_group_size": self.average_group_size,
            "most_common_interests": [
                {"interest": name, "count": count}
                for name, count in self.most_common_interests
            ],
            "bot_count": self.bot_count,
            "verified_count": self.verified_count,
            "total_memberships": self.total_memberships,
        }


def compute_world_statistics(
    personas: list[Persona],
    groups: list[Group],
) -> WorldStatistics:
    languages = Counter(p.language for p in personas)
    activities = Counter(p.activity_level for p in personas)
    risks = Counter(p.risk_profile for p in personas)
    professions = Counter(p.personality_type for p in personas)
    interests: Counter[str] = Counter()
    for persona in personas:
        interests.update(persona.interests)

    memberships = sum(len(p.group_memberships) for p in personas)
    avg_size = (
        sum(g.current_members for g in groups) / len(groups) if groups else 0.0
    )

    return WorldStatistics(
        total_users=len(personas),
        total_groups=len(groups),
        language_distribution=dict(languages),
        activity_distribution=dict(activities),
        risk_distribution=dict(risks),
        profession_distribution=dict(professions),
        average_group_size=round(avg_size, 2),
        most_common_interests=interests.most_common(10),
        bot_count=sum(1 for p in personas if p.bot),
        verified_count=sum(1 for p in personas if p.verified),
        total_memberships=memberships,
    )
