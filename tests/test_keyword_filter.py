"""Tests for keyword filter module."""

from __future__ import annotations

from keyword_filter import scan_message_text


class TestScanMessageText:
    """Tests for category keyword detection."""

    def test_detects_narcotics_keyword(self) -> None:
        result = scan_message_text("Suspected cocaine shipment discussed in channel")
        assert result.matched is True
        assert "narcotics" in result.categories
        assert any(hit.keyword == "cocaine" for hit in result.hits)

    def test_detects_human_trafficking_phrase(self) -> None:
        result = scan_message_text("Report on human trafficking ring activity")
        assert result.matched is True
        assert "human_trafficking" in result.categories

    def test_detects_firearms_keyword(self) -> None:
        result = scan_message_text("Discussion about ghost gun assembly")
        assert result.matched is True
        assert "firearms" in result.categories

    def test_ignores_unrelated_text(self) -> None:
        result = scan_message_text("Weather update and local sports news")
        assert result.matched is False
        assert result.hits == ()

    def test_empty_text_not_matched(self) -> None:
        assert scan_message_text("").matched is False
        assert scan_message_text(None).matched is False

    def test_case_insensitive_match(self) -> None:
        result = scan_message_text("HEROIN distribution mentioned")
        assert result.matched is True

    def test_word_boundary_avoids_partial_match(self) -> None:
        result = scan_message_text("methodology review completed")
        assert result.matched is False
