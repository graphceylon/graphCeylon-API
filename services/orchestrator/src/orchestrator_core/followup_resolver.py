from __future__ import annotations
from typing import Any, Dict, List
import os, json
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("ENTITY_LLM_MODEL", "llama-3.3-70b-versatile").strip()

FIELD_MAP = {
    "destination_city": "city",
    "origin_city": "origin_city",
    "start_date": "start_date",
    "end_date": "end_date",
    "travel_month": "travel_month",
}

def resolve_followup(
    *,
    user_text: str,
    missing_fields: List[str],
    current_entities: Dict[str, Any] | None = None,
    current_prefs: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    current_entities = dict(current_entities or {})
    current_prefs = dict(current_prefs or {})

    want_keys = [FIELD_MAP.get(f, f) for f in (missing_fields or [])]

    if not GROQ_API_KEY or not user_text.strip() or not want_keys:
        return {"entities": {}, "preference_overrides": {}}

    system = (
        "You are a strict slot-filling extractor for a Sri Lanka travel planner.\n"
        "The user is answering a follow-up question.\n"
        "Extract ONLY the requested fields.\n"
        "Do NOT invent values. If unclear, output null.\n"
        "Return ONLY JSON: {\"entities\": {...}, \"preference_overrides\": {...}}"
    )

    schema = {"entities": {k: None for k in want_keys}, "preference_overrides": {}}

    prompt_obj = {
        "missing_fields": missing_fields,
        "requested_entity_keys": want_keys,
        "user_answer": user_text,
        "current_entities": current_entities,
        "current_prefs": current_prefs,
        "output_schema": schema,
        "notes": [
            "If user provides a city name like 'Kandy', set entities.city.",
            "If user provides relative dates like 'next week', convert to ISO dates if possible, else set travel_month.",
        ],
    }

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(prompt_obj, ensure_ascii=False)},
            ],
            "temperature": 0,
        },
        timeout=15,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    data = json.loads(content)

    entities = data.get("entities") or {}
    prefs = data.get("preference_overrides") or {}

    # map back if model returned destination_city instead of city etc.
    # (optional safety)
    cleaned = {}
    for k, v in entities.items():
        if v in (None, "", [], {}, "unknown"):
            continue
        cleaned[k] = v

    return {"entities": cleaned, "preference_overrides": prefs}