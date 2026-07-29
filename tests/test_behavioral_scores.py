"""Behavioral analytics scoring — live and simulation corpora."""

from __future__ import annotations

from datetime import datetime, timedelta

from behavioral_analytics import (
    _compute_user_profile,
    ensure_behavioral_analytics,
    rebuild_behavioral_analytics,
)


def test_compute_profile_produces_nonzero_score_for_sparse_activity() -> None:
    now = datetime.utcnow()
    messages = [
        {
            "chat_id": -1001,
            "timestamp": now - timedelta(hours=i * 5),
            "text": f"hello {i}",
            "media_type": "MessageMediaPhoto" if i % 2 == 0 else None,
            "forward_from_chat_id": -2000 if i % 3 == 0 else None,
        }
        for i in range(8)
    ]
    messages[0]["chat_id"] = -1002
    messages[1]["chat_id"] = -1003
    chats = {
        -1001: {"chat_type": "group"},
        -1002: {"chat_type": "channel"},
        -1003: {"chat_type": "private chat"},
    }
    profile = _compute_user_profile(
        42,
        {"username": "sim_user", "first_name": "Sim", "last_name": "User"},
        messages,
        chats,
        None,
    )
    assert int(profile["behavior_score"]) > 0
    assert profile["behavior_status"] in {"Normal", "Unusual", "Suspicious", "High Risk"}
    assert profile["message_count"] == 8


def test_ensure_rebuilds_when_profiles_missing(db_settings) -> None:
    from config import load_settings
    from database import database_available, get_session, init_db

    settings = load_settings()
    if not database_available(settings):
        return

    init_db(settings)
    with get_session(settings) as session:
        # Use whatever messages exist; ensure should not crash and should score when possible.
        result = ensure_behavioral_analytics(session)
        overview_count = session.db["behavioral_analytics"].count_documents({})
        msg_count = session.messages.count_documents({})
        if msg_count > 0:
            assert overview_count > 0
            if result is not None:
                assert result["profiles_written"] >= 1
            scores = [
                int(doc.get("behavior_score") or 0)
                for doc in session.db["behavioral_analytics"].find().limit(20)
            ]
            assert any(score > 0 for score in scores)


def test_rebuild_writes_scores(db_settings) -> None:
    from config import load_settings
    from database import database_available, get_session, init_db

    settings = load_settings()
    if not database_available(settings):
        return

    init_db(settings)
    with get_session(settings) as session:
        if session.messages.count_documents({}) == 0:
            return
        stats = rebuild_behavioral_analytics(session)
        assert stats["profiles_written"] >= 1
        doc = session.db["behavioral_analytics"].find_one()
        assert doc is not None
        assert "behavior_score" in doc
