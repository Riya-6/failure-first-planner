"""
Plan quality scorer.

Evaluates the *soundness* of a RobustPlan — not just whether fields exist,
but whether the plan actually addresses the right failures with real actions
and clear ownership.

Metrics (all 0–100):
  critical_resolution        — CRITICAL failures addressed at CRITICAL/HIGH in risk register
  severity_weighted_coverage — severity-weighted coverage of the full failure space
  owner_specificity          — named, non-generic owners in timeline + risk register
  contingency_depth          — substantive contingency actions in the timeline
  overall                    — weighted composite (35/30/20/15)
"""
import math
from src.models.plan import RobustPlan, PlanScore

# Severity → integer weight (higher = more dangerous)
_SEVERITY_WEIGHT: dict[str, int] = {
    "critical": 4,
    "high":     3,
    "medium":   2,
    "low":      1,
}

# Owner strings that indicate the AI gave a generic placeholder
_GENERIC_OWNER_TOKENS = {
    "", "tbd", "n/a", "none", "-", "na",
    "team", "staff", "vendor", "contractor",
    "organizer", "organiser", "management",
    "production", "the team", "event team",
}


def _sev_weight(severity: str) -> int:
    return _SEVERITY_WEIGHT.get(str(severity).strip().lower(), 1)


def _is_specific_owner(owner: str) -> bool:
    """True if the owner looks like a real person or company name."""
    cleaned = owner.strip().lower()
    if cleaned in _GENERIC_OWNER_TOKENS:
        return False
    # catch "production team", "security staff", etc.
    for token in ("team", "staff", "crew", "department", "dept"):
        if cleaned.endswith(token):
            return False
    return len(cleaned) >= 3


def _has_deep_contingency(contingency: str) -> bool:
    """True if the contingency is a substantive action, not a placeholder."""
    stripped = contingency.strip().lower()
    if stripped in ("", "n/a", "tbd", "none", "-", "na"):
        return False
    return len(stripped) > 20


def compute_scores(plan: RobustPlan) -> PlanScore:
    scenarios = plan.failure_scenarios
    risk_reg  = plan.risk_register
    timeline  = plan.timeline

    # ── 1. Critical Resolution Rate ──────────────────────────────────────────
    # Of the CRITICAL failures the agent surfaced, how many are represented
    # by a CRITICAL or HIGH entry in the risk register?
    # A high ratio means the plan correctly escalated its most dangerous findings.
    critical_failures = [s for s in scenarios if str(s.severity).lower() == "critical"]
    risk_critical_high = [r for r in risk_reg if r.severity.upper() in ("CRITICAL", "HIGH")]

    if critical_failures:
        critical_resolution = min(
            math.floor(len(risk_critical_high) / len(critical_failures) * 100), 100
        )
    elif risk_reg:
        # No critical failures found — plan is dealing with manageable risks
        critical_resolution = 80
    else:
        critical_resolution = 0

    # ── 2. Severity-Weighted Coverage ────────────────────────────────────────
    # Each failure scenario has a severity weight. Each risk register entry
    # also has a weight. Score = min(Σ risk weights / Σ failure weights, 1).
    # This rewards plans that concentrate risk entries on the high-severity failures
    # rather than padding with low-severity items.
    total_failure_weight = sum(_sev_weight(s.severity) for s in scenarios) or 1
    total_risk_weight    = sum(_sev_weight(r.severity) for r in risk_reg)

    severity_weighted_coverage = min(
        math.floor(total_risk_weight / total_failure_weight * 100), 100
    )

    # ── 3. Owner Specificity ─────────────────────────────────────────────────
    # Generic owners ("the team", "TBD") are not actionable. We measure
    # what fraction of timeline entries and risk register entries name a
    # real contractor, person, or company.
    all_owners = [e.owner for e in timeline] + [r.owner for r in risk_reg]
    if all_owners:
        specific_count = sum(1 for o in all_owners if _is_specific_owner(o))
        owner_specificity = math.floor(specific_count / len(all_owners) * 100)
    else:
        owner_specificity = 0

    # ── 4. Contingency Depth ─────────────────────────────────────────────────
    # A good plan doesn't just list what to do — it says what to do *if it
    # fails*. We check whether contingency fields are substantive (> 20 chars,
    # not "N/A"), signalling real fallback thinking rather than boilerplate.
    if timeline:
        deep_count = sum(1 for e in timeline if _has_deep_contingency(e.contingency))
        contingency_depth = math.floor(deep_count / len(timeline) * 100)
    else:
        contingency_depth = 0

    # ── Overall (weighted composite) ─────────────────────────────────────────
    overall = math.floor(
        critical_resolution        * 0.35
        + severity_weighted_coverage * 0.30
        + owner_specificity          * 0.20
        + contingency_depth          * 0.15
    )

    return PlanScore(
        overall=overall,
        critical_resolution=critical_resolution,
        severity_weighted_coverage=severity_weighted_coverage,
        owner_specificity=owner_specificity,
        contingency_depth=contingency_depth,
    )
