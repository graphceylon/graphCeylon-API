from __future__ import annotations

import re
from typing import Any, Dict, Optional

from ...api.schemas import ParsedIntent, Entities
from ..memory.session_state import SessionState


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


class ConversationManager:
    """
    Conservative conversation layer.

    Responsibilities:
      1) Continue a pending follow-up when the user gives a short slot-like reply
      2) Force modify_itinerary only for true edit-style turns on an active trip
      3) Merge session slots into missing entities/prefs
      4) NEVER hijack a strong explicit intent from the classifier/router
    """

    LOW_SIGNAL_INTENTS = {"smalltalk", "out_of_scope", "generic_fact_query"}
    STRONG_INTENT_THRESHOLD = 0.80
    WEAK_INTENT_THRESHOLD = 0.55

    EDIT_HINTS = [
        "make it", "change it", "update it", "edit it", "modify it",
        "cheaper", "more budget", "luxury", "with family", "solo",
        "add", "remove", "shorter", "longer", "2 days", "3 days", "4 days",
        "next week", "this weekend", "tomorrow", "next month",
        "day 1", "day 2", "day 3",
    ]

    SLOTY_REPLY_PATTERNS = [
        re.compile(r"^\d+\s+days?$", re.I),
        re.compile(r"^(kandy|ella|galle|sigiriya|nuwara eliya|colombo|south coast)$", re.I),
        re.compile(r"^(solo|family|friends|couple)$", re.I),
        re.compile(r"^(low|mid|medium|high|budget|luxury)$", re.I),
        re.compile(r"^(this weekend|next week|tomorrow|next month|april 2026|may 2026|june 2026)$", re.I),
        re.compile(r"^\d{4}-\d{2}-\d{2}$", re.I),
    ]

    CONTINUATION_HINTS = [
        "there", "that", "that place", "that one", "same trip",
        "same place", "same hotel", "same date", "same dates",
        "continue", "go on",
    ]

    EXPLICIT_INTENT_KEYWORDS = {
        "forecast_weather": ["weather", "forecast", "rain", "temperature", "climate"],
        "info_transport": ["transport", "bus", "train", "taxi", "route", "how to go"],
        "info_accommodation": ["hotel", "hotels", "stay", "accommodation", "room", "rooms"],
        "book_hotel": ["book hotel", "reserve hotel", "booking", "check in", "check out"],
        "info_visa_policy": ["visa", "eta", "entry requirement", "entry requirements"],
        "recommend_restaurants": ["restaurant", "restaurants", "food", "eat", "dining", "where to eat"],
        "recommend_pois": ["places to visit", "what to do", "recommend places", "things to do"],
        "info_attraction": ["attraction", "attractions", "historical", "temple", "museum", "site", "sites"],
        "plan_itinerary": ["plan a trip", "plan trip", "itinerary", "plan itinerary"],
        "modify_itinerary": ["make it", "change it", "update it", "edit it", "modify it"],
    }

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

        # 1) If the current turn clearly signals a real intent, trust the classifier/router.
        #    Do NOT override with session context.
        if self._has_explicit_intent_signal(raw, primary):
            if active_trip_id and self._looks_like_modify(raw) and primary != "modify_itinerary":
                return self._override_intent(parsed_intent, "modify_itinerary", active_trip_id=active_trip_id)
            return parsed_intent

        if primary not in self.LOW_SIGNAL_INTENTS and conf >= self.STRONG_INTENT_THRESHOLD:
            if active_trip_id and self._looks_like_modify(raw) and primary != "modify_itinerary":
                return self._override_intent(parsed_intent, "modify_itinerary", active_trip_id=active_trip_id)
            return parsed_intent

        # 2) Pending follow-up: only continue pending intent for short slot-like replies.
        if pending_intent and self._looks_like_slot_reply(raw):
            return self._override_intent(parsed_intent, pending_intent, active_trip_id=active_trip_id)

        # 3) Active trip + edit-like text => modify itinerary.
        if active_trip_id and self._looks_like_modify(raw):
            return self._override_intent(parsed_intent, "modify_itinerary", active_trip_id=active_trip_id)

        # 4) Only use active_intent for truly weak/vague continuation turns.
        if active_intent and self._should_continue_active_intent(
            raw=raw,
            primary=primary,
            conf=conf,
            pending_intent=bool(pending_intent),
        ):
            return self._override_intent(parsed_intent, active_intent, active_trip_id=active_trip_id)

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

    def _has_explicit_intent_signal(self, raw: str, primary: str) -> bool:
        words = self.EXPLICIT_INTENT_KEYWORDS.get(primary, [])
        return any(w in raw for w in words)

    def _looks_like_slot_reply(self, raw: str) -> bool:
        if len(raw.split()) <= 5 and not self._has_any_explicit_domain_keyword(raw):
            return True
        return any(p.match(raw) for p in self.SLOTY_REPLY_PATTERNS)

    def _should_continue_active_intent(
        self,
        *,
        raw: str,
        primary: str,
        conf: float,
        pending_intent: bool,
    ) -> bool:
        # Never steal turns that already have explicit domain wording.
        if self._has_any_explicit_domain_keyword(raw):
            return False

        # Only continue on truly vague/weak turns.
        if primary in self.LOW_SIGNAL_INTENTS:
            return True

        if conf < self.WEAK_INTENT_THRESHOLD and self._looks_like_continuation(raw):
            return True

        # Short ambiguous continuations like "there?", "what about that one?"
        if not pending_intent and len(raw.split()) <= 4 and self._looks_like_continuation(raw):
            return True

        return False

    def _has_any_explicit_domain_keyword(self, raw: str) -> bool:
        for words in self.EXPLICIT_INTENT_KEYWORDS.values():
            if any(w in raw for w in words):
                return True
        return False

    def _looks_like_continuation(self, raw: str) -> bool:
        return any(x in raw for x in self.CONTINUATION_HINTS)

    def _looks_like_modify(self, raw: str) -> bool:
        return any(x in raw for x in self.EDIT_HINTS)

    def _is_empty(self, v: Any) -> bool:
        return v in (None, "", [], {}, "unknown")