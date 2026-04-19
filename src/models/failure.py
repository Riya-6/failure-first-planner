from pydantic import BaseModel, Field
from enum import Enum


class FailureSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def _missing_(cls, value):
        """Accept uppercase variants e.g. 'CRITICAL' → FailureSeverity.CRITICAL."""
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower():
                    return member
        return None


class FailureScenario(BaseModel):
    """A single failure mode identified by the failure simulation agent."""

    title: str
    description: str
    severity: FailureSeverity
    root_cause: str
    affected_components: list[str] = Field(
        ...,
        description="e.g. ['artist', 'ticketing', 'venue']",
    )
    probability: float = Field(..., ge=0.0, le=1.0)
    mitigation: str = Field(default="", description="Preventive action (pre-event)")
    contingency: str = Field(default="", description="Reactive action (during event)")


class FailureReport(BaseModel):
    """Output of one failure simulation pass."""

    event_name: str
    scenarios: list[FailureScenario]
    iteration: int
    weather_risk: dict = Field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for s in self.scenarios if s.severity == FailureSeverity.CRITICAL)

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0
