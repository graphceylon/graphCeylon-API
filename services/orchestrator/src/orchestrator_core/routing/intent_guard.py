# services/orchestrator/src/orchestrator_core/routing/intent_guard.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple


_WEATHER_PAT = re.compile(r"\b(weather|forecast|rain|raining|temperature|temp|humidity|climate)\b", re.I)
_HOTEL_PAT = re.compile(r"\b(hotel|hotels|stay|accommodation|room|resort|villa|guesthouse|hostel)\b", re.I)
_VISA_PAT = re.compile(r"\b(visa|eta|passport|entry requirement|immigration)\b", re.I)

# Modify phrases should be explicit to route to modify_itinerary.
_MODIFY_PAT = re.compile(
    r"\b(modify|change|update|edit|remove|add|replace|swap|make it|set to|shift to)\b", re.I
)

_PRONOUN_REF_PAT = re.compile(r"\b(there|that place|that city|in that area|it)\b", re.I)


@dataclass(frozen=True)
class GuardDecision:
    forced_intent: Optional[str]
    reason: Optional[str]


def guard_intent(raw_text: str) -> GuardDecision:
    """
    High-precision lexical guard. This must run BEFORE session/trip logic.
    """
    t = (raw_text or "").strip().lower()

    # Hard domain locks
    if _WEATHER_PAT.search(t):
        return GuardDecision(forced_intent="forecast_weather", reason="lexical_guard:weather")
    if _VISA_PAT.search(t):
        return GuardDecision(forced_intent="info_visa_policy", reason="lexical_guard:visa")
    if _HOTEL_PAT.search(t):
        return GuardDecision(forced_intent="info_accommodation", reason="lexical_guard:accommodation")

    # No forced intent
    return GuardDecision(forced_intent=None, reason=None)


def allow_modify_itinerary(raw_text: str, parsed_intent: str, confidence: float) -> Tuple[bool, str]:
    """
    Production rule:
      - Only allow modify_itinerary if explicit modify language exists
        OR intent model is highly confident.
    """
    t = (raw_text or "").strip().lower()

    if _MODIFY_PAT.search(t):
        return True, "modify_gate:explicit_modify_phrase"

    if parsed_intent == "modify_itinerary" and confidence >= 0.90:
        return True, "modify_gate:high_confidence"

    return False, "modify_gate:blocked"