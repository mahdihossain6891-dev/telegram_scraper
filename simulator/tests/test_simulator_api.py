"""Tests for Threat Simulation API facade."""

from __future__ import annotations

from simulator.api.facade import SimulationConsoleFacade


def test_health_isolated() -> None:
    facade = SimulationConsoleFacade()
    health = facade.health()
    assert health["ok"] is True
    assert health["environment"] == "simulation"
    assert health["isolated"] is True


def test_create_session_and_overview() -> None:
    facade = SimulationConsoleFacade()
    summary = facade.create_session(name="test-ui")
    assert summary["session_id"]
    assert summary["environment"] == "simulation"
    overview = facade.overview(summary["session_id"])
    assert overview["environment"] == "simulation"
    assert overview["users"] >= 2


def test_tick_ingests_messages() -> None:
    facade = SimulationConsoleFacade()
    summary = facade.create_session(name="tick-test", config={"users": 30, "groups": 4, "max_ticks": 3})
    facade.tick(summary["session_id"])
    activity = facade.activity(summary["session_id"])
    assert isinstance(activity, list)


def test_scenarios_list() -> None:
    facade = SimulationConsoleFacade()
    scenarios = facade.scenarios()
    assert len(scenarios) >= 5


def test_benchmark_empty_session() -> None:
    facade = SimulationConsoleFacade()
    summary = facade.create_session()
    bench = facade.benchmark(summary["session_id"])
    assert "precision" in bench
    assert "recall" in bench


def test_config_validation() -> None:
    facade = SimulationConsoleFacade()
    result = facade.update_config(None, {"users": 0})
    assert result["ok"] is False
