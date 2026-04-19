"""
Replanner Agent.

Generates the final robust event plan incorporating all failure
scenarios and mitigations from previous iterations. Uses
output_config effort="max" for the deepest possible reasoning.
"""
import json
import logging
import re
import openai

from src.models.event import LiveMusicEvent
from src.models.plan import (
    RobustPlan,
    TimelineEntry,
    GoNoGoCheckpoint,
    RiskEntry,
    BackupOptions,
)
from src.prompts.failure_first import REPLAN_PROMPT
from src.utils.config import Config
from src.utils.scorer import compute_scores

logger = logging.getLogger(__name__)


def _parse_plan(raw_text: str) -> dict:
    """Extract the JSON object from the replan response."""
    start = raw_text.find("{")
    end = raw_text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in replan response.")
    return json.loads(raw_text[start:end])


def _timeline_sort_key(entry: TimelineEntry) -> int:
    """
    Return an integer sort key so that timeline entries appear in
    chronological order — earliest preparation tasks first, day-of tasks last.

    Mapping (all in minutes, relative to event start):
      T-N days   → -(N * 1440)
      T-N weeks  → -(N * 10080)
      T-N hours  → -(N * 60)
      HH:MM      → minutes past midnight on event day (positive, 0–1439)
      fallback   → 0  (treated as day-of, unknown time)
    """
    t = entry.time.lower().strip()

    m = re.search(r"t[-–]\s*(\d+(?:\.\d+)?)\s*week", t)
    if m:
        return -int(float(m.group(1)) * 10080)

    m = re.search(r"t[-–]\s*(\d+(?:\.\d+)?)\s*day", t)
    if m:
        return -int(float(m.group(1)) * 1440)

    m = re.search(r"t[-–]\s*(\d+(?:\.\d+)?)\s*hour", t)
    if m:
        return -int(float(m.group(1)) * 60)

    m = re.search(r"(\d{1,2}):(\d{2})", t)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))

    return 0


def generate_robust_plan(
    client: openai.OpenAI,
    event: LiveMusicEvent,
    mitigations: list[dict],
    iterations_taken: int,
    total_failures: int,
    all_failure_scenarios: list = [],
) -> RobustPlan:
    """
    Produce a production-ready robust event plan.

    Args:
        client:           OpenAI client instance.
        event:            The live music event.
        mitigations:      All mitigations accumulated across iterations.
        iterations_taken: Number of failure-first iterations completed.
        total_failures:   Total failure scenarios surfaced.

    Returns:
        RobustPlan — the final structured plan ready for export.
    """
    logger.info("Generating final robust plan...")

    response = client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        max_completion_tokens=32768,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": REPLAN_PROMPT.format(
                event_json=json.dumps(
                    event.model_dump(mode="json"), indent=2, default=str
                ),
                mitigations_json=json.dumps(mitigations, indent=2),
            ),
        }],
    )

    raw = response.choices[0].message.content or ""
    logger.debug(
        f"Replan tokens — in: {response.usage.prompt_tokens}, "
        f"out: {response.usage.completion_tokens}"
    )

    if not raw:
        logger.error("Replan response was empty.")
        return RobustPlan(
            event_name=event.name,
            summary="Plan generation failed — empty response from model.",
            iterations_taken=iterations_taken,
            total_failures_surfaced=total_failures,
        )

    try:
        plan_data = _parse_plan(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error(f"Failed to parse replan response: {exc}\nRaw response:\n{raw[:1000]}")
        return RobustPlan(
            event_name=event.name,
            summary=raw[:500] if raw.strip() else "Plan generation failed — unparseable response.",
            iterations_taken=iterations_taken,
            total_failures_surfaced=total_failures,
        )

    # Parse nested structures — skip individual entries that fail validation
    timeline = []
    for entry in plan_data.get("timeline", []):
        if isinstance(entry, dict):
            try:
                timeline.append(TimelineEntry(**entry))
            except Exception as exc:
                logger.warning(f"Skipping invalid timeline entry {entry}: {exc}")

    checkpoints = []
    for cp in plan_data.get("go_no_go_checkpoints", []):
        if isinstance(cp, dict):
            try:
                checkpoints.append(GoNoGoCheckpoint(**cp))
            except Exception as exc:
                logger.warning(f"Skipping invalid checkpoint {cp}: {exc}")

    risk_register = []
    for r in plan_data.get("risk_register", []):
        if isinstance(r, dict):
            try:
                risk_register.append(RiskEntry(**r))
            except Exception as exc:
                logger.warning(f"Skipping invalid risk entry {r}: {exc}")
    backup_raw = plan_data.get("backup_options", {})
    backup_options = BackupOptions(**backup_raw) if isinstance(backup_raw, dict) else BackupOptions()

    # Sort timeline chronologically: T-60 days → T-7 days → T-48 hours → day-of steps
    timeline.sort(key=_timeline_sort_key)

    plan = RobustPlan(
        event_name=event.name,
        summary=plan_data.get("summary", ""),
        timeline=timeline,
        go_no_go_checkpoints=checkpoints,
        risk_register=risk_register,
        backup_options=backup_options,
        failure_scenarios=all_failure_scenarios,
        iterations_taken=iterations_taken,
        total_failures_surfaced=total_failures,
    )

    plan.score = compute_scores(plan)

    logger.info(
        f"Robust plan generated — "
        f"{len(timeline)} timeline entries, "
        f"{len(checkpoints)} go/no-go checkpoints, "
        f"{len(risk_register)} risk register entries."
    )
    return plan
