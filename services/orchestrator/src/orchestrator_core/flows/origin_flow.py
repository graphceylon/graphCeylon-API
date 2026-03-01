# orchestrator_core/flows/origin_flow.py
from __future__ import annotations
import re
from typing import Optional, Tuple

UNKNOWN_ORIGIN_SET = {
    "idk", "i don't know", "dont know", "not sure", "no idea",
    "skip", "ignore", "whatever", "any", "unknown",
}

def is_unknown_origin(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in UNKNOWN_ORIGIN_SET

def looks_like_place_answer(text: str) -> bool:
    """
    Very simple heuristic:
    - short-ish text, no question mark
    - not obviously a new request
    """
    t = (text or "").strip()
    if not t:
        return False
    if "?" in t:
        return False
    if len(t) > 40:
        return False
    # if it contains planning verbs, it's likely not just an origin answer
    if re.search(r"\b(plan|create|build|generate|recommend|show|weather|visa|hotel)\b", t.lower()):
        return False
    return True

def consume_pending_origin(
    *,
    pending_clarification: Optional[str],
    user_text: str,
    parsed_intent_name: str,
) -> Tuple[bool, Optional[str], bool]:
    """
    Returns:
      consumed: did we consume this message as origin handling?
      origin_city: origin value if provided; None if unknown/ignored
      cleared_pending: should clear pending clarification?
    """
    if pending_clarification != "origin_city":
        return (False, None, False)

    raw = (user_text or "").strip()

    # 1) explicit unknown/skip
    if is_unknown_origin(raw):
        return (True, None, True)

    # 2) if user is asking a different intent now, treat as "ignored"
    if parsed_intent_name not in {"plan_itinerary", "modify_itinerary"}:
        return (True, None, True)

    # 3) treat as origin answer only if it looks like a place answer
    if looks_like_place_answer(raw):
        return (True, raw, True)

    # otherwise: still not usable, keep pending (don’t clear)
    return (True, None, False)