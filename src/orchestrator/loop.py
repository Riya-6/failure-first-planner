"""
Failure-First Orchestrator Loop.

Coordinates the full multi-agent pipeline:
  1. Simulate failures (failure_simulator)
  2. Generate mitigations (mitigation_agent)
  3. Replan with mitigations (replanner)
  4. Repeat until no critical failures remain or max_iterations hit.
"""
import logging
import openai

from src.models.event import LiveMusicEvent
from src.models.plan import RobustPlan
from src.agents.failure_simulator import simulate_failures, _enrich_event
from src.agents.mitigation_agent import generate_mitigations
from src.agents.replanner import generate_robust_plan
from src.utils.config import Config
from src.utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


def run_failure_first_loop(event: LiveMusicEvent) -> RobustPlan:
    """
    Run the full Failure-First Planning Agent loop for a live music event.

    Args:
        event: The live music event to plan.

    Returns:
        RobustPlan — the final hardened event plan.
    """
    Config.validate()

    client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
    cost = CostTracker()
    max_iterations = Config.MAX_LOOP_ITERATIONS

    all_failures = []
    all_mitigations = []
    mitigated_titles: set[str] = set()

    logger.info(f"{'═' * 60}")
    logger.info(f"  Failure-First Planner — {event.name}")
    logger.info(f"  Venue: {event.venue} | Date: {event.date} | Outdoor: {event.is_outdoor}")
    logger.info(f"  Max iterations: {max_iterations}")
    logger.info(f"{'═' * 60}")

    # Enrich event context once — weather/venue/artist data doesn't change between iterations
    logger.info("Enriching event context with tool data (once)...")
    enriched = _enrich_event(event)

    for iteration in range(1, max_iterations + 1):
        logger.info(f"\n{'─' * 50}")
        logger.info(f"  ITERATION {iteration}/{max_iterations}")
        logger.info(f"{'─' * 50}")

        # ── Phase 1: Failure Simulation ────────────────────────────────────
        report = simulate_failures(client, event, iteration=iteration, enriched=enriched)
        all_failures.extend(report.scenarios)

        # ── Phase 2: Mitigation Generation — only for new scenarios ───────
        new_scenarios = [s for s in report.scenarios if s.title not in mitigated_titles]
        report.scenarios = new_scenarios
        mitigations = generate_mitigations(client, report)
        all_mitigations.extend(mitigations)
        mitigated_titles.update(s.title for s in new_scenarios)

        # ── Early Exit Check ───────────────────────────────────────────────
        if not report.has_critical:
            logger.info(
                f"\n✓ No critical failures in iteration {iteration}. "
                "Plan is sufficiently robust. Proceeding to final plan."
            )
            break

        if iteration == max_iterations:
            logger.warning(
                f"\n⚠ Reached max iterations ({max_iterations}) with "
                f"{report.critical_count} unresolved critical failure(s)."
            )
        else:
            logger.info(
                f"\n↻ {report.critical_count} critical failure(s) remain. "
                "Running another iteration."
            )

    # ── Phase 3: Final Robust Plan ─────────────────────────────────────────
    logger.info(f"\n{'═' * 60}")
    logger.info("  Generating Final Robust Plan")
    logger.info(f"{'═' * 60}")

    plan = generate_robust_plan(
        client=client,
        event=event,
        mitigations=all_mitigations,
        iterations_taken=iteration,
        total_failures=len(all_failures),
        all_failure_scenarios=all_failures,
    )

    logger.info(f"\n{'═' * 60}")
    logger.info(f"  ✅ Complete")
    logger.info(f"  Iterations:        {plan.iterations_taken}")
    logger.info(f"  Failures surfaced: {plan.total_failures_surfaced}")
    logger.info(f"  Timeline entries:  {len(plan.timeline)}")
    logger.info(f"  Go/no-go checks:   {len(plan.go_no_go_checkpoints)}")
    logger.info(f"  Risk register:     {len(plan.risk_register)}")
    logger.info(f"{'═' * 60}\n")

    return plan
