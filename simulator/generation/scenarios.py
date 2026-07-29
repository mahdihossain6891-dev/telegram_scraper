"""Parse and format console simulation threat scenarios (multi-select)."""

from __future__ import annotations

VALID_CONSOLE_SCENARIOS = frozenset({"narcotics", "firearms", "human_trafficking"})

_SCENARIO_FOCUS: dict[str, str] = {
    "narcotics": "narcotics trafficking and drug dealing",
    "firearms": "illegal firearms trafficking and ghost guns",
    "human_trafficking": "human trafficking and smuggling rings",
}


def parse_console_scenarios(raw: str | None) -> list[str]:
    """Normalize a comma/semicolon-separated scenario string."""
    if not raw:
        return ["narcotics"]
    parts: list[str] = []
    for chunk in raw.replace(";", ",").split(","):
        token = chunk.strip().lower()
        if token and token in VALID_CONSOLE_SCENARIOS and token not in parts:
            parts.append(token)
    return parts or ["narcotics"]


def format_console_scenarios(scenarios: list[str] | None) -> str:
    """Serialize scenario ids for mode state / API payloads."""
    normalized = parse_console_scenarios(",".join(scenarios or []))
    return ",".join(normalized)


def scenario_focus_phrase(scenarios: list[str] | None) -> str:
    """Human-readable threat focus for AI prompts."""
    selected = parse_console_scenarios(",".join(scenarios or []))
    phrases = [_SCENARIO_FOCUS.get(item, item.replace("_", " ")) for item in selected]
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} and {phrases[1]}"
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"
