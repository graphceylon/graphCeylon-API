# orchestrator_core/handlers.py
from __future__ import annotations

from typing import Any, Dict
import httpx


async def h_extract_entities(task, ctx: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """
    In your current system, intent parsing already produces entities.
    This handler can:
    - normalize them
    - fill defaults
    - validate types
    - store final version in ctx["entities"]
    """
    parsed = ctx.get("parsed_intent") or {}
    entities = parsed.get("entities") or {}

    # small normalization example
    if "days" in entities and entities["days"] is not None:
        entities["days"] = int(entities["days"])

    if not entities.get("country"):
        entities["country"] = "Sri Lanka"

    ctx["entities"] = entities
    return {"ok": True, "entities": entities}


async def h_call_rec_itinerary(task, ctx: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls your recommender service itinerary endpoint.
    Store output in ctx so formatter can read it.
    """
    rec_url = ctx["config"]["RECOMMENDER_SERVICE_URL"].rstrip("/")
    entities = ctx.get("entities") or {}

    payload = {
        "user_id": ctx.get("user_id"),
        "session_id": ctx.get("session_id"),
        "intent": (ctx.get("parsed_intent") or {}).get("intent"),
        "entities": entities,
        "preference_overrides": (ctx.get("parsed_intent") or {}).get("preference_overrides", {}),
        "raw_text": (ctx.get("parsed_intent") or {}).get("raw_text"),
    }

    # 🔁 Change this path to your real endpoint
    endpoint = f"{rec_url}/itinerary/plan"

    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(endpoint, json=payload)
        r.raise_for_status()
        data = r.json()

    ctx["itinerary_result"] = data
    return data


async def h_format_response(task, ctx: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes whatever downstream produced and formats for user.
    Keep it simple: just wrap it nicely for now.
    """
    itinerary = ctx.get("itinerary_result")
    parsed = ctx.get("parsed_intent") or {}
    entities = ctx.get("entities") or {}

    if not itinerary:
        return {
            "ok": False,
            "message": "I couldn't generate an itinerary. Please try again.",
            "debug": {"intent": parsed.get("intent"), "entities": entities},
        }

    # Minimal formatting (you can move to ExplainabilityAgent later)
    return {
        "ok": True,
        "message": f"Here is your {entities.get('days', '?')}-day plan for {entities.get('city', 'your destination')}:",
        "itinerary": itinerary,
    }
