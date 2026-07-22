"""Phase 7 — investigation engine scenarios (keyword, suspicious, false positives)."""

from __future__ import annotations

from ai.investigation.context import InvestigationContext, ToolExecution
from ai.investigation.engine import run_investigation_engine
from ai.investigation.threat_analysis import run_threat_analysis


def _ctx_with_evidence(
    *,
    evidence_snippet: str,
    keywords: list[str],
    risk_score: int = 40,
    behavior_score: int = 30,
    edges: int = 1,
) -> InvestigationContext:
    ctx = InvestigationContext(question="Investigate user", session_id="phase7")
    ctx.subject = {"user_id": 99001, "username": "target_user", "display_name": "Target User"}
    ctx.tool_results = [
        ToolExecution(
            name="risk",
            ok=True,
            summary=f"Risk score={risk_score}",
            data={"risk_score": risk_score, "risk_level": "Medium", "factors": keywords[:3]},
        ),
        ToolExecution(
            name="behavior",
            ok=True,
            summary=f"Behavior score={behavior_score}",
            data={
                "behavior_score": behavior_score,
                "behavior_status": "Unusual" if behavior_score >= 60 else "Normal",
                "metrics": {"message_count": 12},
            },
        ),
        ToolExecution(
            name="search",
            ok=True,
            summary="Retrieved 1",
            data={
                "evidence": [
                    {
                        "label": "[E1]",
                        "snippet": evidence_snippet,
                        "timestamp": "2024-06-01T12:00:00Z",
                        "keywords": keywords,
                        "group_name": "Test Group",
                    }
                ],
            },
        ),
        ToolExecution(
            name="relationship",
            ok=True,
            summary=f"{edges} edge(s)",
            data={
                "edges": [
                    {
                        "chat_id": 100,
                        "title": f"Group {i}",
                        "type": "shared_chat",
                        "message_count": 5,
                        "suspicious_count": 1,
                    }
                    for i in range(edges)
                ]
            },
        ),
    ]
    return run_investigation_engine(ctx)


def test_keyword_only_detection_lowers_operational_risk() -> None:
    """Keyword hits without transaction language should not imply malicious intent."""
    ctx = _ctx_with_evidence(
        evidence_snippet=(
            "Narcotics keyword dictionary for monitoring: methamphetamine, heroin — reference only."
        ),
        keywords=["methamphetamine", "heroin"],
        risk_score=55,
        behavior_score=15,
    )
    report = run_threat_analysis(ctx)
    row = report.evidence_analysis[0]

    assert row["intent_classification"] in {"Unknown", "Educational/reference"}
    assert row["context_analysis"]["keyword_match_only"] is True
    assert row["context_analysis"]["evidence_of_intent"] is False
    assert report.activity_assessment in {"informational", "unknown", "suspicious"}
    assert report.risk_scores["risk_band"] in {"LOW", "MEDIUM"}


def test_real_suspicious_behavior_elevates_risk() -> None:
    """Operational sales language plus elevated behavior should raise threat scores."""
    ctx = _ctx_with_evidence(
        evidence_snippet="Meth for sale — DM me for price and delivery today.",
        keywords=["meth"],
        risk_score=72,
        behavior_score=78,
        edges=4,
    )
    report = run_threat_analysis(ctx)
    row = report.evidence_analysis[0]

    assert row["intent_classification"] == "Selling"
    assert row["context_analysis"]["evidence_of_intent"] is True
    assert report.false_positive_assessment.get("likely_false_positive") is False
    assert report.activity_assessment in {"malicious", "suspicious"}
    assert report.risk_scores["final_score"] >= 50
    assert report.risk_scores["risk_band"] in {"MEDIUM", "HIGH", "CRITICAL"}
    assert report.threat_categories


def test_false_positive_reference_content() -> None:
    """Reference/monitoring content with low behavior should be flagged as likely FP."""
    ctx = _ctx_with_evidence(
        evidence_snippet=(
            "Training material: keyword list includes methamphetamine for SOC monitoring tests."
        ),
        keywords=["methamphetamine"],
        risk_score=70,
        behavior_score=10,
        edges=1,
    )
    report = run_threat_analysis(ctx)

    assert report.false_positive_assessment.get("likely_false_positive") is True
    assert report.false_positive_assessment.get("categories", {}).get("keyword_list_only") is True
    assert report.activity_assessment == "informational"
    assert report.risk_scores["final_score"] <= 55


def test_engine_attaches_structured_threat_report() -> None:
    ctx = _ctx_with_evidence(
        evidence_snippet="Cocaine wholesale supply available — bulk orders only.",
        keywords=["cocaine"],
        risk_score=80,
        behavior_score=70,
        edges=3,
    )
    assert ctx.threat_report
    assert ctx.threat_report.get("executive_summary")
    assert ctx.threat_report.get("risk_scores", {}).get("final_score") is not None
    assert any(f.key == "threat_intelligence" for f in ctx.findings)


# --- Simulation mode, DB isolation, API smoke (imports deferred per test) ---


def test_simulation_mode_lifecycle_and_restore() -> None:
    from data_providers.router import end_simulation_mode, get_data_provider, start_simulation_mode
    from data_providers.simulation import SimulationDataProvider
    from data_providers.state import reset_to_live

    reset_to_live()
    assert get_data_provider().mode == "live"

    state = start_simulation_mode(scenario="narcotics", auto_start=False)
    assert state.simulation_active is True
    provider = get_data_provider()
    assert isinstance(provider, SimulationDataProvider)
    assert provider.get_investigations()["mode"] == "simulation"

    ended = end_simulation_mode()
    assert ended.mode == "live"
    assert get_data_provider().mode == "live"


def test_simulation_export_populates_analytics_fields() -> None:
    from data_providers.router import end_simulation_mode, get_data_provider, start_simulation_mode
    from data_providers.state import reset_to_live
    from scrape_jobs.simulation_runner import run_simulation_scrape
    from scrape_jobs.store import ScrapeJobStore
    from config import load_settings

    reset_to_live()
    start_simulation_mode(scenario="narcotics", auto_start=False)
    store = ScrapeJobStore()
    store.try_begin()
    run_simulation_scrape(load_settings(), store, scenario="narcotics", limit=16)
    provider = get_data_provider()
    payload = provider.get_export_payload()
    messages = payload.get("messages") or []
    entities = payload.get("entities") or []
    assert len(messages) > 0
    assert any(m.get("risk_level") in {"Low", "Medium", "High", "Critical"} for m in messages)
    assert any(e.get("entity_type") in {"narcotics", "firearms", "human_trafficking"} for e in entities)
    assert any(m.get("reply_to_message_id") or m.get("media_type") for m in messages)

    overview = provider.behavioral_overview()
    assert overview["total_users"] > 0
    assert "distribution" in overview

    end_simulation_mode()
    reset_to_live()


def test_ai_investigate_during_simulation_mode() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from ai.api import build_ai_router
    from data_providers.router import end_simulation_mode, start_simulation_mode
    from data_providers.state import reset_to_live
    from tests.test_ai_api import FakeFacade

    reset_to_live()
    start_simulation_mode(scenario="narcotics", auto_start=False)
    app = FastAPI()
    app.include_router(build_ai_router(FakeFacade()))
    client = TestClient(app)
    try:
        res = client.post(
            "/api/ai/investigate",
            json={"question": "Assess subject", "subject": {"user_id": 9000000001}},
        )
        assert res.status_code == 200
        assert res.json()["kind"] == "investigate"
    finally:
        end_simulation_mode()
        reset_to_live()


def test_database_namespace_isolation() -> None:
    from simulator.constants import DEFAULT_LIVE_DATABASE_NAME, DEFAULT_SIMULATION_DATABASE_NAME
    from simulator.contexts.database import DatabaseContext
    from simulator.enums import EnvironmentType

    live = DatabaseContext(environment=EnvironmentType.LIVE, database_name=DEFAULT_LIVE_DATABASE_NAME)
    sim = DatabaseContext(
        environment=EnvironmentType.SIMULATION,
        database_name=DEFAULT_SIMULATION_DATABASE_NAME,
    )
    assert live.database_name != sim.database_name


def test_simulation_does_not_write_production_mongo(db_settings) -> None:
    from datetime import datetime, timezone

    from data_providers.router import end_simulation_mode, get_data_provider, start_simulation_mode
    from data_providers.state import reset_to_live
    from models import Chat, Message

    settings, db_module = db_settings
    reset_to_live()

    with db_module.get_session(settings) as session:
        session.upsert_chat(Chat(id=42, title="Production Chat", chat_type="group"))
        session.insert_message(
            Message(
                message_id=1,
                chat_id=42,
                text="production baseline",
                timestamp=datetime.now(timezone.utc),
            )
        )
        before = session.messages.count_documents({})

    start_simulation_mode(scenario="narcotics", auto_start=False)
    from scrape_jobs.simulation_runner import run_simulation_scrape
    from scrape_jobs.store import ScrapeJobStore
    from config import load_settings

    store = ScrapeJobStore()
    store.try_begin()
    run_simulation_scrape(load_settings(), store, scenario="narcotics", limit=8)
    assert get_data_provider().mode == "simulation"

    with db_module.get_session(settings) as session:
        assert session.messages.count_documents({}) == before

    end_simulation_mode()
    reset_to_live()


def test_api_mode_and_core_endpoints(no_live_mongo) -> None:
    from fastapi.testclient import TestClient

    from data_providers.state import reset_to_live

    reset_to_live()
    from server import app

    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/mode").json()["mode"] == "live"
    assert client.get("/api/personnel").status_code == 200
    assert client.get("/api/behavioral/overview").status_code == 200
    assert client.get("/api/ai/health").status_code == 200

    enabled = client.put(
        "/api/mode",
        json={"mode": "simulation", "scenario": "narcotics", "auto_start": False},
    )
    assert enabled.status_code == 200
    assert client.get("/api/data").json()["source"] in {"simulation", "simulation_mongodb"}
    scrape = client.post("/api/scrape/start", json={})
    assert scrape.status_code == 200
    assert client.post("/api/scrape/start", json={}).status_code == 409
    assert client.post("/api/mode/end").json()["mode"] == "live"

