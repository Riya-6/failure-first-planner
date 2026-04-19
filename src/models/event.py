from pydantic import BaseModel, Field, model_validator
from typing import Optional
import datetime


class LiveMusicEvent(BaseModel):
    """Represents a live music event to be planned."""

    name: str = Field(..., description="Event/festival name")
    venue: str = Field(..., description="Venue name")
    venue_capacity: int = Field(..., gt=0, description="Maximum legal capacity")
    headliner: str = Field(..., description="Main headliner artist")
    supporting_acts: list[str] = Field(default_factory=list)
    date: datetime.date = Field(..., description="Event date (YYYY-MM-DD)")
    is_outdoor: bool = Field(..., description="True if the venue is outdoors")
    expected_attendance: int = Field(..., gt=0)
    budget_usd: float = Field(..., gt=0, description="Total event budget in USD")
    city: str = Field(..., description="City where event is held")
    backup_venue: Optional[str] = Field(None, description="Fallback venue if primary fails")

    # Contractors — optional but dramatically improve plan specificity
    sound_vendor: Optional[str] = Field(None, description="PA/sound company name")
    stage_company: Optional[str] = Field(None, description="Staging and rigging company")
    security_company: Optional[str] = Field(None, description="Security contractor")
    catering_vendor: Optional[str] = Field(None, description="Food and beverage contractor")
    medical_provider: Optional[str] = Field(None, description="First aid / medical provider")
    ticketing_platform: Optional[str] = Field(None, description="Ticketing platform e.g. Eventbrite")
    production_manager: Optional[str] = Field(None, description="Lead production manager name")

    notes: str = Field(default="", description="Any additional context")

    @model_validator(mode="after")
    def attendance_within_capacity(self) -> "LiveMusicEvent":
        if self.expected_attendance > self.venue_capacity:
            raise ValueError(
                f"expected_attendance ({self.expected_attendance}) "
                f"exceeds venue_capacity ({self.venue_capacity})"
            )
        return self
