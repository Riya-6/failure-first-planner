"""
Weather risk tool using the free Open-Meteo API.
No API key required. Geocodes city via Nominatim (OpenStreetMap).
"""
import logging
import httpx

logger = logging.getLogger(__name__)


def _geocode(city: str) -> tuple[float, float] | None:
    """Returns (latitude, longitude) for a city name, or None on failure."""
    try:
        from geopy.geocoders import Nominatim
        geo = Nominatim(user_agent="failure-first-planner/1.0")
        location = geo.geocode(city, timeout=10)
        if location:
            return location.latitude, location.longitude
    except Exception as exc:
        logger.warning(f"Geocoding failed for '{city}': {exc}")
    return None


def get_weather_risk(city: str, event_date: str, is_outdoor: bool) -> dict:
    """
    Assess weather-related failure risk for an event.

    Args:
        city:        City name (e.g. "Los Angeles").
        event_date:  Event date as ISO string "YYYY-MM-DD".
        is_outdoor:  True if the venue is outdoors.

    Returns:
        dict with keys: risk_level, precipitation_mm, wind_kmh, reasons.
    """
    if not is_outdoor:
        return {
            "risk_level": "none",
            "precipitation_mm": 0,
            "wind_kmh": 0,
            "reasons": ["Indoor venue — weather risk not applicable."],
        }

    coords = _geocode(city)
    if not coords:
        logger.warning(f"Could not geocode '{city}'. Using unknown risk.")
        return {
            "risk_level": "unknown",
            "precipitation_mm": None,
            "wind_kmh": None,
            "reasons": [f"Could not determine location for '{city}'."],
        }

    lat, lon = coords
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum,windspeed_10m_max,weathercode",
        "start_date": event_date,
        "end_date": event_date,
        "timezone": "auto",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error(f"Weather API call failed: {exc}")
        return {
            "risk_level": "unknown",
            "precipitation_mm": None,
            "wind_kmh": None,
            "reasons": ["Weather API unavailable."],
        }

    daily = data.get("daily", {})
    precip = (daily.get("precipitation_sum") or [0])[0] or 0.0
    wind = (daily.get("windspeed_10m_max") or [0])[0] or 0.0

    risk_level = "low"
    reasons: list[str] = []

    if precip > 5:
        risk_level = "medium"
        reasons.append(f"Rain forecast: {precip}mm — cover for stage/equipment required.")
    if precip > 15:
        risk_level = "high"
        reasons.append("Heavy rain — outdoor stage drainage and waterproofing critical.")
    if wind > 50:
        risk_level = "high"
        reasons.append(f"High winds: {wind} km/h — tent and rigging inspection required.")
    if wind > 70:
        risk_level = "critical"
        reasons.append(
            f"Dangerous winds: {wind} km/h — exceeds stage rigging safety threshold. "
            "Consider cancellation or indoor relocation."
        )

    if not reasons:
        reasons.append("No significant weather risk detected.")

    return {
        "risk_level": risk_level,
        "precipitation_mm": precip,
        "wind_kmh": wind,
        "reasons": reasons,
    }
