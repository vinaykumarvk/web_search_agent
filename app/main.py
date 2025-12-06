from __future__ import annotations

import asyncio
import json
import logging
from uuid import uuid4
from typing import Dict, Union, Optional, Tuple

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

from app.config import load_settings
from app.observability import configure_logging, configure_tracing, MetricsEmitter
from app.orchestrator import NormalizedRequest
from app.runtime import build_orchestrator
from app.schemas import (
    Depth,
    ResearchRequest,
    ResearchResponse,
    ResearchTaskCreated,
    ResearchTaskStatus,
    QualityReport,
    ResponseEnvelope,
    ResponseMetadata,
    TaskStatus,
)
from app.tools.deep_research import DeepResearchClient, MockDeepResearchClient

# Ensure .env is loaded even if uvicorn is started from a different CWD.
_DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_DOTENV_PATH, override=False)
settings = load_settings()
configure_logging(settings.observability)
tracer = configure_tracing(settings.observability)
logger = logging.getLogger("app")
metrics = MetricsEmitter()

if settings.openai_api_key:
    logger.info("OPENAI_API_KEY detected (length=%s)", len(settings.openai_api_key))
else:
    logger.warning("OPENAI_API_KEY not detected; OpenAI calls will fail")

app = FastAPI(title="Web Research Agent API", version="0.2.0")

# CORS configuration - allow configurable origins for production
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins != "*":
    allowed_origins = [origin.strip() for origin in allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if isinstance(allowed_origins, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info("%s %s", request.method, request.url.path)
        response = await call_next(request)
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response


app.add_middleware(LoggingMiddleware)

# Initialize persistent task storage
from app.utils.task_storage import TaskStorage
_task_storage = TaskStorage()
_tasks: Dict[str, ResearchTaskStatus] = {}  # In-memory cache for quick access
_deep_client = DeepResearchClient(metrics_emitter=metrics) if settings.openai_api_key else MockDeepResearchClient()
_orchestrator = build_orchestrator()


def _run_sync_research(
    payload: ResearchRequest, task_id: Optional[str] = None, metadata_extra: Optional[dict] = None
) -> Tuple[
    ResponseEnvelope,
    Optional[QualityReport],
    Optional[dict],
    Optional[dict],
    Optional[dict],
    Optional[list],
    Optional[list],
    Optional[str],
]:
    """Execute the orchestrated workflow synchronously."""

    metadata = {"controls": payload.controls}
    if metadata_extra:
        metadata.update(metadata_extra)
    normalized = NormalizedRequest(query=payload.query, metadata=metadata)
    result = _orchestrator.run(normalized)
    output = result["output"]
    envelope: ResponseEnvelope = output["envelope"]
    quality: Optional[QualityReport] = output.get("quality")
    bibliography = output.get("bibliography")
    source_map = output.get("source_map")
    notes = output.get("notes")
    findings = output.get("findings")
    evidence = output.get("evidence")
    overall_confidence = output.get("overall_confidence")
    envelope.metadata = ResponseMetadata(
        purpose=payload.controls.purpose,
        depth=payload.controls.depth,
        audience=payload.controls.audience,
        region=payload.controls.region,
        timeframe=payload.controls.timeframe,
        task_id=task_id,
        status=TaskStatus.COMPLETED,
    )
    return envelope, quality, bibliography, source_map, notes, findings, evidence, overall_confidence


async def _process_task(task_id: str, payload: ResearchRequest) -> None:
    """Background worker for async deep/long-running research with proper background polling."""

    logger.info("task.start", extra={"task_id": task_id})
    metrics.emit_task_status(task_id, TaskStatus.RUNNING)
    task_status = ResearchTaskStatus(task_id=task_id, status=TaskStatus.RUNNING, envelope=None)
    _tasks[task_id] = task_status
    _task_storage.save_task(task_status)  # Persist to database
    
    try:
        metadata_extra: dict = {}
        deep_results = None
        
        # For deep research, use proper background polling
        if payload.controls.depth == Depth.DEEP:
            try:
                # Start background research
                response_id = _deep_client.run_background(payload.query)
                logger.info("Started background deep research", extra={"task_id": task_id, "response_id": response_id})
                
                # Poll asynchronously until complete (non-blocking)
                # Use run_in_executor to run synchronous retrieve_response in async context
                import concurrent.futures
                loop = asyncio.get_event_loop()
                
                def poll_deep_research():
                    """Run synchronous polling in executor with intermediate note extraction."""
                    import time
                    start_time = time.time()
                    last_status = None
                    
                    while time.time() - start_time < 900:  # 15 minutes timeout for deep research
                        try:
                            status_response = _deep_client._client.responses.retrieve(response_id) if _deep_client._client else None
                            if status_response:
                                status = getattr(status_response, "status", None) or getattr(status_response, "response_status", None)
                                if status != last_status:
                                    logger.info("Deep research status changed", extra={"task_id": task_id, "status": status})
                                    last_status = status
                                
                                # Extract intermediate notes if available
                                intermediate_notes = _deep_client._extract_intermediate_notes(status_response)
                                if intermediate_notes and task_id in _tasks:
                                    current_notes = _tasks[task_id].notes or []
                                    new_notes = [n for n in intermediate_notes if n not in current_notes]
                                    if new_notes:
                                        _tasks[task_id].notes = list(set(current_notes + new_notes))
                                
                                # Check if complete
                                if status in ("completed", "succeeded"):
                                    return status_response
                                elif status in ("failed", "error"):
                                    error_msg = getattr(status_response, "error", {}).get("message", "Unknown error") if hasattr(status_response, "error") else "Unknown error"
                                    raise RuntimeError(f"Deep research failed: {error_msg}")
                            
                            time.sleep(2)  # Poll every 2 seconds
                        except Exception as exc:
                            if "completed" in str(exc).lower() or "succeeded" in str(exc).lower():
                                break
                            if time.time() - start_time > 900:  # 15 minutes timeout
                                raise TimeoutError("Deep research polling timeout")
                            time.sleep(2)
                    
                    raise TimeoutError("Deep research did not complete within timeout")
                
                try:
                    response = await loop.run_in_executor(None, poll_deep_research)
                    deep_results = _deep_client._extract_citations_from_response(response)
                    logger.info("Background deep research completed", extra={"task_id": task_id})
                except Exception as poll_exc:
                    logger.warning("Deep research polling failed", extra={"task_id": task_id, "error": str(poll_exc)})
                    metrics.emit_metric("deep_research.polling_failed", 1, extra={"task_id": task_id})
                    
            except Exception as exc:
                logger.warning("Deep research background failed; falling back to standard path: %s", exc)
                metrics.emit_metric("deep_research.fallback", 1, extra={"task_id": task_id, "error": str(exc)})

        if deep_results:
            metadata_extra["deep_results"] = deep_results

        envelope, quality, bibliography, source_map, notes, findings, evidence, overall_confidence = _run_sync_research(
            payload, task_id=task_id, metadata_extra=metadata_extra
        )
        _tasks[task_id] = ResearchTaskStatus(
            task_id=task_id,
            status=TaskStatus.WRITING,
            envelope=None,
            quality=None,
            bibliography=bibliography,
            source_map=source_map,
            notes=notes,
            findings=findings,
            evidence=evidence,
            overall_confidence=overall_confidence,
        )
        _tasks[task_id] = ResearchTaskStatus(
            task_id=task_id,
            status=TaskStatus.VALIDATING,
            envelope=None,
            quality=None,
            bibliography=bibliography,
            source_map=source_map,
            notes=notes,
            findings=findings,
            evidence=evidence,
            overall_confidence=overall_confidence,
        )
        task_status = ResearchTaskStatus(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            envelope=envelope,
            quality=quality,
            bibliography=bibliography,
            source_map=source_map,
            notes=notes,
            findings=findings,
            evidence=evidence,
            overall_confidence=overall_confidence,
        )
        _tasks[task_id] = task_status
        _task_storage.save_task(task_status)  # Persist to database
        logger.info("task.completed", extra={"task_id": task_id})
        metrics.emit_task_status(task_id, TaskStatus.COMPLETED)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Async task %s failed: %s", task_id, exc)
        task_status = ResearchTaskStatus(
            task_id=task_id,
            status=TaskStatus.FAILED,
            envelope=None,
            error=str(exc),
        )
        _tasks[task_id] = task_status
        _task_storage.save_task(task_status)  # Persist to database
        logger.info("task.failed", extra={"task_id": task_id, "error": str(exc)})
        metrics.emit_task_status(task_id, TaskStatus.FAILED)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness check - verifies OpenAI API key is configured for real API calls."""
    has_api_key = bool(settings.openai_api_key)
    return {
        "status": "ready" if has_api_key else "degraded",
        "openai_api_key_configured": has_api_key,
        "message": "API will make real OpenAI calls" if has_api_key else "WARNING: OPENAI_API_KEY not set - API will use fallbacks/mocks",
        "endpoints_available": {
            "router": "LLM-based" if has_api_key else "Heuristic fallback",
            "clarifier": "LLM-based" if has_api_key else "Skipped",
            "researcher": "OpenAI Responses API" if has_api_key else "No-op (empty results)",
            "writer": "GPT-5.1" if has_api_key else "Placeholder content",
            "fact_checker": "GPT-5.1 + Heuristics" if has_api_key else "Heuristics only",
            "deep_research": "O3-deep-research" if has_api_key else "Mock (test data)",
        },
    }


@app.post("/v1/agent/run", response_model=Union[ResearchResponse, ResearchTaskCreated])
async def create_research_job(payload: ResearchRequest, background_tasks: BackgroundTasks):
    """Start a research run. Deep/async requests are queued; quick/standard runs return immediately."""

    try:
        async_requested = payload.controls.async_mode or payload.controls.depth == Depth.DEEP

        if async_requested:
            task_id = str(uuid4())
            _tasks[task_id] = ResearchTaskStatus(
                task_id=task_id,
                status=TaskStatus.QUEUED,
                envelope=None,
            )
            background_tasks.add_task(_process_task, task_id, payload)
            return ResearchTaskCreated(task_id=task_id, status=TaskStatus.QUEUED, estimated_mode="async")

        envelope, quality, bibliography, source_map, notes, findings, evidence, overall_confidence = _run_sync_research(payload)
        return ResearchResponse(
            envelope=envelope,
            quality=quality,
            bibliography=bibliography,
            source_map=source_map,
            notes=notes,
            findings=findings,
            evidence=evidence,
            overall_confidence=overall_confidence,
        )
    except Exception as exc:
        logger.exception("Research job failed: %s", exc, extra={"query": payload.query, "controls": payload.controls.dict()})
        raise HTTPException(
            status_code=500,
            detail=f"Research job failed: {str(exc)}"
        ) from exc


@app.get("/v1/agent/tasks/{task_id}", response_model=ResearchTaskStatus)
async def get_research_task(task_id: str):
    """Retrieve the status (and response, when complete) for an async research task."""

    # Try in-memory cache first
    task = _tasks.get(task_id)
    if not task:
        # Fall back to persistent storage
        task = _task_storage.get_task(task_id)
        if task:
            _tasks[task_id] = task  # Cache for future access
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/v1/agent/tasks/{task_id}/stream")
async def stream_research_task(task_id: str):
    """SSE stream that emits progress and partial artifacts until completion."""

    async def event_stream():
        last_payload = None
        yield "event: status\ndata: {\"status\": \"stream_started\"}\n\n"
        while True:
            task = _tasks.get(task_id)
            if not task:
                yield "event: error\ndata: {\"error\": \"Task not found\"}\n\n"
                break

            payload = task.dict()
            if payload != last_payload:
                event_type = "status"
                if task.status == TaskStatus.RUNNING:
                    event_type = "running"
                elif task.status == TaskStatus.WRITING:
                    event_type = "writing"
                elif task.status == TaskStatus.VALIDATING:
                    event_type = "validating"
                elif task.status == TaskStatus.COMPLETED:
                    event_type = "completed"
                elif task.status == TaskStatus.FAILED:
                    event_type = "failed"

                # Emit partial findings/evidence when available
                if task.findings:
                    yield f"event: findings\ndata: {json.dumps(task.findings)}\n\n"
                if task.evidence:
                    yield f"event: evidence\ndata: {json.dumps(task.evidence)}\n\n"
                # Emit intermediate notes from deep research
                if task.notes:
                    yield f"event: notes\ndata: {json.dumps(task.notes)}\n\n"

                yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
                last_payload = payload

            if task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error("HTTP error %s: %s", exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
