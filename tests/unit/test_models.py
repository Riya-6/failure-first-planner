"""Unit tests for Pydantic data models."""
import pytest
from datetime import date
from pydantic import ValidationError

from src.models.event import LiveMusicEvent
from src.models.failure import FailureScenario, FailureReport, FailureSeverity
from src.models.plan import RobustPlan, TimelineEntry, BackupOptions


# ── LiveMusicEvent ────────────────────────────────────────────────────────────

def make_event(**overrides) -> LiveMusicEvent:
    defaults = dict(
        name="Test Fest",
        venue="Test Arena",
        venue_capacity=5000,
        headliner="Test Band",
        date=date(2025, 9, 1),
        is_outdoor=False,
        expected_attendance=4500,
        budget_usd=100_000,
        city="London",
    )
    return LiveMusicEvent(**{**defaults, **overrides})


def test_event_valid():
    event = make_event()
    assert event.name == "Test Fest"
    assert event.venue_capacity == 5000


def test_event_attendance_exceeds_capacity_raises():
    with pytest.raises(ValidationError, match="exceeds venue_capacity"):
        make_event(expected_attendance=6000, venue_capacity=5000)


def test_event_negative_capacity_raises():
    with pytest.raises(ValidationError):
        make_event(venue_capacity=-1)


def test_event_model_dump_json_serializable():
    import json
    event = make_event()
    dumped = event.model_dump(mode="json")
    assert json.dumps(dumped)  # must not raise


# ── FailureScenario ───────────────────────────────────────────────────────────

def make_scenario(**overrides) -> FailureScenario:
    defaults = dict(
        title="Headliner Cancellation",
        description="Artist cancels 48hrs before due to illness.",
        severity=FailureSeverity.CRITICAL,
        root_cause="No backup headliner contracted.",
        affected_components=["artist", "ticketing"],
        probability=0.08,
    )
    return FailureScenario(**{**defaults, **overrides})


def test_scenario_valid():
    s = make_scenario()
    assert s.severity == FailureSeverity.CRITICAL
    assert s.probability == 0.08


def test_scenario_probability_out_of_range():
    with pytest.raises(ValidationError):
        make_scenario(probability=1.5)


def test_scenario_invalid_severity():
    with pytest.raises(ValidationError):
        make_scenario(severity="catastrophic")


# ── FailureReport ─────────────────────────────────────────────────────────────

def test_report_critical_count():
    report = FailureReport(
        event_name="Test",
        iteration=1,
        scenarios=[
            make_scenario(severity=FailureSeverity.CRITICAL),
            make_scenario(severity=FailureSeverity.HIGH),
            make_scenario(severity=FailureSeverity.CRITICAL),
        ],
    )
    assert report.critical_count == 2
    assert report.has_critical is True


def test_report_no_critical():
    report = FailureReport(
        event_name="Test",
        iteration=1,
        scenarios=[make_scenario(severity=FailureSeverity.LOW)],
    )
    assert report.has_critical is False


def test_report_empty_scenarios():
    report = FailureReport(event_name="Test", iteration=1, scenarios=[])
    assert report.critical_count == 0
    assert report.has_critical is False


# ── RobustPlan ────────────────────────────────────────────────────────────────

def test_robust_plan_defaults():
    plan = RobustPlan(
        event_name="Test Fest",
        summary="A summary.",
        iterations_taken=2,
        total_failures_surfaced=5,
    )
    assert plan.timeline == []
    assert plan.go_no_go_checkpoints == []
    assert isinstance(plan.backup_options, BackupOptions)
    assert plan.generated_at  # auto-set


def test_timeline_entry_optional_contingency():
    entry = TimelineEntry(time="T-7 days", action="Sound check", owner="Audio team")
    assert entry.contingency == ""
