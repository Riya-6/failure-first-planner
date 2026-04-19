"""
Mitigation Agent.

Given a FailureReport, calls Claude to generate specific mitigation
(pre-event preventive) and contingency (day-of reactive) actions
for each failure scenario.
"""
import json
import logging
import openai

from src.models.failure import FailureReport, FailureScenario
from src.prompts.failure_first import MITIGATION_PROMPT
from src.utils.config import Config

logger = logging.getLogger(__name__)


def _parse_mitigations(raw_text: str, scenarios: list[FailureScenario]) -> list[dict]:
    """Parse mitigations from JSON object response."""
    try:
        data = json.loads(raw_text)
        items = data.get("mitigations", data) if isinstance(data, dict) else data
        return items if isinstance(items, list) else []
    except (json.JSONDecodeError, Exception) as exc:
        logger.error(f"Failed to parse mitigations: {exc}")
        return [{"title": s.title, "mitigation": "", "contingency": ""} for s in scenarios]


def generate_mitigations(
    client: openai.OpenAI,
    report: FailureReport,
) -> list[dict]:
    """
    Generate mitigation and contingency for every scenario in the report.

    Args:
        client: OpenAI client instance.
        report: FailureReport from the failure simulator.

    Returns:
        List of dicts: [{title, mitigation, contingency}, ...]
        Titles correspond 1-to-1 with report.scenarios.
    """
    if not report.scenarios:
        logger.warning("No scenarios to mitigate.")
        return []

    failures_json = json.dumps(
        [s.model_dump() for s in report.scenarios], indent=2
    )

    logger.info(
        f"[Iteration {report.iteration}] Generating mitigations for "
        f"{len(report.scenarios)} scenarios..."
    )

    response = client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        max_completion_tokens=32768,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": MITIGATION_PROMPT.format(failures_json=failures_json),
        }],
    )

    raw = response.choices[0].message.content or ""
    logger.debug(
        f"[Iteration {report.iteration}] Mitigation tokens — "
        f"in: {response.usage.prompt_tokens}, out: {response.usage.completion_tokens}"
    )

    mitigations = _parse_mitigations(raw, report.scenarios)
    logger.info(f"[Iteration {report.iteration}] Generated {len(mitigations)} mitigations.")
    return mitigations
