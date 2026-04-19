"""
Ticketing risk tool.
Estimates overselling risk, fraud exposure, and competing event density.
Uses Ticketmaster for competing events; rest is heuristic-based.
"""
import logging
import httpx
from src.utils.config import Config

logger = logging.getLogger(__name__)


def assess_ticketing_risk(
    city: str,
    event_date: str,
    expected_attendance: int,
    venue_capacity: int,
) -> dict:
    """
    Assess ticketing-related failure risks.

    Returns a dict with:
        - oversell_risk: risk level if expected > 95% capacity
        - competing_events: number of other events same day in city
        - fraud_risk: heuristic based on event size
        - recommendations: list of actionable suggestions
    """
    recommendations: list[str] = []
    fill_rate = expected_attendance / venue_capacity

    # Oversell risk
    if fill_rate >= 1.0:
        oversell_risk = "critical"
        recommendations.append("Expected attendance equals capacity — no safety buffer.")
    elif fill_rate >= 0.95:
        oversell_risk = "high"
        recommendations.append("Attendance is 95%+ of capacity — implement strict access control.")
    elif fill_rate >= 0.85:
        oversell_risk = "medium"
        recommendations.append("High fill rate — deploy additional entry scanners.")
    else:
        oversell_risk = "low"

    # Fraud risk heuristic: large shows attract more counterfeit tickets
    if expected_attendance > 5000:
        fraud_risk = "high"
        recommendations.append(
            "Large event — use NFC/RFID tickets and deploy fraud detection scanners."
        )
    elif expected_attendance > 1000:
        fraud_risk = "medium"
        recommendations.append("Mid-size event — enable barcode re-validation on entry.")
    else:
        fraud_risk = "low"

    # Competing events (Ticketmaster, optional)
    competing_events = _get_competing_event_count(city, event_date)
    if competing_events and competing_events > 3:
        recommendations.append(
            f"{competing_events} competing events on the same date — "
            "expect transport congestion and shared audience."
        )

    return {
        "fill_rate": round(fill_rate, 2),
        "oversell_risk": oversell_risk,
        "fraud_risk": fraud_risk,
        "competing_events": competing_events,
        "recommendations": recommendations,
    }


def _get_competing_event_count(city: str, event_date: str) -> int | None:
    """Returns the count of events on the same date in the same city via Ticketmaster."""
    if not Config.TICKETMASTER_API_KEY:
        return None

    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "city": city,
        "startDateTime": f"{event_date}T00:00:00Z",
        "endDateTime": f"{event_date}T23:59:00Z",
        "apikey": Config.TICKETMASTER_API_KEY,
        "size": 1,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        return data.get("page", {}).get("totalElements", 0)
    except httpx.HTTPError as exc:
        logger.warning(f"Could not fetch competing events: {exc}")
        return None
