"""
Failure Simulator Agent.

Calls Claude with failure-first prompting to surface the top failure
scenarios for a live music event. Enriches the event context with
real tool data (weather, venue, artist, ticketing, logistics) before
asking Claude to reason about failure.
"""
import json
import logging
import openai

from src.models.event import LiveMusicEvent
from src.models.failure import FailureScenario, FailureReport
from src.prompts.failure_first import SYSTEM_PROMPT, FAILURE_SIMULATION_PROMPT
from src.tools.weather_checker import get_weather_risk
from src.tools.venue_lookup import get_venue_info
from src.tools.artist_registry import get_artist_risk
from src.tools.ticketing import assess_ticketing_risk
from src.tools.logistics import assess_logistics_risk
from src.utils.config import Config

logger = logging.getLogger(__name__)


def _enrich_event(event: LiveMusicEvent) -> dict:
    """
    Builds a rich context dict by combining event fields with live tool data.
    All tool failures are caught and logged — never crash the agent.
    """
    base = event.model_dump(mode="json")

    try:
        base["weather_forecast"] = get_weather_risk(
            event.city, str(event.date), event.is_outdoor
        )
    except Exception as exc:
        logger.warning(f"Weather tool failed: {exc}")
        base["weather_forecast"] = {}

    try:
        base["venue_info"] = get_venue_info(event.venue, event.city)
    except Exception as exc:
        logger.warning(f"Venue tool failed: {exc}")
        base["venue_info"] = {}

    try:
        base["artist_risk"] = get_artist_risk(event.headliner)
    except Exception as exc:
        logger.warning(f"Artist tool failed: {exc}")
        base["artist_risk"] = {}

    try:
        base["ticketing_risk"] = assess_ticketing_risk(
            event.city, str(event.date),
            event.expected_attendance, event.venue_capacity,
        )
    except Exception as exc:
        logger.warning(f"Ticketing tool failed: {exc}")
        base["ticketing_risk"] = {}

    try:
        base["logistics_risk"] = assess_logistics_risk(event)
    except Exception as exc:
        logger.warning(f"Logistics tool failed: {exc}")
        base["logistics_risk"] = {}

    return base


def _parse_scenarios(raw_text: str) -> list[FailureScenario]:
    """Extract and parse scenarios from the JSON object response."""
    try:
        data = json.loads(raw_text)
        items = data.get("scenarios", data) if isinstance(data, dict) else data
        scenarios = []
        for item in items:
            try:
                scenarios.append(FailureScenario(**item))
            except Exception as exc:
                logger.warning(f"Skipping invalid scenario {item}: {exc}")
        return scenarios
    except (json.JSONDecodeError, Exception) as exc:
        logger.error(f"Failed to parse failure scenarios: {exc}\nRaw:\n{raw_text[:500]}")
        return []


def simulate_failures(
    client: openai.OpenAI,
    event: LiveMusicEvent,
    iteration: int = 1,
    enriched: dict | None = None,
) -> FailureReport:
    """
    Runs a single failure simulation pass against the event.

    Args:
        client:    OpenAI client instance.
        event:     The live music event to analyse.
        iteration: Current loop iteration number (for logging).

    Returns:
        FailureReport containing parsed FailureScenario objects.
    """
    if enriched is None:
        logger.info(f"[Iteration {iteration}] Enriching event context with tool data...")
        enriched = _enrich_event(event)

    prompt = FAILURE_SIMULATION_PROMPT.format(
        event_json=json.dumps(enriched, indent=2, default=str)
    )

    logger.info(f"[Iteration {iteration}] Calling OpenAI for failure simulation...")

    response = client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        max_completion_tokens=32768,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    raw = response.choices[0].message.content or ""
    logger.debug(
        f"[Iteration {iteration}] Tokens — "
        f"in: {response.usage.prompt_tokens}, out: {response.usage.completion_tokens}"
    )

    scenarios = _parse_scenarios(raw)
    weather_risk = enriched.get("weather_forecast", {})

    report = FailureReport(
        event_name=event.name,
        scenarios=scenarios,
        iteration=iteration,
        weather_risk=weather_risk,
    )

    logger.info(
        f"[Iteration {iteration}] Found {len(scenarios)} scenarios "
        f"({report.critical_count} critical)."
    )
    return report
