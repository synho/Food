"""
User context model (API input). All fields optional; more context = more accurate, safer guidance.
Standardized field names per docs/API_AND_SERVER.md and docs/USER_CONTEXT_AND_COLLECTION.md.
"""
from typing import Optional
from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """User profile for recommendations and health map. None = not provided."""

    age: Optional[int] = Field(None, description="User age")
    gender: Optional[str] = Field(None, description="'male', 'female', or 'other'")
    ethnicity: Optional[str] = None
    # Place & lifestyle (standardized names)
    location: Optional[str] = Field(None, description="Place of living: country, region, or city")
    way_of_living: Optional[str] = Field(None, description="Lifestyle: activity level, work pattern, cooking access")
    culture: Optional[str] = Field(None, description="Dietary culture: e.g. vegetarian, halal, Mediterranean")
    # Health
    conditions: Optional[list[str]] = Field(default_factory=list, description="Current diseases/conditions (canonical names preferred)")
    symptoms: Optional[list[str]] = Field(default_factory=list, description="Current symptoms")
    medications: Optional[list[str]] = Field(default_factory=list, description="Current medications (for interaction checks)")
    goals: Optional[list[str]] = Field(default_factory=list, description="e.g. longevity, weight_management, hypertension_management")
    # Optional
    timezone: Optional[str] = None
    season: Optional[str] = None
