"""Tests for TIE → Console intelligence ingest endpoint."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("TIE_INGEST_API_KEY", "test-ingest-key")
    # Import after env so module-level readers see it on each request
    from server import app

    return TestClient(app)


def test_receive_intelligence_report(client):
    payload = {
        "message_id": "tie-test-1",
        "original_text": "white available",
        "translated_text": "white available",
        "language": "English",
        "indicators": {"keywords": ["white"]},
        "classification": {"categories": [{"name": "narcotics", "confidence": 0.9}]},
        "risk": {"score": 80, "level": "High", "reasons": ["keyword"]},
        "channel": "ops-lab",
        "source": "telegram",
    }
    res = client.post(
        "/api/intelligence/reports",
        json=payload,
        headers={"Authorization": "Bearer test-ingest-key"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["message_id"] == "tie-test-1"
    assert body["status"] in {"accepted", "updated"}

    listed = client.get(
        "/api/intelligence/reports?limit=10",
        headers={"Authorization": "Bearer test-ingest-key"},
    )
    assert listed.status_code == 200
    ids = [i["message_id"] for i in listed.json()["items"]]
    assert "tie-test-1" in ids


def test_receive_rejects_bad_auth(client):
    res = client.post(
        "/api/intelligence/reports",
        json={
            "message_id": "x",
            "original_text": "a",
            "translated_text": "a",
            "language": "en",
            "risk": {"score": 1, "level": "Low", "reasons": []},
        },
        headers={"Authorization": "Bearer wrong"},
    )
    assert res.status_code == 401


def test_ingest_status(client):
    res = client.get("/api/intelligence/status")
    assert res.status_code == 200
    assert res.json()["ingest"] in {"ready", "degraded"}
