# src/db/models/user_preferences.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import func

from src.db.session import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    # --- Core identity ---
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)  # from auth/orchestrator
    username = Column(String, nullable=True)

    # --- Basic profile ---
    age = Column(Integer, nullable=True)
    country_of_origin = Column(String, nullable=True)
    is_domestic = Column(Boolean, nullable=False, default=False)

    # --- Travel style ---
    travel_interests = Column(ARRAY(String), nullable=False, default=list)
    travel_pace = Column(String, nullable=True)              # relaxed / moderate / packed
    destination_types = Column(ARRAY(String), nullable=False, default=list)

    # --- Weather & crowd ---
    sun_sensitivity = Column(String, nullable=True)          # low / medium / high
    rain_preference = Column(String, nullable=True)          # avoid_rain / dont_care / enjoy_rain
    temperature_preference = Column(String, nullable=True)   # cool / mild / hot
    crowd_tolerance = Column(String, nullable=True)          # low / medium / high

    # --- Food & diet ---
    diet_type = Column(String, nullable=True)                # vegan / veg / halal / etc.
    food_preferences = Column(ARRAY(String), nullable=False, default=list)
    food_strictness = Column(String, nullable=True)          # strict / flexible

    # --- Budget ---
    budget_level = Column(String, nullable=True)             # budget / mid / luxury

    # --- Accessibility & safety ---
    accessibility_needs = Column(String, nullable=True)      # wheelchair / low_mobility / etc.
    preferred_transport = Column(ARRAY(String), nullable=False, default=list)
    avoid_stray_animals = Column(Boolean, nullable=False, default=False)
    motion_sickness = Column(Boolean, nullable=False, default=False)

    # --- Compact JSON preference vector ---
    pref_vector = Column(JSONB, nullable=False, default=dict)

    # --- Audit fields ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
