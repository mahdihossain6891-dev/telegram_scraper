"""Tests for Phase 10 isolated ``/api/ai`` FastAPI router."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai.api import AIServiceFacade, build_ai_router
from ai.api.serializers import citation_dict, query_response_dict
from ai.config import AISettings, clear_ai_settings_cache
from ai.models.schemas import Citation, QueryResponse
from dataclasses import replace
from pathlib import Path


def _settings(**kwargs) -> AISettings:
    clear_ai_settings_cache()
    base = AISettings(
        enabled=True,
        chat_provider="local",
        chat_model="fake-chat",
        embedding_provider="local",
        embedding_model="fake-embed",
        api_base_url="",
        api_key="",
        vector_backend="memory",
        vector_collection="ai_vectors",
        vector_url="",
        request_timeout_seconds=5.0,
        retry_max_attempts=1,
        retry_backoff_seconds=0.01,
        max_tokens=256,
        daily_token_budget=0,
        default_top_k=5,
        prompts_dir=Path(__file__).resolve().parents[1] / "ai" / "prompts",
        embed_batch_size=8,
        chunk_max_chars=400,
        chunk_overlap_chars=40,
        index_message_batch_size=50,
        rag_top_k=5,
        rag_max_evidence_items=5,
        rag_max_context_chars=4000,
        rag_context_token_budget=1000,
        rag_min_score=0.0,
        entity_min_confidence=0.4,
        entity_batch_size=20,
        assistant_name="Test Assistant",
        assistant_history_turns=4,
        assistant_session_collection="ai_sessions",
        report_collection="ai_reports",
    )
    return replace(base, **kwargs) if kwargs else base


class FakeFacade(AIServiceFacade):
    """Facade stub: no DB, no providers — HTTP contract only."""

    def __init__(self) -> None:
        super().__init__(settings=_settings(), db_factory=lambda: None)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "enabled": True,
            "chat_configured": True,
            "embeddings_configured": True,
            "chat_provider": "local",
            "embedding_provider": "local",
            "vector_backend": "memory",
            "report_collection": "ai_reports",
            "session_collection": "ai_sessions",
        }

    def ensure_ready(self) -> None:
        return None

    def query(self, question: str, *, top_k=None, filters=None) -> dict[str, Any]:
        self.calls.append(("query", {"question": question, "top_k": top_k, "filters": filters}))
        return {
            "answer": f"Answer for: {question}",
            "citations": [
                {
                    "source_type": "message",
                    "source_id": "1",
                    "label": "E1:msg",
                    "snippet": "evidence",
                }
            ],
            "confidence": "high",
            "model": "fake",
            "retrieved": [],
            "metadata": {},
        }

    def summary(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("summary", kwargs))
        return {
            "kind": "summary",
            "session_id": "s1",
            "intent": "summary",
            "intent_label": "Summarize",
            "answer": "Summary [E1]",
            "citations": [
                {
                    "source_type": "message",
                    "source_id": "1",
                    "label": "E1",
                    "snippet": "x",
                }
            ],
            "confidence": "medium",
            "model": "fake",
            "refused": False,
            "retrieved": [],
            "metadata": {},
        }

    def report(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("report", kwargs))
        return {
            "report_id": "r1",
            "report_type": kwargs.get("report_type"),
            "title": "Report",
            "subject_type": kwargs.get("subject_type"),
            "subject_id": kwargs.get("subject_id"),
            "sections": [],
            "citations": [],
            "confidence": "low",
            "model": "fake",
            "body_markdown": "# Report",
            "refused": False,
            "created_at": None,
            "metadata": {},
        }

    def investigate(self, question: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("investigate", {"question": question, **kwargs}))
        return {
            "kind": "investigate",
            "session_id": kwargs.get("session_id") or "s-inv",
            "intent": "high_risk",
            "intent_label": "high risk",
            "answer": "Because [E1]",
            "citations": [
                {
                    "source_type": "message",
                    "source_id": "1",
                    "label": "E1",
                    "snippet": "y",
                }
            ],
            "confidence": "high",
            "model": "fake",
            "refused": False,
            "retrieved": [],
            "metadata": {},
        }

    def chat(self, message: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("chat", {"message": message, **kwargs}))
        return {
            "kind": "chat",
            "session_id": kwargs.get("session_id") or "s-chat",
            "intent": "general",
            "intent_label": "general",
            "answer": "Chat reply [E1]",
            "citations": [
                {
                    "source_type": "message",
                    "source_id": "1",
                    "label": "E1",
                    "snippet": "z",
                }
            ],
            "confidence": "medium",
            "model": "fake",
            "refused": False,
            "retrieved": [],
            "metadata": {},
        }

    def list_providers(self, *, refresh: bool = False) -> dict[str, Any]:
        self.calls.append(("list_providers", {"refresh": refresh}))
        return {
            "providers": [
                {
                    "id": "ollama",
                    "label": "Ollama",
                    "kind": "local",
                    "selected": True,
                    "health": {
                        "ok": True,
                        "status": "healthy",
                        "latency_ms": 12,
                        "models_available": 1,
                    },
                }
            ],
            "selected_provider": "ollama",
        }

    def list_models(
        self, *, provider: str | None = None, refresh: bool = False
    ) -> dict[str, Any]:
        self.calls.append(("list_models", {"provider": provider, "refresh": refresh}))
        return {
            "provider": provider or "ollama",
            "models": [
                {
                    "model_id": "dyn-discovered",
                    "display_name": "Dyn Discovered",
                    "provider": provider or "ollama",
                    "capabilities": {"supports_streaming": True},
                }
            ],
            "cached": False,
            "error": None,
            "count": 1,
        }

    def provider_health(
        self, *, provider: str | None = None, refresh: bool = False
    ) -> dict[str, Any]:
        self.calls.append(("provider_health", {"provider": provider, "refresh": refresh}))
        return {
            "provider": provider or "ollama",
            "ok": True,
            "status": "healthy",
            "detail": "reachable",
            "latency_ms": 15,
            "models_available": 1,
            "cached": False,
        }

    def clear_model_cache(self, *, provider: str | None = None) -> dict[str, Any]:
        self.calls.append(("clear_model_cache", {"provider": provider}))
        return {"ok": True, "provider": provider, "cache": {}}

    def test_provider(self, *, provider: str | None = None) -> dict[str, Any]:
        return self.provider_health(provider=provider, refresh=True)

    def reload_prompts(self) -> dict[str, Any]:
        self.calls.append(("reload_prompts", {}))
        return {
            "ok": True,
            "prompt_ids": ["investigation_assistant"],
            "prompt_version": "investigation_assistant@v1",
        }

    def planner_info(self, *, question=None, subject=None) -> dict[str, Any]:
        self.calls.append(("planner_info", {"question": question}))
        return {
            "planner": "InvestigationPlanner",
            "pipeline": ["user_question", "investigation_planner", "tool_registry"],
            "registered_tools": ["risk", "search"],
            "preview": {"intent": "investigate_user"} if question else None,
        }

    def list_tools_catalog(self) -> dict[str, Any]:
        self.calls.append(("list_tools_catalog", {}))
        return {"tools": [{"name": "risk", "description": "risk"}], "catalog": []}


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(build_ai_router(FakeFacade()))
    return TestClient(app)


def test_health(client: TestClient) -> None:
    res = client.get("/api/ai/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "db" not in body
    assert "mongo" not in body


def test_query(client: TestClient) -> None:
    res = client.post("/api/ai/query", json={"question": "Who is active at night?"})
    assert res.status_code == 200
    body = res.json()
    assert "answer" in body
    assert body["citations"]
    assert "database" not in body


def test_summary(client: TestClient) -> None:
    res = client.post(
        "/api/ai/summary",
        json={"subject_id": "55", "subject_type": "user"},
    )
    assert res.status_code == 200
    assert res.json()["kind"] == "summary"


def test_report(client: TestClient) -> None:
    res = client.post(
        "/api/ai/report",
        json={
            "report_type": "user_intelligence",
            "subject_id": "55",
            "persist": False,
        },
    )
    assert res.status_code == 200
    assert res.json()["report_type"] == "user_intelligence"


def test_investigate_and_chat(client: TestClient) -> None:
    inv = client.post(
        "/api/ai/investigate",
        json={"question": "Why is this user high risk?", "subject": {"user_id": 55}},
    )
    assert inv.status_code == 200
    assert inv.json()["citations"]

    chat = client.post(
        "/api/ai/chat",
        json={"message": "Show behavioral anomalies", "session_id": inv.json()["session_id"]},
    )
    assert chat.status_code == 200
    assert chat.json()["kind"] == "chat"


def test_discovery_endpoints(client: TestClient) -> None:
    providers = client.get("/api/ai/providers")
    assert providers.status_code == 200
    assert providers.json()["providers"]

    models = client.get("/api/ai/models", params={"provider": "ollama"})
    assert models.status_code == 200
    body = models.json()
    assert body["count"] == 1
    assert body["models"][0]["model_id"] == "dyn-discovered"

    health = client.get("/api/ai/provider/health", params={"provider": "ollama"})
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


def test_control_center_endpoints(client: TestClient) -> None:
    cleared = client.post("/api/ai/cache/clear", json={})
    assert cleared.status_code == 200
    assert cleared.json()["ok"] is True

    tested = client.post("/api/ai/provider/test", json={"provider": "ollama"})
    assert tested.status_code == 200
    assert tested.json()["ok"] is True

    reloaded = client.post("/api/ai/prompts/reload")
    assert reloaded.status_code == 200
    assert reloaded.json()["ok"] is True


def test_planner_and_tools_endpoints(client: TestClient) -> None:
    planner = client.get("/api/ai/planner")
    assert planner.status_code == 200
    assert planner.json()["planner"] == "InvestigationPlanner"

    preview = client.get("/api/ai/planner", params={"question": "Investigate user"})
    assert preview.status_code == 200
    assert preview.json().get("preview")

    tools = client.get("/api/ai/tools")
    assert tools.status_code == 200
    assert tools.json()["tools"]


def test_serializers_omit_raw_evidence() -> None:
    result = QueryResponse(
        answer="ok [E1]",
        citations=[Citation(source_type="message", source_id="1", label="E1", snippet="hi")],
        confidence="high",
        model="m",
        metadata={"filters": {}},
    )
    payload = query_response_dict(result)
    assert "evidence" not in payload
    assert citation_dict(result.citations[0])["source_id"] == "1"


def test_disabled_ai_returns_503() -> None:
    facade = AIServiceFacade(settings=_settings(enabled=False), db_factory=lambda: None)
    app = FastAPI()
    app.include_router(build_ai_router(facade))
    client = TestClient(app)
    res = client.post("/api/ai/query", json={"question": "hello"})
    assert res.status_code == 503
    health = client.get("/api/ai/health")
    assert health.status_code == 200
    assert health.json()["status"] == "disabled"


def test_server_mounts_ai_router_without_changing_existing_paths() -> None:
    """Additive mount: /api/ai works; existing routes still registered."""
    from server import app

    paths = {getattr(r, "path", None) for r in app.routes}
    # Existing endpoints untouched
    assert "/api/behavioral/overview" in paths
    assert "/api/alerts/status" in paths
    assert "/api/data" in paths

    client = TestClient(app)
    health = client.get("/api/ai/health")
    assert health.status_code == 200
    assert "enabled" in health.json()
    # OpenAPI documents the AI paths
    spec = client.get("/openapi.json").json()
    assert "/api/ai/health" in spec["paths"]
    assert "/api/ai/query" in spec["paths"]
    assert "/api/ai/summary" in spec["paths"]
    assert "/api/ai/report" in spec["paths"]
    assert "/api/ai/investigate" in spec["paths"]
    assert "/api/ai/chat" in spec["paths"]
    assert "/api/ai/providers" in spec["paths"]
    assert "/api/ai/models" in spec["paths"]
    assert "/api/ai/provider/health" in spec["paths"]
