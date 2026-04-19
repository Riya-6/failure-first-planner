#!/usr/bin/env python
"""
Failure-First Live Music Event Planning Agent
Entry point — run from the project root:

    python run.py                                   # uses built-in demo event
    python run.py --event tests/fixtures/sample_events.json --key soundwave_outdoor
    python run.py --event my_event.json --output out/plan.json
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from src.models.event import LiveMusicEvent
from src.orchestrator.loop import run_failure_first_loop
from src.utils.logger import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Failure-First Live Music Event Planning Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--event",
        type=str,
        default=None,
        help=(
            "Path to a JSON file containing event data. "
            "Can be a single event object or a dict of named events "
            "(use --key to select which one)."
        ),
    )
    parser.add_argument(
        "--key",
        type=str,
        default=None,
        help="Key to select from a multi-event JSON file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write the output plan JSON. Defaults to assets/example_plans/<event_name>.json",
    )
    return parser.parse_args()


def load_event(event_path: str | None, key: str | None) -> LiveMusicEvent:
    if event_path is None:
        # Built-in demo event
        from datetime import date
        return LiveMusicEvent(
            name="SoundWave Festival 2025",
            venue="Griffith Park Amphitheater",
            venue_capacity=8000,
            headliner="Arctic Monkeys",
            supporting_acts=["Wet Leg", "Black Midi"],
            date=date(2025, 8, 15),
            is_outdoor=True,
            expected_attendance=7500,
            budget_usd=450_000,
            city="Los Angeles",
            backup_venue="Hollywood Bowl (Stage B)",
            notes="Annual flagship festival. Outdoor main stage.",
        )

    raw = json.loads(Path(event_path).read_text())

    if key:
        if key not in raw:
            print(f"ERROR: Key '{key}' not found in {event_path}.")
            print(f"Available keys: {list(raw.keys())}")
            sys.exit(1)
        raw = raw[key]

    return LiveMusicEvent(**raw)


def resolve_output_path(plan_event_name: str, output_arg: str | None) -> Path:
    if output_arg:
        path = Path(output_arg)
    else:
        safe_name = plan_event_name.lower().replace(" ", "_").replace("/", "_")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = Path(f"assets/example_plans/{safe_name}_{timestamp}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main() -> None:
    configure_logging()
    args = parse_args()

    # Load event
    try:
        event = load_event(args.event, args.key)
    except Exception as exc:
        print(f"ERROR loading event: {exc}")
        sys.exit(1)

    print(f"\n[*] Failure-First Planner -- {event.name}")
    print(f"    Venue    : {event.venue}, {event.city}")
    print(f"    Date     : {event.date}")
    print(f"    Headliner: {event.headliner}")
    print(f"    Outdoor  : {event.is_outdoor}")
    print(f"    Budget   : ${event.budget_usd:,.0f}\n")

    # Run the agent loop
    plan = run_failure_first_loop(event)

    # Save output
    output_path = resolve_output_path(event.name, args.output)
    output_path.write_text(plan.model_dump_json(indent=2))

    print(f"\n[>] Plan saved to: {output_path}")
    print(f"\n{'-' * 55}")
    print(f"  SUMMARY")
    print(f"{'-' * 55}")
    print(plan.summary)
    print(f"\n  Iterations taken    : {plan.iterations_taken}")
    print(f"  Failures surfaced   : {plan.total_failures_surfaced}")
    print(f"  Timeline entries    : {len(plan.timeline)}")
    print(f"  Go/No-Go checkpoints: {len(plan.go_no_go_checkpoints)}")
    print(f"  Risk register items : {len(plan.risk_register)}")

    if plan.backup_options.venue:
        print(f"\n  Backup venue    : {plan.backup_options.venue}")
    if plan.backup_options.headliner:
        print(f"  Backup headliner: {plan.backup_options.headliner}")
    print()


if __name__ == "__main__":
    main()
