"""Unit tests for the failure simulator agent (mocked OpenAI calls)."""
import json
import pytest
from datetime import date
from unittest.mock import MagicMock, patch, PropertyMock

from src.models.event import LiveMusicEvent
from src.models.failure import FailureSeverity
from src.agents.failure_simulator import simulate_failures, _parse_scenarios, _enrich_event


MOCK_FAILURES_JSON = json.dumps([
    {
        "title": "Headliner Cancellation",
        "description": "Arctic Monkeys cancel 48hrs before due to illness.",
        "severity": "critical",
        "root_cause": "No backup headliner contracted.",
        "affected_components": ["artist", "ticketing"],
        "probability": 0.08,
    },
    {
        "title": "Generator Failure",
        "description": "Primary generator fails during headliner set.",
        "severity": "high",
        "root_cause": "No backup generator on standby.",
        "affected_components": ["power", "sound"],
        "probability": 0.05,
    },
])


@pytest.fixture
def sample_event() -> LiveMusicEvent:
    return LiveMusicEvent(
        name="SoundWave Festival 2025",
        venue="Griffith Park Amphitheater",
        venue_capacity=8000,
        headliner="Arctic Monkeys",
        supporting_acts=["Wet Leg"],
        date=date(2025, 8, 15),
        is_outdoor=True,
        expected_attendance=7500,
        budget_usd=450_000,
        city="Los Angeles",
    )


def _make_mock_client(response_text: str) -> MagicMock:
    """Build a mock OpenAI client that returns response_text from chat.completions.create."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=response_text))]
    mock_response.usage = MagicMock(prompt_tokens=200, completion_tokens=100)
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ── _parse_scenarios ──────────────────────────────────────────────────────────

def test_parse_scenarios_valid_json():
    scenarios = _parse_scenarios(MOCK_FAILURES_JSON)
    assert len(scenarios) == 2
    assert scenarios[0].title == "Headliner Cancellation"
    assert scenarios[0].severity == FailureSeverity.CRITICAL
    assert scenarios[1].severity == FailureSeverity.HIGH


def test_parse_scenarios_embedded_in_prose():
    text = f"Here are the failures:\n{MOCK_FAILURES_JSON}\nEnd."
    scenarios = _parse_scenarios(text)
    assert len(scenarios) == 2


def test_parse_scenarios_no_json_returns_empty():
    scenarios = _parse_scenarios("No JSON here at all.")
    assert scenarios == []


def test_parse_scenarios_malformed_json_returns_empty():
    scenarios = _parse_scenarios("[{broken json")
    assert scenarios == []


# ── simulate_failures ─────────────────────────────────────────────────────────

def test_simulate_failures_returns_report(sample_event):
    mock_client = _make_mock_client(MOCK_FAILURES_JSON)

    with patch("src.agents.failure_simulator.get_weather_risk",
               return_value={"risk_level": "low", "reasons": []}), \
         patch("src.agents.failure_simulator.get_venue_info",
               return_value={"status": "stub"}), \
         patch("src.agents.failure_simulator.get_artist_risk",
               return_value={"status": "stub"}), \
         patch("src.agents.failure_simulator.assess_ticketing_risk",
               return_value={"oversell_risk": "medium"}), \
         patch("src.agents.failure_simulator.assess_logistics_risk",
               return_value={"overall_logistics_risk": "medium"}):

        report = simulate_failures(mock_client, sample_event, iteration=1)

    assert report.event_name == "SoundWave Festival 2025"
    assert len(report.scenarios) == 2
    assert report.critical_count == 1
    assert report.has_critical is True
    assert report.iteration == 1


def test_simulate_failures_tool_errors_dont_crash(sample_event):
    """Tool failures must be swallowed — the agent should still run."""
    mock_client = _make_mock_client(MOCK_FAILURES_JSON)

    with patch("src.agents.failure_simulator.get_weather_risk",
               side_effect=Exception("Network error")), \
         patch("src.agents.failure_simulator.get_venue_info",
               side_effect=Exception("API key missing")), \
         patch("src.agents.failure_simulator.get_artist_risk",
               return_value={}), \
         patch("src.agents.failure_simulator.assess_ticketing_risk",
               return_value={}), \
         patch("src.agents.failure_simulator.assess_logistics_risk",
               return_value={}):

        report = simulate_failures(mock_client, sample_event)

    assert len(report.scenarios) == 2  # Still parsed despite tool failures


def test_simulate_failures_empty_response(sample_event):
    mock_client = _make_mock_client("Claude returned nothing useful.")

    with patch("src.agents.failure_simulator.get_weather_risk", return_value={}), \
         patch("src.agents.failure_simulator.get_venue_info", return_value={}), \
         patch("src.agents.failure_simulator.get_artist_risk", return_value={}), \
         patch("src.agents.failure_simulator.assess_ticketing_risk", return_value={}), \
         patch("src.agents.failure_simulator.assess_logistics_risk", return_value={}):

        report = simulate_failures(mock_client, sample_event)

    assert report.scenarios == []
    assert report.has_critical is False
