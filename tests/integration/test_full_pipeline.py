"""
Integration tests — hit the real OpenAI API.

Run with:
    pytest tests/integration/ -v -m integration

Requires OPENAI_API_KEY set in .env.
These tests are intentionally slow (~30–90s) and cost real tokens.
"""
import json
import pytest
from datetime import date
from pathlib import Path

from src.models.event import LiveMusicEvent
from src.orchestrator.loop import run_failure_first_loop
from src.utils.config import Config


@pytest.fixture(scope="module")
def small_event() -> LiveMusicEvent:
    """A small, inexpensive event for integration testing."""
    return LiveMusicEvent(
        name="Integration Test Concert",
        venue="Small Club",
        venue_capacity=500,
        headliner="Test Artist",
        supporting_acts=[],
        date=date(2025, 10, 1),
        is_outdoor=False,
        expected_attendance=450,
        budget_usd=15_000,
        city="London",
    )


@pytest.mark.integration
def test_api_key_is_set():
    """Sanity check: OPENAI_API_KEY must be configured."""
    assert Config.OPENAI_API_KEY, (
        "Set OPENAI_API_KEY in your .env file before running integration tests."
    )


@pytest.mark.integration
def test_full_pipeline_returns_valid_plan(small_event):
    """
    End-to-end test: runs the full failure-first loop against the real API
    and asserts the output plan is well-formed.
    """
    plan = run_failure_first_loop(small_event)

    assert plan.event_name == "Integration Test Concert"
    assert plan.iterations_taken >= 1
    assert plan.total_failures_surfaced >= 1
    assert plan.summary, "Plan summary must not be empty."
    assert len(plan.timeline) > 0, "Plan must have at least one timeline entry."
    assert len(plan.go_no_go_checkpoints) > 0, "Plan must have at least one go/no-go checkpoint."
    assert len(plan.risk_register) > 0, "Plan must have at least one risk register entry."


@pytest.mark.integration
def test_full_pipeline_saves_output(small_event, tmp_path):
    """Plan JSON must be serialisable and writable."""
    plan = run_failure_first_loop(small_event)

    output_file = tmp_path / "integration_plan.json"
    output_file.write_text(plan.model_dump_json(indent=2))

    reloaded = json.loads(output_file.read_text())
    assert reloaded["event_name"] == "Integration Test Concert"
    assert "timeline" in reloaded
    assert "risk_register" in reloaded
