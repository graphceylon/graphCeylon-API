from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Tuple

# If you have these in your codebase already, import them instead
from ..api.schemas import ParsedIntent, Entities  # adjust path if needed
from .memory.session_state import SessionState    # adjust path if needed


_PRONOUN_HINTS = {
    "there", "here", "it", "that", "that city", "this city", "that place", "this place"
}

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def _contains_pronoun_followup(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    # quick checks
    if any(p in t for p in _PRONOUN_HINTS):
        return True
    # "in that area", "go there", etc.
    if re.search(r"\b(go|stay|visit|plan)\s+(there|here)\b", t):
        return True
    return False


def _extract_days(text: str) -> Optional[int]:
    t = (text or "").lower()
    m = re.search(r"\b(\d{1,2})\s*day[s]?\b", t)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    # "make it two days" (tiny mapping)
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
    m2 = re.search(r"\b(make it|change to|update to)\s+(one|two|three|four|five|six|seven)\s*day[s]?\b", t)
    if m2:
        return words.get(m2.group(2))
    return None


def _normalize_next_month(base: date) -> Tuple[int, int]:
    y, m = base.year, base.month
    m += 1
    if m == 13:
        m = 1
        y += 1
    return y, m


def _parse_next_month_or_named_month(text: str, today: Optional[date] = None) -> Optional[Tuple[int, int]]:
    """
    Returns (year, month) if "next month" or "next March" detected, else None.
    """
    t = (text or "").strip().lower()
    if not t:
        return None
    today = today or date.today()

    if re.search(r"\bnext month\b", t):
        return _normalize_next_month(today)

    m = re.search(r"\bnext\s+([a-z]+)\b", t)
    if m:
        mm = _MONTHS.get(m.group(1))
        if mm:
            y = today.year
            # "next March" means next occurrence strictly after this month
            if mm <= today.month:
                y += 1
            return (y, mm)

    return None


def resolve_followup(
    *,
    user_text: str,
    parsed_intent: ParsedIntent,
    session_state: Optional[SessionState],
) -> ParsedIntent:
    """
    Minimal Phase-1 follow-up resolver:
    - pronoun followup: fill city from session active_place
    - "make it X days": if active_trip exists -> force modify_itinerary + set days
    - "next month/next March": normalize travel_month (or start_date if you want later)
    Returns patched ParsedIntent.
    """
    if not session_state:
        return parsed_intent

    text = (user_text or "").strip()
    if not text:
        return parsed_intent

    slots = session_state.slots or {}
    active_place = (slots.get("active_place") or slots.get("city") or "").strip() or None
    active_trip_id = (slots.get("active_trip_id") or "").strip() or None

    # current entities dict
    ents = parsed_intent.entities.model_dump(exclude_none=False)

    # -------------------------
    # 1) Pronoun-based city fill
    # -------------------------
    has_city = bool(ents.get("city") or ents.get("destination"))
    if (not has_city) and active_place and _contains_pronoun_followup(text):
        ents["city"] = active_place
        # keep destination aligned if your downstream expects it
        if not ents.get("destination"):
            ents["destination"] = active_place

    # -------------------------
    # 2) Days follow-up -> modify
    # -------------------------
    days = _extract_days(text)
    if days and active_trip_id:
        ents["days"] = days
        # convert to modify intent if user is adjusting an existing trip
        # (only if not already modify)
        if (parsed_intent.intent or "").strip().lower() != "modify_itinerary":
            parsed_intent = parsed_intent.model_copy(update={
                "intent": "modify_itinerary",
                "domain_category": "itinerary",
            })

    # -------------------------
    # 3) Next month / next March -> travel_month
    # -------------------------
    ym = _parse_next_month_or_named_month(text, today=date.today())
    if ym:
        y, m = ym
        # store as "YYYY-MM" (simple + stable)
        ents["travel_month"] = f"{y:04d}-{m:02d}"

    # return patched parsed_intent with patched entities
    return parsed_intent.model_copy(update={"entities": Entities(**ents)})