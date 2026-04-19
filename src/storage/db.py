"""
SQLite storage layer for plans and async jobs.

Uses a single file database at data/planner.db.
Thread-safe via a module-level lock for writes.
"""
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("data/planner.db")
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    """Create tables if they don't exist. Call once at startup."""
    with _lock, _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS plans (
                id            TEXT PRIMARY KEY,
                event_name    TEXT NOT NULL,
                generated_at  TEXT NOT NULL,
                iterations    INTEGER NOT NULL,
                failures      INTEGER NOT NULL,
                data          TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id         TEXT PRIMARY KEY,
                status     TEXT NOT NULL,
                message    TEXT NOT NULL DEFAULT '',
                plan_id    TEXT,
                error      TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
    logger.info(f"Database ready at {DB_PATH}")


# ── Plans ──────────────────────────────────────────────────────────────────────

def save_plan(plan_data: dict) -> str:
    """Persist a plan dict to the database. Returns the plan_id."""
    plan_id = plan_data["plan_id"]
    with _lock, _conn() as con:
        con.execute(
            """
            INSERT OR REPLACE INTO plans
                (id, event_name, generated_at, iterations, failures, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                plan_data.get("event_name", ""),
                plan_data.get("generated_at", ""),
                plan_data.get("iterations_taken", 0),
                plan_data.get("total_failures_surfaced", 0),
                json.dumps(plan_data),
            ),
        )
    return plan_id


def get_plan(plan_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT data FROM plans WHERE id = ?", (plan_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def list_plans() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT id, event_name, generated_at, iterations, failures
            FROM plans ORDER BY generated_at DESC
            """
        ).fetchall()
    return [
        {
            "plan_id": r["id"],
            "event_name": r["event_name"],
            "generated_at": r["generated_at"],
            "iterations_taken": r["iterations"],
            "total_failures_surfaced": r["failures"],
        }
        for r in rows
    ]


# ── Jobs ───────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_job(job_id: str) -> None:
    """Create a new job in 'pending' state."""
    now = _now()
    with _lock, _conn() as con:
        con.execute(
            "INSERT INTO jobs (id, status, message, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, "pending", "Queued — waiting to start.", now, now),
        )


def get_job(job_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def update_job(
    job_id: str,
    status: str,
    message: str = "",
    plan_id: str | None = None,
    error: str | None = None,
) -> None:
    with _lock, _conn() as con:
        con.execute(
            """
            UPDATE jobs
            SET status = ?, message = ?, plan_id = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, message, plan_id, error, _now(), job_id),
        )
