# src/recommendation/user_profile.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class UserProfile:
    """
    Runtime user preference object used by the recommendation engine.
    Built from:
      - long-term preferences in Postgres (UserPreference row)
      - per-request overrides from Orchestrator payload
    """
    user_id: str
    username: Optional[str] = None

    # Basic info
    age: Optional[int] = None
    country_of_origin: Optional[str] = None
    is_domestic: bool = False

    # Main preference vector (from pref_vector + overrides)
    tag_weights: Dict[str, float] = field(default_factory=dict)

    # Budget & crowd
    budget_level: Optional[str] = None            # "budget" | "mid" | "luxury"
    crowd_tolerance: Optional[str] = None         # "low" | "medium" | "high" | "avoid_crowds"
    avoid_crowds: bool = False                    # derived or override

    # Weather / comfort
    sun_sensitivity: Optional[str] = None         # "low" | "medium" | "high"
    rain_preference: Optional[str] = None         # "avoid_rain" | "dont_care" | "enjoy_rain"
    temperature_preference: Optional[str] = None  # "cool" | "mild" | "hot"

    # Food & diet
    diet_type: Optional[str] = None
    food_preferences: List[str] = field(default_factory=list)

    # Accessibility & transport
    accessibility_needs: Optional[str] = None
    preferred_transport: List[str] = field(default_factory=list)
    avoid_stray_animals: bool = False
    motion_sickness: bool = False
