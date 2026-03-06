from __future__ import annotations
from typing import Any, Dict, List, Optional
import os, json
import requests
from datetime import date, timedelta
import re

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("ENTITY_LLM_MODEL", "llama-3.3-70b-versatile").strip()
FIELD_MAP = {
    "destination_city": "city",
    "origin_city": "origin_city",
    "start_date": "start_date",
    "end_date": "end_date",
    "travel_month": "travel_month",
}

# ✅ NEW: deterministic relative date resolver
def _resolve_relative_date(text: str) -> Optional[str]:
    t = (text or "").strip().lower()
    today = date.today()

    # already ISO
    m = re.match(r"(\d{4}-\d{2}-\d{2})", t)
    if m:
        return m.group(1)

    if t in {"today"}:
        return today.isoformat()
    if t in {"tomorrow"}:
        return (today + timedelta(days=1)).isoformat()
    if t in {"this weekend", "weekend"}:
        days_ahead = 5 - today.weekday()  # Saturday
        if days_ahead <= 0:
            days_ahead += 7
        return (today + timedelta(days=days_ahead)).isoformat()
    if "next week" in t and "monday" not in t:
        return (today + timedelta(weeks=1) - timedelta(days=today.weekday())).isoformat()

    # next <weekday>
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    }
    for day_name, day_num in weekdays.items():
        if day_name in t:
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).isoformat()

    # month names: "april 2026", "next april"
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for month_name, month_num in months.items():
        if month_name in t:
            year_match = re.search(r"\b(202\d)\b", t)
            year = int(year_match.group(1)) if year_match else today.year
            if year == today.year and month_num < today.month:
                year += 1
            return date(year, month_num, 1).isoformat()

    return None


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
        "For dates, ALWAYS convert to ISO format YYYY-MM-DD.\n"
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
        "today_date": date.today().isoformat(),   # ✅ give LLM anchor for relative dates
        "notes": [
            "If user provides a city name like 'Kandy', set entities.city.",
            "If user provides relative dates like 'next monday', convert to ISO YYYY-MM-DD using today_date as anchor.",
            "If user provides 'next week', set start_date to next Monday's date.",
            "If user provides a number of days like '3 days' or just '3', set entities.days as an integer.",
        ],
    }

    try:
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
    except Exception as e:
        print(f"[resolve_followup] LLM call failed: {e}")
        data = {"entities": {}, "preference_overrides": {}}

    entities = data.get("entities") or {}
    prefs = data.get("preference_overrides") or {}

    cleaned = {}
    for k, v in entities.items():
        if v in (None, "", [], {}, "unknown"):
            continue
        cleaned[k] = v

    # ✅ Safety net: if LLM didn't resolve date fields, do it deterministically
    for date_field in ("start_date", "end_date"):
        if date_field not in cleaned or not cleaned.get(date_field):
            # check if user_text itself looks like a date reference
            if date_field in want_keys:
                resolved = _resolve_relative_date(user_text)
                if resolved:
                    cleaned[date_field] = resolved

        # also fix if LLM returned a non-ISO string like "next monday"
        elif isinstance(cleaned.get(date_field), str):
            val = cleaned[date_field]
            if not re.match(r"\d{4}-\d{2}-\d{2}", val):
                resolved = _resolve_relative_date(val)
                if resolved:
                    cleaned[date_field] = resolved

    return {"entities": cleaned, "preference_overrides": prefs}