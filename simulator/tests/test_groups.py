"""Tests for group generation, membership, and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from simulator.exceptions import GroupValidationError
from simulator.generation_config import GenerationConfig
from simulator.groups.manager import GroupManager
from simulator.groups.validators import validate_membership_integrity
from simulator.personas.manager import PersonaManager
from simulator.world_generator import WorldGenerator


class TestGroupManager:
    def test_generates_unique_groups(self) -> None:
        mgr = GroupManager(GenerationConfig(user_count=20, group_count=8, random_seed=11))
        groups = mgr.generate()
        assert len(groups) == 8
        names = {g.name for g in groups}
        assert len(names) == 8

    def test_deterministic_groups(self) -> None:
        cfg = GenerationConfig(user_count=10, group_count=5, random_seed=777)
        a = GroupManager(cfg).generate()
        b = GroupManager(cfg).generate()
        assert [g.to_dict() for g in a] == [g.to_dict() for g in b]

    def test_membership_integrity(self) -> None:
        cfg = GenerationConfig(user_count=40, group_count=6, random_seed=5)
        persona_mgr = PersonaManager(cfg)
        group_mgr = GroupManager(cfg)
        personas = persona_mgr.generate()
        groups = group_mgr.generate()
        group_mgr.assign_members(personas)
        known = {str(p.id) for p in personas}
        validate_membership_integrity(groups, known_persona_ids=known)
        assert all(g.current_members == len(g.member_ids) for g in groups)
        assert all(
            len(p.group_memberships) >= cfg.min_groups_per_user
            for p in personas
            if p.personality_type != "spam_bot"
        )

    def test_export_groups(self, tmp_path: Path) -> None:
        mgr = GroupManager(GenerationConfig(user_count=5, group_count=3, random_seed=4))
        mgr.generate()
        path = mgr.export(tmp_path / "groups.json")
        assert path.exists()

    def test_world_generator(self) -> None:
        world = WorldGenerator(
            GenerationConfig(user_count=100, group_count=10, random_seed=99)
        ).generate()
        assert world.statistics.total_users == 100
        assert world.statistics.total_groups == 10
        assert world.statistics.total_memberships > 0

    def test_statistics_fields(self) -> None:
        world = WorldGenerator(
            GenerationConfig(user_count=50, group_count=5, random_seed=21)
        ).generate()
        data = world.statistics.to_dict()
        assert "language_distribution" in data
        assert "risk_distribution" in data
        assert "most_common_interests" in data
        assert data["total_users"] == 50

    def test_invalid_membership_raises(self) -> None:
        cfg = GenerationConfig(user_count=5, group_count=2, random_seed=1)
        persona_mgr = PersonaManager(cfg)
        group_mgr = GroupManager(cfg)
        personas = persona_mgr.generate()
        groups = group_mgr.generate()
        group_mgr.assign_members(personas)
        groups[0].owner_id = "not-a-real-id"
        with pytest.raises(GroupValidationError):
            validate_membership_integrity(groups, known_persona_ids={str(p.id) for p in personas})
