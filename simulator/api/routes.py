"""FastAPI routes for Threat Simulation console."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from simulator.api.facade import SimulationConsoleFacade
from simulator.api.singleton import get_simulator_facade

logger = logging.getLogger("simulator.api.routes")


class CreateSessionBody(BaseModel):
    name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ConfigBody(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class ScenarioPatchBody(BaseModel):
    enabled: bool | None = None
    weight: float | None = None


def build_simulator_router(facade: SimulationConsoleFacade | None = None) -> APIRouter:
    """Return router mounted at ``/api/simulator`` — simulation environment only."""
    console = facade or get_simulator_facade()
    router = APIRouter(prefix="/api/simulator", tags=["simulator"])

    @router.get("/health")
    def health() -> JSONResponse:
        return JSONResponse(console.health())

    @router.get("/overview")
    def overview(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.overview(session_id))

    @router.get("/sessions")
    def list_sessions() -> JSONResponse:
        return JSONResponse({"sessions": console.list_sessions()})

    @router.post("/sessions")
    def create_session(body: CreateSessionBody) -> JSONResponse:
        return JSONResponse(console.create_session(name=body.name, config=body.config))

    @router.get("/sessions/{session_id}")
    def get_session(session_id: str) -> JSONResponse:
        try:
            return JSONResponse(console.get_session(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete("/sessions/{session_id}")
    def delete_session(session_id: str) -> JSONResponse:
        return JSONResponse(console.delete_session(session_id))

    @router.post("/sessions/{session_id}/duplicate")
    def duplicate_session(session_id: str) -> JSONResponse:
        try:
            return JSONResponse(console.duplicate_session(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/sessions/{session_id}/export")
    def export_session(session_id: str, fmt: str = "json") -> PlainTextResponse:
        try:
            return PlainTextResponse(console.export_session(session_id, fmt=fmt), media_type="application/json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/control/start")
    def start(session_id: str | None = None) -> JSONResponse:
        try:
            return JSONResponse(console.start(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/control/pause")
    def pause(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.pause(session_id))

    @router.post("/control/resume")
    def resume(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.resume(session_id))

    @router.post("/control/stop")
    def stop(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.stop(session_id))

    @router.post("/control/tick")
    def tick(session_id: str | None = None) -> JSONResponse:
        try:
            return JSONResponse(console.tick(session_id))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/scenarios")
    def scenarios() -> JSONResponse:
        return JSONResponse({"scenarios": console.scenarios()})

    @router.patch("/scenarios/{scenario_id}")
    def patch_scenario(scenario_id: str, body: ScenarioPatchBody) -> JSONResponse:
        return JSONResponse(console.update_scenario(scenario_id, enabled=body.enabled, weight=body.weight))

    @router.get("/personas")
    def personas(session_id: str | None = None, q: str = "", limit: int = 200) -> JSONResponse:
        return JSONResponse({"personas": console.personas(session_id, q=q, limit=limit)})

    @router.get("/groups")
    def groups(session_id: str | None = None, q: str = "", limit: int = 100) -> JSONResponse:
        return JSONResponse({"groups": console.groups(session_id, q=q, limit=limit)})

    @router.get("/activity")
    def activity(session_id: str | None = None, q: str = "", limit: int = 500) -> JSONResponse:
        return JSONResponse({"messages": console.activity(session_id, q=q, limit=limit)})

    @router.get("/pipeline/{session_id}/{message_id}")
    def pipeline_inspect(session_id: str, message_id: str) -> JSONResponse:
        return JSONResponse(console.pipeline_inspect(session_id, message_id))

    @router.get("/benchmark")
    def benchmark(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.benchmark(session_id))

    @router.get("/reports")
    def reports(session_id: str | None = None) -> JSONResponse:
        return JSONResponse({"reports": console.reports(session_id)})

    @router.get("/config")
    def get_config(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.get_config(session_id))

    @router.put("/config")
    def put_config(body: ConfigBody, session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.update_config(session_id, body.config))

    @router.get("/metrics")
    def metrics(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.metrics(session_id))

    @router.get("/pipeline-health")
    def pipeline_health(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.pipeline_health(session_id))

    @router.get("/architecture")
    def architecture(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.architecture(session_id))

    return router
