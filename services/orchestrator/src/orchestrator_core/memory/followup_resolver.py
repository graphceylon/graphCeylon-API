# services/orchestrator/src/orchestrator_core/memory/followup_resolver.py

from __future__ import annotations
import re
from typing import Any, Dict, Tuple
from src.api.schemas import ParsedIntent

from .session_state import SessionState


CITY_CHANGE_RE = re.compile(r"\b(change|switch)\s+(it\s+)?to\s+(?P<city>[A-Za-z ]{2,})\b", re.I)
DAYS_RE = re.compile(r"\b(?P<days>\d+)\s*day(s)?\b", re.I)

HISTORY_HINTS = {"history", "historical", "heritage", "museum", "temple"}
FAMILY_HINTS = {"family", "kids", "child", "children"}
FOOD_HINTS = {"food", "eat", "restaurant", "cafe", "cafes", "street food"}
BEACH_HINTS = {"beach", "sea", "coast"}


def _dictify(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if isinstance(obj, dict):
        return {k: v for k, v in obj.items() if v is not None}
    return {}


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip().lower() in {"", "unknown", "any"}:
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def _merge_slots(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})
    for k, v in (patch or {}).items():
        if _is_empty(v):
            continue
        out[k] = v
    return out


def _infer_tags(text: str) -> list[str]:
    t = (text or "").lower()
    tags = []
    if any(w in t for w in HISTORY_HINTS):
        tags.append("history")
    if any(w in t for w in FAMILY_HINTS):
        tags.append("family")
    if any(w in t for w in FOOD_HINTS):
        tags.append("food")
    if any(w in t for w in BEACH_HINTS):
        tags.append("beach")
    return tags


def resolve_followup(
    *,
    user_text: str,
    parsed_intent: ParsedIntent,
    state: SessionState,
) -> Tuple[ParsedIntent, Dict[str, Any]]:
    """
    Returns:
      updated ParsedIntent (entities filled)
      session_state_patch (what changed)
    """
    patch: Dict[str, Any] = {"slots": {}}
    text = (user_text or "").strip()

    ents = _dictify(parsed_intent.entities)

    # (1) explicit edits
    m = CITY_CHANGE_RE.search(text)
    if m:
        city = (m.group("city") or "").strip()
        if city:
            ents["city"] = city
            patch["slots"]["city"] = city

    m2 = DAYS_RE.search(text)
    if m2:
        try:
            days = int(m2.group("days"))
            if days > 0:
                ents["days"] = days
                patch["slots"]["days"] = days
        except Exception:
            pass

    # (2) carry-over missing slots from state
    carry_keys = [
        "city", "region", "country",
        "origin", "destination", "nationality_country",
        "start_date", "end_date", "travel_month",
        "days", "budget_level", "max_price_lkr",
        "accommodation_type", "min_star_rating", "max_star_rating",
    ]
    for k in carry_keys:
        if _is_empty(ents.get(k)) and k in (state.slots or {}):
            ents[k] = state.slots.get(k)

    # (3) tags merge
    existing_tags = ents.get("tags") or []
    if not isinstance(existing_tags, list):
        existing_tags = []
    inferred = _infer_tags(text)
    combined = list(dict.fromkeys([*existing_tags, *inferred]))
    if combined:
        ents["tags"] = combined
        patch["slots"]["tags"] = combined

    # update parsed_intent.entities
    updated_intent = parsed_intent.model_copy(update={"entities": ents})

    # apply patch into state
    if patch["slots"]:
        state.slots = _merge_slots(state.slots, patch["slots"])

    return updated_intent, patch
