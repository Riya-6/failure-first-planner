"""
Logistics risk tool.
Heuristic assessment of stage, sound, security, and supply chain failure risks.
"""
from src.models.event import LiveMusicEvent


def assess_logistics_risk(event: LiveMusicEvent) -> dict:
    """
    Produces a heuristic logistics risk profile for a live music event.

    Covers: stage/rigging, sound system, security staffing,
    generator redundancy, and catering supply chain.
    """
    risks: list[dict] = []
    recommendations: list[str] = []

    # ── Security staffing ──────────────────────────────────────────────────
    # Industry standard: 1 security per 100 attendees minimum
    min_security = event.expected_attendance // 100
    risks.append({
        "area": "security_staffing",
        "minimum_required": min_security,
        "note": f"Minimum {min_security} security staff for {event.expected_attendance} attendees.",
    })
    recommendations.append(
        f"Book at least {min_security} licensed security staff. "
        "Add 20% buffer for no-shows."
    )

    # ── Generator redundancy ───────────────────────────────────────────────
    if event.is_outdoor:
        risks.append({
            "area": "generator",
            "risk": "high",
            "note": "Outdoor events rely entirely on generator power.",
        })
        recommendations.append(
            "Contract a backup generator (min. equal capacity to primary). "
            "Test both 48hrs before event."
        )

    # ── Stage rigging ──────────────────────────────────────────────────────
    if event.venue_capacity > 2000:
        risks.append({
            "area": "stage_rigging",
            "risk": "medium",
            "note": "Large-capacity events require certified structural inspection.",
        })
        recommendations.append(
            "Engage a certified rigger for pre-event structural sign-off. "
            "Document with photos."
        )

    # ── Sound system ──────────────────────────────────────────────────────
    risks.append({
        "area": "sound_system",
        "risk": "medium" if event.venue_capacity > 3000 else "low",
        "note": "PA failure at peak moment is the most common tech failure at live events.",
    })
    recommendations.append(
        "Contract primary and backup PA vendor. "
        "Conduct full soundcheck 4hrs before doors open."
    )

    # ── Catering & supply chain ────────────────────────────────────────────
    if event.expected_attendance > 3000:
        risks.append({
            "area": "catering",
            "risk": "medium",
            "note": "Large events are exposed to single-vendor catering collapse.",
        })
        recommendations.append(
            "Use minimum 3 independent catering vendors. "
            "Confirm delivery windows in writing 72hrs before."
        )

    overall = "high" if any(r.get("risk") == "high" for r in risks) else "medium"

    return {
        "overall_logistics_risk": overall,
        "risks": risks,
        "recommendations": recommendations,
    }
