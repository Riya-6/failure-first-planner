from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from src.models.failure import FailureScenario


class TimelineEntry(BaseModel):
    time: str = Field(..., description="e.g. 'T-30 days' or '14:00 day-of'")
    action: str
    owner: str
    contingency: str = ""


class GoNoGoCheckpoint(BaseModel):
    checkpoint: str
    criteria: str
    fallback: str


class RiskEntry(BaseModel):
    risk: str
    severity: str
    owner: str
    mitigation: str


class BackupOptions(BaseModel):
    venue: str = ""
    headliner: str = ""
    sound_vendor: str = ""
    generator: str = ""

    @field_validator("venue", "headliner", "sound_vendor", "generator", mode="before")
    @classmethod
    def coerce_to_string(cls, v):
        if isinstance(v, dict):
            return v.get("name") or v.get("venue") or str(v)
        return v or ""


class PlanScore(BaseModel):
    """Evaluation metrics for the soundness of the generated plan (0–100 scale)."""

    overall: int = Field(..., ge=0, le=100, description="Weighted composite quality score")
    critical_resolution: int = Field(..., ge=0, le=100, description="% of CRITICAL failures addressed at CRITICAL/HIGH level in risk register")
    severity_weighted_coverage: int = Field(..., ge=0, le=100, description="Severity-weighted fraction of failure space covered by risk register")
    owner_specificity: int = Field(..., ge=0, le=100, description="% of timeline + risk entries with a named, non-generic owner")
    contingency_depth: int = Field(..., ge=0, le=100, description="% of timeline steps with a substantive contingency action")


class RobustPlan(BaseModel):
    """Final output of the Failure-First Planning Agent."""

    event_name: str
    summary: str
    timeline: list[TimelineEntry] = Field(default_factory=list)
    go_no_go_checkpoints: list[GoNoGoCheckpoint] = Field(default_factory=list)
    risk_register: list[RiskEntry] = Field(default_factory=list)
    backup_options: BackupOptions = Field(default_factory=BackupOptions)
    failure_scenarios: list[FailureScenario] = Field(default_factory=list)
    score: PlanScore | None = None
    iterations_taken: int
    total_failures_surfaced: int
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
