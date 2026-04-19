"""
Venue metadata tool using the Ticketmaster Discovery API.
Falls back to stub data when TICKETMASTER_API_KEY is not set.
"""
import logging
import httpx
from src.utils.config import Config

logger = logging.getLogger(__name__)

_STUB = {
    "status": "stub",
    "note": "Set TICKETMASTER_API_KEY in .env for real venue data.",
}


def get_venue_info(venue_name: str, city: str) -> dict:
    """
    Fetch venue metadata (capacity, address, accessibility).

    Args:
        venue_name: Name of the venue to look up.
        city:       City to narrow the search.

    Returns:
        dict with venue metadata, or stub data if API key not configured.
    """
    if not Config.TICKETMASTER_API_KEY:
        logger.info("TICKETMASTER_API_KEY not set — returning stub venue data.")
        return {
            **_STUB,
            "name": venue_name,
            "city": city,
            "capacity": "unknown",
            "accessible": "unknown",
            "parking_spaces": "unknown",
        }

    url = "https://app.ticketmaster.com/discovery/v2/venues.json"
    params = {
        "keyword": venue_name,
        "city": city,
        "apikey": Config.TICKETMASTER_API_KEY,
        "size": 1,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error(f"Ticketmaster API error: {exc}")
        return {**_STUB, "name": venue_name, "error": str(exc)}

    venues = data.get("_embedded", {}).get("venues", [])
    if not venues:
        return {"name": venue_name, "status": "not_found", "city": city}

    v = venues[0]
    return {
        "status": "found",
        "name": v.get("name"),
        "address": v.get("address", {}).get("line1"),
        "city": v.get("city", {}).get("name"),
        "capacity": v.get("upcomingEvents", {}).get("_total", "unknown"),
        "accessible": v.get("accessibleSeatingDetail") is not None,
        "url": v.get("url"),
    }
