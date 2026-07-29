"""Tests for persona generation and management."""

from __future__ import annotations

from pathlib import Path

import pytest

from simulator.exceptions import PersonaValidationError
from simulator.generation_config import GenerationConfig
from simulator.personas.manager import PersonaManager
from simulator.personas.validators import validate_unique_personas


class TestPersonaManager:
    def test_generates_unique_ids(self) -> None:
        mgr = PersonaManager(GenerationConfig(user_count=50, group_count=5, random_seed=99))
        personas = mgr.generate()
        assert len(personas) == 50
        validate_unique_personas(personas)

    def test_deterministic_with_same_seed(self) -> None:
        cfg = GenerationConfig(user_count=20, group_count=4, random_seed=12345)
        first = PersonaManager(cfg).generate()
        second = PersonaManager(cfg).generate()
        assert [p.to_dict() for p in first] == [p.to_dict() for p in second]

    def test_search_and_filter(self) -> None:
        mgr = PersonaManager(GenerationConfig(user_count=30, random_seed=7))
        mgr.generate()
        devs = mgr.filter(personality_type="developer")
        assert all(p.personality_type == "developer" for p in devs)
        results = mgr.search("developer")
        assert isinstance(results, list)

    def test_export_json_and_csv(self, tmp_path: Path) -> None:
        mgr = PersonaManager(GenerationConfig(user_count=5, random_seed=1))
        mgr.generate()
        json_path = mgr.export(tmp_path / "users.json", format="json")
        csv_path = mgr.export(tmp_path / "users.csv", format="csv")
        assert json_path.exists()
        assert csv_path.exists()

    def test_load_roundtrip(self, tmp_path: Path) -> None:
        mgr = PersonaManager(GenerationConfig(user_count=3, random_seed=2))
        mgr.generate()
        path = mgr.export(tmp_path / "users.json")
        loaded = PersonaManager(GenerationConfig()).load(path)
        assert len(loaded) == 3

    def test_preset_sizes(self) -> None:
        for size in (10, 100, 500):
            cfg = GenerationConfig.preset(size, random_seed=42)
            personas = PersonaManager(cfg).generate()
            assert len(personas) == size

    def test_validation_rejects_duplicate_username(self) -> None:
        mgr = PersonaManager(GenerationConfig(user_count=2, random_seed=3))
        personas = mgr.generate()
        personas[1].username = personas[0].username
        with pytest.raises(PersonaValidationError):
            validate_unique_personas(personas)
