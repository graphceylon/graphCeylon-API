from __future__ import annotations
from typing import Any, Dict, Tuple, Optional

from .normalize import clean_dict, pick, is_present

DOC_MAX_CHARS = 900  # keep short for embeddings


def _truncate(s: str, n: int = DOC_MAX_CHARS) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 3] + "..."


def build_doc(event_type: str, intent: Optional[str], payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    payload = payload or {}
    meta: Dict[str, Any] = {"intent": intent, "event_type": event_type}

    if event_type == "intent_parsed":
        entities = clean_dict(payload.get("entities") or payload.get("extracted_entities") or {})
        overrides = clean_dict(payload.get("query_preference_overrides") or payload.get("preference_overrides") or {})

        city = entities.get("city") or entities.get("destination")
        days = entities.get("days")
        max_budget = entities.get("max_trip_budget_lkr") or entities.get("budget")

        # pull important overrides only (don’t dump everything)
        key_overrides = pick(overrides, [
            "travel_style", "food_preferences", "budget_level", "avoid_crowds",
            "eco_preference", "pace_preference", "accommodation_type"
        ])

        meta.update({
            "city": city,
            "days": days,
            "max_trip_budget_lkr": max_budget,
            **key_overrides
        })

        parts = [f"Intent={intent}"]
        if is_present(city): parts.append(f"city={city}")
        if is_present(days): parts.append(f"days={days}")
        if is_present(max_budget): parts.append(f"max_budget_lkr={max_budget}")
        if key_overrides: parts.append(f"overrides={key_overrides}")

        return _truncate(". ".join(parts)), meta

    if event_type == "prefs_merged":
        merged = clean_dict(payload.get("merged_prefs") or {})
        sources = clean_dict(payload.get("preference_sources") or {})

        # keep only stable/important fields
        key_prefs = pick(merged, [
            "city", "destination", "days",
            "travel_style", "food_preferences", "budget_level", "avoid_crowds",
            "eco_preference", "pace_preference", "accommodation_type",
            "preferred_transport", "budget_per_night_lkr", "max_trip_budget_lkr"
        ])

        meta.update({
            **key_prefs,
            "preference_sources": sources
        })

        doc = f"Merged prefs for {intent}. prefs={key_prefs}"
        return _truncate(doc), meta

    if event_type == "downstream_response":
        endpoint = payload.get("endpoint")
        ok = payload.get("ok")
        # IMPORTANT: your downstream event stores full "response". Do NOT embed it.
        # only store short summary keys if present
        summary = payload.get("summary") or payload.get("message") or ""
        meta.update({"endpoint": endpoint, "ok": ok})

        doc = f"Downstream {endpoint} ok={ok}"
        if is_present(summary):
            doc += f". summary={summary}"
        return _truncate(doc), meta

    # fallback
    return _truncate(f"Event {event_type} intent={intent}"), meta
