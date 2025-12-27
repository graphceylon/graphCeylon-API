from __future__ import annotations

from typing import Optional, List, Literal, Dict, Any
from pydantic import Field

from .base import BaseSchema


PartyType = Literal["solo", "couple", "family", "friends", "unknown"]
BudgetLevel = Literal["low", "mid", "high", "unknown"]

ActivityPreference = Literal["outdoor", "indoor", "mixed", "unknown"]
PacePreference = Literal["relaxed", "balanced", "packed", "unknown"]
AdventureLevel = Literal["low", "medium", "high", "unknown"]

AccommodationType = Literal[
    "hotel", "resort", "villa", "guesthouse", "hostel", "eco_lodge", "homestay", "any"
]
Amenity = Literal["wifi", "ac", "pool", "breakfast", "parking", "gym", "spa", "family_rooms"]

StarPreference = Literal["any", "3_star_plus", "4_star_plus", "5_star_only"]
CancellationPreference = Literal["flexible", "strict", "any"]

RainPreference = Literal["avoid_rain", "ok_with_rain", "prefer_rain", "unknown"]
TempPreference = Literal["cool", "moderate", "warm", "unknown"]
SensitivityLevel = Literal["low", "medium", "high", "unknown"]



class UserIdentity(BaseSchema):
    user_id: str = Field(...)
    username: Optional[str] = Field(default=None)
    full_name: Optional[str] = Field(default=None)


class UserDemographics(BaseSchema):
    country: Optional[str] = Field(default=None, description="User's home country / nationality country")
    date_of_birth: Optional[str] = Field(
        default=None,
        description="ISO date YYYY-MM-DD (store as string to avoid timezone issues)"
    )


class UserLanguages(BaseSchema):
    primary_language: Optional[str] = Field(default=None, description="e.g., 'en', 'si', 'ta'")
    secondary_languages: List[str] = Field(default_factory=list, description="e.g., ['si','ta']")


class PreferenceOverrides(BaseSchema):
    # Trip style / scoring
    travel_style: List[str] = Field(default_factory=list, description="e.g., ['nature','culture']")
    avoid_crowds: Optional[bool] = Field(default=None)
    eco_preference: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    activity_preference: Optional[ActivityPreference] = Field(default="unknown")
    pace_preference: Optional[PacePreference] = Field(default="unknown")
    adventure_level: Optional[AdventureLevel] = Field(default="unknown")

    # Budget (keep coarse + add actionable numeric)
    budget_level: Optional[BudgetLevel] = Field(default=None)
    budget_per_night_lkr: Optional[int] = Field(default=None, ge=0, description="Hotel budget per night (LKR)")
    budget_flexibility: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="0=strict, 1=flexible")

    # Transport / food / accessibility
    preferred_transport: List[str] = Field(default_factory=list, description="e.g., ['train','car']")
    food_preferences: List[str] = Field(default_factory=list, description="e.g., ['halal','veg']")
    accessibility_needs: Optional[List[str]] = Field(default=None, description="e.g., ['wheelchair']")
    walking_tolerance_minutes: Optional[int] = Field(default=None, ge=0, le=600)

    # Accommodation preferences (HotelAgent-critical)
    accommodation_type: AccommodationType = Field(default="any")
    star_preference: StarPreference = Field(default="any")
    must_have_amenities: List[Amenity] = Field(default_factory=list)
    cancellation_preference: CancellationPreference = Field(default="any")

    # Weather tolerance
    sun_sensitivity: Optional[SensitivityLevel] = Field(default=None)
    rain_preference: Optional[RainPreference] = Field(default=None)
    temperature_preference: Optional[TempPreference] = Field(default=None)

    # Optional constraints (keep only if you will actually use them)
    motion_sickness: Optional[bool] = Field(default=None, description="Only used if route planning supports it")


class OnboardingQuestionnaire(BaseSchema):
    questionnaire_version: int = Field(default=1)
    completed: bool = Field(default=False)

    # Store raw answers in a flexible dict so you can change questions without DB migrations.
    # You can still add typed fields later if you want.
    answers: Dict[str, Any] = Field(default_factory=dict)

    completed_at_iso: Optional[str] = Field(default=None)


class ProfileEvent(BaseSchema):
    event_type: Literal["saved_poi", "disliked_poi", "completed_trip", "feedback"] = Field(...)
    payload: Dict[str, Any] = Field(default_factory=dict)
    ts_iso: Optional[str] = Field(default=None)


class UserProfile(BaseSchema):
    # identity + basic info
    identity: UserIdentity = Field(...)
    demographics: UserDemographics = Field(default_factory=UserDemographics)
    languages: UserLanguages = Field(default_factory=UserLanguages)

    # travel defaults
    home_city: Optional[str] = Field(default=None)
    default_party: PartyType = Field(default="unknown")
    budget_level: BudgetLevel = Field(default="unknown")

    # onboarding + preferences
    onboarding: OnboardingQuestionnaire = Field(default_factory=OnboardingQuestionnaire)
    preference_overrides: PreferenceOverrides = Field(default_factory=PreferenceOverrides)

    # activity log
    events: List[ProfileEvent] = Field(default_factory=list)

    updated_at_iso: Optional[str] = Field(default=None)
    profile_version: int = Field(default=1)


class ProfilePatch(BaseSchema):
    source: Optional[Literal["user_text", "onboarding", "explicit_settings", "system"]] = Field(default="user_text")

    # identity / demographics / language updates
    username: Optional[str] = Field(default=None)
    full_name: Optional[str] = Field(default=None)

    country: Optional[str] = Field(default=None)
    date_of_birth: Optional[str] = Field(default=None)

    primary_language: Optional[str] = Field(default=None)
    secondary_languages: Optional[List[str]] = Field(default=None)

    # travel defaults
    home_city: Optional[str] = Field(default=None)
    default_party: Optional[PartyType] = Field(default=None)
    budget_level: Optional[BudgetLevel] = Field(default=None)

    # preferences
    preference_overrides: Optional[PreferenceOverrides] = Field(default=None)

    # onboarding
    onboarding: Optional[OnboardingQuestionnaire] = Field(default=None)
