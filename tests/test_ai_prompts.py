"""Tests for Phase 3 prompt management (Markdown + PromptLoader)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai.prompts import (
    KNOWN_PROMPT_IDS,
    PromptLoader,
    PromptNotFoundError,
    PromptRenderError,
    extract_placeholders,
)


@pytest.fixture
def loader() -> PromptLoader:
    return PromptLoader()


def test_known_prompt_ids_match_shipped_templates(loader: PromptLoader) -> None:
    shipped = set(loader.list_prompt_ids())
    assert set(KNOWN_PROMPT_IDS) <= shipped


@pytest.mark.parametrize("prompt_id", KNOWN_PROMPT_IDS)
def test_each_known_prompt_has_v1(loader: PromptLoader, prompt_id: str) -> None:
    versions = loader.list_versions(prompt_id)
    assert "v1" in versions
    template = loader.load(prompt_id, version="v1")
    assert template.id == prompt_id
    assert template.version == "v1"
    assert "{{" in template.body or template.variables
    # Bodies must not be empty and must come from disk
    assert template.body.strip()
    assert template.path.endswith(f"{prompt_id}\\v1.md") or template.path.endswith(
        f"{prompt_id}/v1.md"
    )


def test_latest_resolves_to_v1_when_only_v1(loader: PromptLoader) -> None:
    assert loader.latest_version("rag_answer") == "v1"
    assert loader.load("rag_answer", version="latest").version == "v1"


def test_render_substitutes_variables(loader: PromptLoader) -> None:
    rendered = loader.render(
        "rag_answer",
        version="v1",
        question="Who is active at night?",
        evidence_chunks="chunk-1: user 42 posted at 03:00",
        citation_instructions="Cite chunk ids.",
    )
    assert "Who is active at night?" in rendered.text
    assert "chunk-1: user 42 posted at 03:00" in rendered.text
    assert "{{" not in rendered.text
    assert rendered.id == "rag_answer"
    assert "question" in rendered.variables_used


def test_render_strict_missing_variable(loader: PromptLoader) -> None:
    with pytest.raises(PromptRenderError):
        loader.render("rag_answer", version="v1", question="only one var")


def test_render_nonstrict_leaves_placeholders(loader: PromptLoader) -> None:
    rendered = loader.render(
        "rag_answer",
        version="v1",
        strict=False,
        question="partial",
    )
    assert "partial" in rendered.text
    assert "{{evidence_chunks}}" in rendered.text


def test_unknown_prompt_raises(loader: PromptLoader) -> None:
    with pytest.raises(PromptNotFoundError):
        loader.load("does_not_exist")


def test_extract_placeholders_order() -> None:
    body = "Hello {{b}} and {{a}} and {{b}} again"
    assert extract_placeholders(body) == ("b", "a")


def test_custom_root_with_versioned_prompt(tmp_path: Path) -> None:
    root = tmp_path
    prompt_dir = root / "templates" / "demo"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "v1.md").write_text(
        "---\nid: demo\nversion: v1\nvariables:\n  - name\n---\n\nHi {{name}}!\n",
        encoding="utf-8",
    )
    (prompt_dir / "v2.md").write_text(
        "---\nid: demo\nversion: v2\n---\n\nHello {{name}} (v2)\n",
        encoding="utf-8",
    )

    custom = PromptLoader(root)
    assert custom.list_versions("demo") == ["v1", "v2"]
    assert custom.latest_version("demo") == "v2"
    assert custom.render("demo", name="Analyst").text.strip() == "Hello Analyst (v2)"
    assert custom.render("demo", version="v1", name="Analyst").text.strip() == "Hi Analyst!"


def test_prompts_are_not_hardcoded_in_loader_source() -> None:
    """Guardrail: loader module must not contain full prompt prose."""
    source = Path(__file__).resolve().parents[1] / "ai" / "prompts" / "loader.py"
    text = source.read_text(encoding="utf-8")
    banned_snippets = [
        "You are a message classification assistant",
        "retrieval-augmented investigation assistant",
        "structured case reports",
    ]
    for snippet in banned_snippets:
        assert snippet not in text
