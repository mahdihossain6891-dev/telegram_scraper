"""Load static datasets for persona and group generation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"


def datasets_dir() -> Path:
    return _DATASETS_DIR


@lru_cache(maxsize=1)
def load_json(name: str) -> Any:
    path = _DATASETS_DIR / name
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def first_names(language: str) -> list[str]:
    data = load_json("first_names.json")
    return list(data.get(language, data.get("english", [])))


def last_names(language: str) -> list[str]:
    data = load_json("last_names.json")
    return list(data.get(language, data.get("english", [])))


def username_parts() -> tuple[list[str], list[str]]:
    data = load_json("usernames.json")
    return list(data["roots"]), list(data["suffixes"])


def cities_by_country() -> dict[str, list[dict[str, str]]]:
    return dict(load_json("cities.json"))


def interest_topics() -> list[str]:
    return list(load_json("interests.json")["topics"])


def interests_by_personality() -> dict[str, list[str]]:
    return dict(load_json("interests.json")["by_personality"])


def supported_languages() -> list[dict[str, Any]]:
    return list(load_json("languages.json")["supported"])


def emoji_sets() -> dict[str, list[str]]:
    return dict(load_json("emojis.json"))
