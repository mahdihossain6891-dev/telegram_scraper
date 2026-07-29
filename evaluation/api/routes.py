"""FastAPI routes for Intelligence Evaluation Framework."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from evaluation.api.facade import EvaluationFacade

logger = logging.getLogger("evaluation.api.routes")


class BenchmarkBody(BaseModel):
    dataset_id: str | None = None
    version: str = "1.0.0"
    ticks: int = 5
    users: int = 40
    groups: int = 6
    random_seed: int = 42
    tags: list[str] = Field(default_factory=list)
    weights: dict[str, float] | None = None


class DatasetImportBody(BaseModel):
    name: str
    scenario_ids: list[str] = Field(default_factory=list)
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)


class ExperimentBody(BaseModel):
    name: str
    variant_a: str = "A"
    variant_b: str = "B"


class ExperimentRecordBody(BaseModel):
    variant: str = "a"
    result: dict[str, Any] = Field(default_factory=dict)


def build_evaluation_router(facade: EvaluationFacade | None = None) -> APIRouter:
    """Return router at ``/api/evaluation`` — evaluation environment only."""
    console = facade or EvaluationFacade()
    router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])

    @router.get("/health")
    def health() -> JSONResponse:
        return JSONResponse(console.health())

    @router.post("/benchmark/run")
    def run_benchmark(body: BenchmarkBody) -> JSONResponse:
        try:
            return JSONResponse(console.run_benchmark(body.model_dump()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/benchmark/latest")
    def latest_benchmark(session_id: str | None = None) -> JSONResponse:
        return JSONResponse(console.latest(session_id))

    @router.get("/benchmark/session/{session_id}")
    def session_benchmark(session_id: str) -> JSONResponse:
        try:
            return JSONResponse(console.evaluate_session(session_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/benchmark/history")
    def benchmark_history(limit: int = 50) -> JSONResponse:
        return JSONResponse({"history": console.history(limit=limit)})

    @router.get("/benchmark/trend")
    def benchmark_trend() -> JSONResponse:
        return JSONResponse({"trend": console.trend()})

    @router.get("/benchmark/regression")
    def regression(baseline_id: str, candidate_id: str) -> JSONResponse:
        try:
            return JSONResponse(console.compare_regression(baseline_id, candidate_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/datasets")
    def list_datasets() -> JSONResponse:
        return JSONResponse({"datasets": console.datasets()})

    @router.post("/datasets")
    def import_dataset(body: DatasetImportBody) -> JSONResponse:
        return JSONResponse(console.import_dataset(body.model_dump()))

    @router.get("/leaderboard")
    def leaderboard() -> JSONResponse:
        return JSONResponse(console.leaderboard())

    @router.get("/experiments")
    def experiments() -> JSONResponse:
        return JSONResponse({"experiments": console.experiments()})

    @router.post("/experiments")
    def create_experiment(body: ExperimentBody) -> JSONResponse:
        return JSONResponse(console.create_experiment(body.model_dump()))

    @router.post("/experiments/{experiment_id}/record")
    def record_experiment(experiment_id: str, body: ExperimentRecordBody) -> JSONResponse:
        return JSONResponse(console.record_experiment(experiment_id, body.model_dump()))

    @router.get("/reports")
    def reports(benchmark_id: str | None = None) -> JSONResponse:
        return JSONResponse({"reports": console.reports(benchmark_id)})

    @router.get("/reports/{report_id}/export")
    def export_report(report_id: str, benchmark_id: str | None = None, fmt: str = "json") -> PlainTextResponse:
        try:
            content = console.export_report(report_id, benchmark_id, fmt)
            media = "text/markdown" if fmt == "md" else "text/csv" if fmt == "csv" else "application/json"
            return PlainTextResponse(content, media_type=media)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/observability")
    def observability() -> JSONResponse:
        return JSONResponse(console.observability())

    @router.get("/scoring/weights")
    def scoring_weights() -> JSONResponse:
        return JSONResponse(console.scoring_weights())

    return router
