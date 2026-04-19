"""
FastAPI HTTP service for the Failure-First Planner.

Run with:
    uvicorn src.api.app:app --reload

Endpoints:
    GET  /                    — frontend UI
    GET  /health              — liveness check, no auth
    POST /plans/async         — submit a plan job, returns job_id immediately
    GET  /jobs/{job_id}       — poll job status (pending|running|done|failed)
    GET  /plans               — list all saved plans
    GET  /plans/{plan_id}     — retrieve a specific plan

Auth:
    X-API-Key header matching PLANNER_API_KEY in .env.
    If PLANNER_API_KEY is unset, auth is disabled (dev mode).

Rate limiting:
    POST /plans/async — 10 requests/minute per IP
"""
import json
import logging
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from src.models.event import LiveMusicEvent
from src.models.plan import RobustPlan
from src.orchestrator.loop import run_failure_first_loop
from src.storage.db import init_db, save_plan, get_plan, list_plans, save_job, get_job, update_job
from src.utils.config import Config
from src.utils.logger import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

# ── Simple in-process rate limiter ─────────────────────────────────────────────

_rate_counts: dict = defaultdict(list)  # ip -> [timestamps]
_rate_lock = threading.Lock()

def _check_rate_limit(ip: str, limit: int = 10, window: int = 60) -> bool:
    """Return True if request is allowed, False if rate limit exceeded."""
    now = time.monotonic()
    with _rate_lock:
        timestamps = [t for t in _rate_counts[ip] if now - t < window]
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        _rate_counts[ip] = timestamps
    return True


app = FastAPI(
    title="Failure-First Planner API",
    description="AI-powered failure-first live music event planning agent.",
    version="1.0.0",
)

# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()


# ── Auth ───────────────────────────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _require_auth(key: str | None = Security(_api_key_header)) -> None:
    if not Config.PLANNER_API_KEY:
        return  # dev mode — auth disabled
    if key != Config.PLANNER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key.")


# ── Response models ────────────────────────────────────────────────────────────

class PlanResponse(RobustPlan):
    plan_id: str


class PlanSummary(BaseModel):
    plan_id: str
    event_name: str
    generated_at: str
    iterations_taken: int
    total_failures_surfaced: int


class JobResponse(BaseModel):
    job_id: str
    status: str          # pending | running | done | failed
    message: str
    plan_id: str | None = None
    error: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run_planning_job(job_id: str, event: LiveMusicEvent) -> None:
    """Background thread: run the planning loop and update job state."""
    try:
        update_job(job_id, "running", "Running failure-first loop (1–2 min)...")
        plan = run_failure_first_loop(event)

        plan_data = json.loads(plan.model_dump_json())
        plan_id = str(uuid.uuid4())
        plan_data["plan_id"] = plan_id
        save_plan(plan_data)

        update_job(job_id, "done", "Plan ready.", plan_id=plan_id)
        logger.info(f"Job {job_id} complete — plan {plan_id}")

    except Exception as exc:
        logger.error(f"Job {job_id} failed: {exc}")
        update_job(job_id, "failed", error=str(exc), message="Planning loop failed.")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse("frontend/index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": Config.OPENAI_MODEL,
        "auth_enabled": bool(Config.PLANNER_API_KEY),
    }


@app.post("/plans/async", response_model=JobResponse, status_code=202)
def create_plan_async(
    request: Request,
    event: LiveMusicEvent,
    _: None = Depends(_require_auth),
):
    """
    Submit a planning job. Returns immediately with a job_id.
    Poll GET /jobs/{job_id} for status and the final plan_id.
    """
    ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Too many requests. Max 10 plans per minute.")

    job_id = str(uuid.uuid4())
    save_job(job_id)
    threading.Thread(target=_run_planning_job, args=(job_id, event), daemon=True).start()
    logger.info(f"Job {job_id} queued for event '{event.name}'")
    return JobResponse(job_id=job_id, status="pending", message="Queued — waiting to start.")


@app.get("/jobs/{job_id}", response_model=JobResponse)
def poll_job(job_id: str, _: None = Depends(_require_auth)):
    """Poll the status of an async planning job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return JobResponse(
        job_id=job["id"],
        status=job["status"],
        message=job["message"],
        plan_id=job.get("plan_id"),
        error=job.get("error"),
    )


@app.get("/plans", response_model=list[PlanSummary])
def list_all_plans(_: None = Depends(_require_auth)):
    """List all saved plans, newest first."""
    return list_plans()


@app.get("/plans/{plan_id}", response_model=PlanResponse)
def get_plan_by_id(plan_id: str, _: None = Depends(_require_auth)):
    """Retrieve a previously generated plan by its ID."""
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")
    return plan
