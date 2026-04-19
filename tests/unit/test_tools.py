"""Unit tests for the tool layer (all external HTTP calls mocked)."""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from src.models.event import LiveMusicEvent
from src.tools.weather_checker import get_weather_risk
from src.tools.ticketing import assess_ticketing_risk
from src.tools.logistics import assess_logistics_risk


# ── Weather tool ──────────────────────────────────────────────────────────────

def test_weather_indoor_returns_none_risk():
    result = get_weather_risk("London", "2025-09-20", is_outdoor=False)
    assert result["risk_level"] == "none"
    assert result["precipitation_mm"] == 0


def test_weather_outdoor_geocode_failure_returns_unknown():
    with patch("src.tools.weather_checker._geocode", return_value=None):
        result = get_weather_risk("Atlantis", "2025-08-01", is_outdoor=True)
    assert result["risk_level"] == "unknown"


def test_weather_outdoor_high_wind_returns_critical():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "daily": {
            "precipitation_sum": [2.0],
            "windspeed_10m_max": [80.0],
            "weathercode": [0],
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch("src.tools.weather_checker._geocode", return_value=(34.05, -118.24)), \
         patch("httpx.Client") as mock_http:
        mock_http.return_value.__enter__.return_value.get.return_value = mock_response
        result = get_weather_risk("Los Angeles", "2025-08-15", is_outdoor=True)

    assert result["risk_level"] == "critical"
    assert result["wind_kmh"] == 80.0


def test_weather_api_failure_returns_unknown():
    import httpx
    with patch("src.tools.weather_checker._geocode", return_value=(51.5, -0.1)), \
         patch("httpx.Client") as mock_http:
        mock_http.return_value.__enter__.return_value.get.side_effect = (
            httpx.HTTPError("timeout")
        )
        result = get_weather_risk("London", "2025-09-20", is_outdoor=True)

    assert result["risk_level"] == "unknown"


# ── Ticketing tool ────────────────────────────────────────────────────────────

def test_ticketing_low_fill_rate():
    result = assess_ticketing_risk("London", "2025-09-20", 500, 1500)
    assert result["fill_rate"] == 0.33
    assert result["oversell_risk"] == "low"


def test_ticketing_near_capacity_raises_high_risk():
    result = assess_ticketing_risk("London", "2025-09-20", 1480, 1500)
    assert result["oversell_risk"] in ("high", "critical")


def test_ticketing_at_capacity_is_critical():
    result = assess_ticketing_risk("LA", "2025-08-15", 8000, 8000)
    assert result["oversell_risk"] == "critical"


def test_ticketing_large_event_fraud_risk():
    result = assess_ticketing_risk("LA", "2025-08-15", 6000, 10000)
    assert result["fraud_risk"] == "high"


# ── Logistics tool ────────────────────────────────────────────────────────────

@pytest.fixture
def outdoor_event() -> LiveMusicEvent:
    return LiveMusicEvent(
        name="Test", venue="Park", venue_capacity=8000,
        headliner="Band", date=date(2025, 8, 1),
        is_outdoor=True, expected_attendance=7000,
        budget_usd=200_000, city="London",
    )


@pytest.fixture
def indoor_event() -> LiveMusicEvent:
    return LiveMusicEvent(
        name="Test", venue="Club", venue_capacity=500,
        headliner="DJ", date=date(2025, 9, 1),
        is_outdoor=False, expected_attendance=450,
        budget_usd=10_000, city="Berlin",
    )


def test_logistics_outdoor_has_generator_risk(outdoor_event):
    result = assess_logistics_risk(outdoor_event)
    areas = [r["area"] for r in result["risks"]]
    assert "generator" in areas


def test_logistics_indoor_no_generator_risk(indoor_event):
    result = assess_logistics_risk(indoor_event)
    areas = [r["area"] for r in result["risks"]]
    assert "generator" not in areas


def test_logistics_large_event_has_catering_risk(outdoor_event):
    result = assess_logistics_risk(outdoor_event)
    areas = [r["area"] for r in result["risks"]]
    assert "catering" in areas


def test_logistics_recommendations_not_empty(outdoor_event):
    result = assess_logistics_risk(outdoor_event)
    assert len(result["recommendations"]) > 0
