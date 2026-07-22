"""Entity resolution must never return duplicate Telegram identities."""

from __future__ import annotations

from ai.investigation.entity_resolution import ResolvedEntity, dedupe_entities


def _user(
    entity_id: int | str,
    *,
    display_name: str = "Ratul",
    username: str | None = None,
    score: float = 1.0,
    reason: str = "exact_name",
) -> ResolvedEntity:
    return ResolvedEntity(
        entity_type="user",
        entity_id=entity_id,
        display_name=display_name,
        username=username,
        score=score,
        match_reason=reason,
    )


def test_dedupe_collapses_same_user_id_from_multiple_collections() -> None:
    items = [
        _user(581294712, username="@ratul", score=0.9, reason="fuzzy_name"),
        _user(581294712, username="@ratul", score=1.0, reason="exact_name"),
        _user("581294712", display_name="Ratul", score=0.95),
    ]
    out = dedupe_entities(items)
    assert len(out) == 1
    assert out[0].entity_id == 581294712
    assert out[0].score == 1.0
    assert out[0].username == "@ratul"


def test_dedupe_keeps_distinct_telegram_ids() -> None:
    items = [
        _user(1, display_name="Ratul Ahmed", username="@ratul_a"),
        _user(2, display_name="Ratul Islam", username="@ratul_i"),
        _user(3, display_name="Ratul Khan", username="@ratul_k"),
    ]
    out = dedupe_entities(items)
    assert len(out) == 3
    assert {e.entity_id for e in out} == {1, 2, 3}


def test_dedupe_merges_metadata_from_weaker_duplicate() -> None:
    items = [
        _user(99, display_name="Ratul", username=None, score=1.0),
        _user(99, display_name="Ratul", username="@ratul99", score=0.8),
    ]
    out = dedupe_entities(items)
    assert len(out) == 1
    assert out[0].username == "@ratul99"


def test_dedupe_collapses_chat_kind_aliases_for_same_id() -> None:
    a = ResolvedEntity(
        entity_type="group",
        entity_id=-1001,
        display_name="Ops Chat",
        score=0.9,
        match_reason="fuzzy_title",
    )
    b = ResolvedEntity(
        entity_type="channel",
        entity_id=-1001,
        display_name="Ops Chat",
        username="@ops",
        score=1.0,
        match_reason="exact_title",
    )
    out = dedupe_entities([a, b])
    assert len(out) == 1
    assert out[0].entity_id == -1001
    assert out[0].username == "@ops"
