from __future__ import annotations

import re
from typing import Any, Dict, Optional

from ...api.schemas import ParsedIntent, Entities
from ..memory.session_state import SessionState


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


class ConversationManager:
    """
    Lightweight conversation-first layer.
    It does NOT replace the DAG.
    It only:
      1) repairs vague / continuation turns using session context
      2) merges session slots into current parsed entities/prefs
    """

    LOW_SIGNAL_INTENTS = {"smalltalk", "out_of_scope", "generic_fact_query"}

    EDIT_HINTS = [
        "make it", "change it", "update it", "edit it", "modify it",
        "cheaper", "more budget", "luxury", "with family", "solo",
        "add", "remove", "shorter", "longer", "2 days", "3 days", "4 days",
        "next week", "this weekend", "tomorrow", "next month",
    ]

    SLOTY_REPLY_PATTERNS = [
        re.compile(r"^\d+\s+days?$", re.I),
        re.compile(r"^(kandy|ella|galle|sigiriya|nuwara eliya|colombo|south coast)$", re.I),
        re.compile(r"^(solo|family|friends|couple)$", re.I),
        re.compile(r"^(low|mid|medium|high|budget|luxury)$", re.I),
        re.compile(r"^(this weekend|next week|tomorrow|next month|april 2026|may 2026)$", re.I),
    ]

    ENTITY_SLOT_KEYS = [
        "city",
        "region",
        "country",
        "origin",
        "destination",
        "origin_city",
        "start_date",
        "end_date",
        "travel_month",
        "days",
        "time_of_day",
        "num_travelers",
        "travel_with",
        "include_stops",
        "route_direction",
        "waypoints",
        "stop_durations_days",
        "budget_level",
        "nationality_country",
        "legal_service",
        "citizenship_type",
    ]

    PREF_SLOT_KEYS = [
        "travel_style",
        "avoid_crowds",
        "eco_preference",
        "activity_preference",
        "pace_preference",
        "adventure_level",
        "budget_level",
        "budget_per_night_lkr",
        "budget_flexibility",
        "preferred_transport",
        "food_preferences",
        "accessibility_needs",
        "walking_tolerance_minutes",
        "accommodation_type",
        "star_preference",
        "must_have_amenities",
        "cancellation_preference",
        "sun_sensitivity",
        "rain_preference",
        "temperature_preference",
        "motion_sickness",
    ]

    INTENT_TO_DOMAIN = {
        "plan_itinerary": "itinerary",
        "modify_itinerary": "itinerary",
        "info_transport": "transport",
        "info_accommodation": "hotel",
        "book_hotel": "hotel",
        "info_visa_policy": "visa",
        "forecast_weather": "weather",
        "recommend_pois": "attraction",
        "info_attraction": "attraction",
        "recommend_restaurants": "restaurant",
    }

    def repair_intent_with_context(
        self,
        *,
        parsed_intent: ParsedIntent,
        session_state: Optional[SessionState],
        user_text: str,
    ) -> ParsedIntent:
        if not session_state:
            return parsed_intent

        raw = _norm(user_text)
        slots = dict(session_state.slots or {})

        pending_intent = slots.get("pending_intent")
        active_intent = slots.get("active_intent")
        active_trip_id = slots.get("active_trip_id")
        primary = (parsed_intent.intent or "").strip()
        conf = float(parsed_intent.confidence or 0.0)

        # Case 1: user is answering a pending follow-up with a short slot-like reply
        if pending_intent and self._looks_like_slot_reply(raw):
            return self._override_intent(parsed_intent, pending_intent, active_trip_id=active_trip_id)

        # Case 2: user says something vague, but we are already inside an active intent
        if active_intent and (
            primary in self.LOW_SIGNAL_INTENTS or conf < 0.72 or self._looks_like_continuation(raw)
        ):
            return self._override_intent(parsed_intent, active_intent, active_trip_id=active_trip_id)

        # Case 3: active trip exists and user says a modifier -> force modify_itinerary
        if active_trip_id and self._looks_like_modify(raw):
            return self._override_intent(parsed_intent, "modify_itinerary", active_trip_id=active_trip_id)

        return parsed_intent

    def merge_session_slots_into_entities(
        self,
        *,
        parsed_intent: ParsedIntent,
        session_state: Optional[SessionState],
    ) -> ParsedIntent:
        if not session_state:
            return parsed_intent

        slots = dict(session_state.slots or {})
        ents = (
            parsed_intent.entities.model_dump(exclude_none=False)
            if hasattr(parsed_intent.entities, "model_dump")
            else dict(parsed_intent.entities or {})
        )

        prefs = (
            parsed_intent.preference_overrides.model_dump(exclude_none=False)
            if hasattr(parsed_intent.preference_overrides, "model_dump")
            else dict(parsed_intent.preference_overrides or {})
        )

        # Merge entities only when current turn doesn't already provide them
        for key in self.ENTITY_SLOT_KEYS:
            if self._is_empty(ents.get(key)) and not self._is_empty(slots.get(key)):
                ents[key] = slots.get(key)

        # Merge prefs only when missing in current turn
        for key in self.PREF_SLOT_KEYS:
            if self._is_empty(prefs.get(key)) and not self._is_empty(slots.get(key)):
                prefs[key] = slots.get(key)

        return parsed_intent.model_copy(
            update={
                "entities": Entities(**ents),
                "preference_overrides": prefs,
            }
        )

    def update_session_from_turn(
        self,
        *,
        parsed_intent: ParsedIntent,
        session_state: Optional[SessionState],
    ) -> None:
        if not session_state:
            return

        session_state.slots["active_intent"] = parsed_intent.intent
        session_state.slots["active_domain"] = parsed_intent.domain_category

        ents = (
            parsed_intent.entities.model_dump(exclude_none=True)
            if hasattr(parsed_intent.entities, "model_dump")
            else dict(parsed_intent.entities or {})
        )
        prefs = (
            parsed_intent.preference_overrides.model_dump(exclude_none=True)
            if hasattr(parsed_intent.preference_overrides, "model_dump")
            else dict(parsed_intent.preference_overrides or {})
        )

        for key in self.ENTITY_SLOT_KEYS:
            val = ents.get(key)
            if not self._is_empty(val):
                session_state.slots[key] = val

        for key in self.PREF_SLOT_KEYS:
            val = prefs.get(key)
            if not self._is_empty(val):
                session_state.slots[key] = val

    def _override_intent(
        self,
        parsed_intent: ParsedIntent,
        intent_name: str,
        *,
        active_trip_id: Optional[str] = None,
    ) -> ParsedIntent:
        scores = dict(parsed_intent.scores or {})
        scores[intent_name] = max(float(scores.get(intent_name, 0.0)), 0.95)

        ents = (
            parsed_intent.entities.model_dump(exclude_none=False)
            if hasattr(parsed_intent.entities, "model_dump")
            else dict(parsed_intent.entities or {})
        )

        if intent_name == "modify_itinerary" and active_trip_id:
            ents["itinerary_id"] = active_trip_id

        return parsed_intent.model_copy(
            update={
                "intent": intent_name,
                "domain_category": self.INTENT_TO_DOMAIN.get(intent_name, parsed_intent.domain_category),
                "confidence": float(scores[intent_name]),
                "scores": scores,
                "entities": Entities(**ents),
            }
        )

    def _looks_like_slot_reply(self, raw: str) -> bool:
        if len(raw.split()) <= 5:
            return True
        return any(p.match(raw) for p in self.SLOTY_REPLY_PATTERNS)

    def _looks_like_continuation(self, raw: str) -> bool:
        return (
            len(raw.split()) <= 8
            or any(x in raw for x in ["instead", "also", "not that", "change", "update", "make it"])
        )

    def _looks_like_modify(self, raw: str) -> bool:
        return any(x in raw for x in self.EDIT_HINTS)

    def _is_empty(self, v: Any) -> bool:
        return v in (None, "", [], {}, "unknown")