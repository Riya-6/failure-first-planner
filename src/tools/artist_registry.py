"""
Artist history tool using the Setlist.fm API.
Looks up past cancellations and touring history as failure risk signals.
Falls back to stub data when SETLISTFM_API_KEY is not set.
"""
import logging
import httpx
from src.utils.config import Config

logger = logging.getLogger(__name__)


def get_artist_risk(artist_name: str) -> dict:
    """
    Assess artist-related failure risk based on touring history.

    Args:
        artist_name: Artist or band name.

    Returns:
        dict with cancellation signals and touring frequency.
    """
    if not Config.SETLISTFM_API_KEY:
        logger.info("SETLISTFM_API_KEY not set — returning stub artist data.")
        return {
            "status": "stub",
            "artist": artist_name,
            "note": "Set SETLISTFM_API_KEY in .env for real cancellation history.",
            "recent_shows": "unknown",
            "cancellation_signals": [],
        }

    url = "https://api.setlist.fm/rest/1.0/search/setlists"
    headers = {
        "x-api-key": Config.SETLISTFM_API_KEY,
        "Accept": "application/json",
    }
    params = {"artistName": artist_name, "p": 1}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error(f"Setlist.fm API error: {exc}")
        return {"status": "error", "artist": artist_name, "error": str(exc)}

    setlists = data.get("setlist", [])
    recent_shows = len(setlists)

    # Simple heuristic: fewer than 3 shows in recent results may indicate
    # infrequent touring or hiatus — flag as a moderate cancellation risk
    signals = []
    if recent_shows == 0:
        signals.append("No recent setlists found — artist may be inactive.")
    elif recent_shows < 3:
        signals.append(f"Only {recent_shows} recent shows found — infrequent touring.")

    return {
        "status": "found",
        "artist": artist_name,
        "recent_shows": recent_shows,
        "cancellation_signals": signals,
    }
