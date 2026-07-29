"""Tests for TIE process path resolution helpers."""

from __future__ import annotations

from pathlib import Path

from tie_process import resolve_tie_engine_command, resolve_tie_engine_cwd


def test_resolve_tie_engine_cwd_from_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = home / "threat translation engine"
    (project / "app").mkdir(parents=True)
    (project / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("TIE_ENGINE_CWD", raising=False)
    # Path.home() on Windows uses USERPROFILE
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    found = resolve_tie_engine_cwd()
    assert found == project.resolve()


def test_resolve_tie_engine_cwd_from_env(tmp_path, monkeypatch):
    project = tmp_path / "custom-tie"
    (project / "app").mkdir(parents=True)
    (project / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    monkeypatch.setenv("TIE_ENGINE_CWD", str(project))
    found = resolve_tie_engine_cwd()
    assert found == project.resolve()


def test_resolve_tie_engine_command_default(tmp_path):
    project = tmp_path / "tie"
    (project / ".venv" / "Scripts").mkdir(parents=True)
    py = project / ".venv" / "Scripts" / "python.exe"
    py.write_text("", encoding="utf-8")
    cmd = resolve_tie_engine_command(project)
    assert cmd[0] == str(py)
    assert "uvicorn" in cmd
    assert "app.main:app" in cmd
