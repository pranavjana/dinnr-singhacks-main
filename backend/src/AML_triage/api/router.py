"""FastAPI router exposing triage plan and feedback endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from ..core.config import Settings, load_settings
from ..core.metrics import REQUEST_LATENCY, configure_logging
from ..core.report_generator import ReportGenerationError, ReportGenerator
from ..core.validation import SchemaValidationError
from ..core.storage import FeedbackRecord, Storage


class FeedbackRequest(BaseModel):
    plan_id: str
    label: str = Field(pattern=r"^(good|bad)_(pass|sus|fail)$")
    action_fit: float | None = Field(default=None, ge=0, le=1)
    reviewer_id_hash: str
    notes: str | None = None


def get_settings() -> Settings:
    return load_settings()


def get_report_generator(settings: Settings = Depends(get_settings)) -> ReportGenerator:
    return ReportGenerator(settings=settings)


def get_storage(settings: Settings = Depends(get_settings)) -> Storage:
    return Storage(settings)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="AML Triage Service", version="0.1.0")

    @app.post("/triage/plan", response_class=PlainTextResponse)
    async def create_plan(
        screening_result: Dict[str, Any],
        generator: ReportGenerator = Depends(get_report_generator),
    ) -> PlainTextResponse:
        with REQUEST_LATENCY.labels(endpoint="triage_plan").time():
            try:
                report = await generator.generate_report(screening_result)
            except SchemaValidationError as exc:
                raise HTTPException(status_code=422, detail={"errors": exc.errors}) from exc
            except ReportGenerationError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            except Exception as exc:  # pragma: no cover - defensive guard
                raise HTTPException(status_code=500, detail=str(exc)) from exc
        return PlainTextResponse(report)

    @app.post("/feedback")
    async def submit_feedback(
        request: FeedbackRequest,
        storage: Storage = Depends(get_storage),
    ) -> JSONResponse:
        record = FeedbackRecord(
            plan_id=request.plan_id,
            label=request.label,
            action_fit=request.action_fit,
            reviewer_id_hash=request.reviewer_id_hash,
            notes=request.notes,
            created_at=datetime.now(timezone.utc),
        )
        storage.record_feedback(record)
        return JSONResponse({"status": "accepted", "stored_at": record.created_at.isoformat()})

    @app.get("/healthz")
    async def healthz(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
        return {
            "status": "ok",
            "schema_version": settings.schema_version,
            "strict_fields": settings.strict_fields,
            "offline_mode": settings.offline_mode,
            "template_top_k": settings.template_top_k,
        }

    return app


__all__ = ["create_app"]
