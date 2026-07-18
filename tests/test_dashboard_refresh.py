"""Tests for dashboard auto-refresh helpers."""

from __future__ import annotations

from dashboard import (
    AUTO_REFRESH_OPTIONS,
    AUTO_REFRESH_QUERY_KEY,
    build_auto_refresh_reload_script,
    choice_index_for_refresh_seconds,
    parse_refresh_query_param,
)


def test_auto_refresh_options_include_off_and_intervals() -> None:
    assert AUTO_REFRESH_OPTIONS["Off"] is None
    assert AUTO_REFRESH_OPTIONS["Every 30 seconds"] == 30
    assert AUTO_REFRESH_OPTIONS["Every 1 minute"] == 60


def test_parse_refresh_query_param_accepts_valid_intervals() -> None:
    assert parse_refresh_query_param("30") == 30
    assert parse_refresh_query_param("60") == 60
    assert parse_refresh_query_param("300") == 300


def test_parse_refresh_query_param_rejects_invalid_values() -> None:
    assert parse_refresh_query_param(None) is None
    assert parse_refresh_query_param("") is None
    assert parse_refresh_query_param("45") is None
    assert parse_refresh_query_param("abc") is None


def test_choice_index_for_refresh_seconds() -> None:
    assert choice_index_for_refresh_seconds(None) == 0
    assert choice_index_for_refresh_seconds(30) == 1
    assert choice_index_for_refresh_seconds(60) == 2
    assert choice_index_for_refresh_seconds(300) == 3
    assert choice_index_for_refresh_seconds(999) == 0


def test_build_auto_refresh_reload_script_preserves_query_param() -> None:
    script = build_auto_refresh_reload_script(30)
    assert AUTO_REFRESH_QUERY_KEY in script
    assert 'url.searchParams.set("refresh", "30")' in script
    assert "30000" in script
