# orchestrator_core/entity_extractor.py

from __future__ import annotations

import json
import logging
import re
import os
import subprocess
import requests
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import calendar
from datetime import datetime, timedelta
from .llm.factory import build_llm_client


load_dotenv() 

logger = logging.getLogger(__name__)
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# ENTITY_LLM_PROVIDER = os.getenv("ENTITY_LLM_PROVIDER", "groq")
# logger.warning(f"GROQ_API_KEY loaded? {bool(GROQ_API_KEY)}")
# logger.warning(f"ENTITY_LLM_PROVIDER={ENTITY_LLM_PROVIDER}")
# print("GROQ_API_KEY loaded?", bool(GROQ_API_KEY))
# print("GROQ_API_KEY repr:", repr(GROQ_API_KEY))
# print("ENTITY_LLM_PROVIDER:", ENTITY_LLM_PROVIDER)




# ---- 1. Base prompt for Mistral via Ollama ----

BASE_PROMPT = """
You are an information extractor for a tourism assistant for Sri Lanka.

Given ONE user query, extract:
- domain_category (STATIC fixed category)
- entities
- preference_overrides

Return ONLY valid JSON with this exact structure:

{
  "domain_category": string|null,    // MUST be one of:
                                     // "attraction", "hotel", "restaurant",
                                     // "transport", "visa", "weather",
                                     // "itinerary", "profile", "general_fact"
                                     // If unclear, set to null.

  "entities": {
    "city": string|null,
    "region": string|null,
    "country": string|null,

    "poi_name": string|null,
    "poi_category": string|null,     // fine-grained KG category like "temple", "museum", "beach", or null

    "activity_type": string|null,    // ONE coarse category: "sightseeing", "hiking", "beach",
                                     // "wildlife", "shopping", "culture", "relaxation", or null

    "start_date": string|null,       // ISO date YYYY-MM-DD if clear; otherwise null
    "end_date": string|null,         // ISO date YYYY-MM-DD if clear; otherwise null
    "travel_month": string|null,     // Month name in English, e.g. "November"
    "days": int|null,
    "time_of_day": string|null,      // "morning" | "afternoon" | "evening" | "night"

    "num_travelers": int|null,
    "travel_with": string|null,      // e.g. "family", "friends", "solo"

    "origin": string|null,
    "destination": string|null,
    "origin_city": string|null,
    "include_stops": bool|null,
    "route_direction": string|null,   // "outbound" | "return" | "both"
    "waypoints": string[],                 // ordered intermediate stops if mentioned
    "stop_durations_days": { "string": int },  // map of waypoint -> days staying there

    "budget_level": string|null,     // "low" | "medium" | "high" or null

    "tags": string[],          // descriptive tags like ["nature", "culture", "family-friendly"]
    "legal_service": string|null,   // "visa" | "citizenship" | null
    "citizenship_type": string|null, // "dual_citizenship" | "citizenship_registration" | null


  },

  "preference_overrides": {
    "travel_style": string[],

    "avoid_crowds": bool|null,

    "eco_preference": string|null,           // "high"|"medium"|"low"|null  (will be normalized to float later)

    "activity_preference": string|null,      // "outdoor"|"indoor"|"mixed"|null
    "pace_preference": string|null,          // "relaxed"|"balanced"|"packed"|null
    "adventure_level": string|null,          // "low"|"medium"|"high"|null

    "budget_level": string|null,             // "low"|"medium"|"high"|null  (normalize to low/mid/high)
    "budget_per_night_lkr": int|null,
    "budget_flexibility": float|null,        // 0..1 if user implies strict/flexible

    "preferred_transport": string[],
    "food_preferences": string[],

    "accessibility_needs": string[]|null,
    "walking_tolerance_minutes": int|null,

    "accommodation_type": string|null,       // "hotel"|"eco_lodge"|"homestay"|...
    "star_preference": string|null,          // "any"|"3_star_plus"|"4_star_plus"|"5_star_only"
    "must_have_amenities": string[],
    "cancellation_preference": string|null,  // "flexible"|"strict"|"any"

    "sun_sensitivity": string|null,          // "low"|"medium"|"high"
    "rain_preference": string|null,          // "avoid_rain"|"ok_with_rain"|"prefer_rain"
    "temperature_preference": string|null,   // "cool"|"moderate"|"warm"

    "motion_sickness": bool|null
  }
}

Rules:
- domain_category MUST come from the fixed list. If unclear, set null.
- If a field is NOT mentioned or is unclear, set:
  - scalars → null
  - arrays → []
- For hotel queries:
  - If the user says "3-star", "4 star", etc., set min_star_rating and max_star_rating accordingly.
  - If the user says "under 15,000 rupees", "below 10000", etc., set max_price_lkr to that number and currency = "LKR".
- NEVER return arrays for fields defined as single strings (city, poi_name, activity_type, etc).
- If the user mentions themes like "nature and culture", place them in:
  - entities.tags → ["nature", "culture"]
  - preference_overrides.travel_style → ["nature", "culture"]
- Do NOT invent cities, POIs, or preferences not clearly implied.
- Use only real Sri Lankan city names when detected.
- If user asks about attractions but no specific POI, set poi_name = null.
- Output ONLY raw JSON. No extra text, no markdown, no explanation.
- If the user mentions intermediate stops like "via", "stop at", "on the way to", "pass through", extract them in "waypoints" in travel order.
- Do NOT include origin_city or destination inside waypoints.
- If the user says "stay/spend X days in Y", add Y to waypoints (if not already) and set stop_durations_days[Y] = X.
- stop_durations_days must only include locations present in waypoints.
"""


# ---- 2. Call Ollama (mistral) and parse JSON ----

# def _run_ollama_mistral(prompt: str, model: str = "mistral") -> str:
#     """
#     Low-level helper that calls `ollama run mistral` and returns raw stdout.
#     """
#     try:
#         proc = subprocess.run(
#             ["ollama", "run", model],
#             input=prompt.encode("utf-8"),
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             check=False,
#         )
#     except FileNotFoundError as e:
#         logger.error("ollama not found on PATH: %s", e)
#         raise

#     stdout = proc.stdout.decode("utf-8").strip()
#     stderr = proc.stderr.decode("utf-8").strip()
#     if stderr:
#         logger.debug("ollama stderr: %s", stderr)

#     return stdout


def _safe_json_extract(raw: str) -> Dict[str, Any]:
    """
    Try to parse JSON from the LLM output.
    If there is extra text, try to isolate the JSON substring.
    """
    raw = raw.strip()

    # Happy path: whole output is JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to find first '{' and last '}' and parse that slice
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        snippet = raw[start:end]
        return json.loads(snippet)
    except Exception as e:
        logger.error("Failed to parse JSON from LLM output: %s\nRaw: %s", e, raw)
        # Fallback to empty structure
        return {
            "domain_category": None,
            "entities": {},
            "preference_overrides": {},
        }
# def _run_groq_chat_completion(prompt: str) -> str:
#     if not GROQ_API_KEY:
#         raise RuntimeError("GROQ_API_KEY is not set in environment")

#     url = "https://api.groq.com/openai/v1/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {GROQ_API_KEY}",
#         "Content-Type": "application/json",   # <<< IMPORTANT
#     }
#     payload = {
#     "model": "llama-3.3-70b-versatile",  # ✅ updated model name
#     "messages": [{"role": "user", "content": prompt}],
#     "temperature": 0,
# }

#     r = requests.post(url, json=payload, headers=headers)

#     # temporary debug
#     if r.status_code != 200:
#         logger.error(
#             "Groq API error %s: %s",
#             r.status_code,
#             r.text,
#         )

#     r.raise_for_status()
#     return r.json()["choices"][0]["message"]["content"]

CANON_BUDGET = {"low": "low", "mid": "mid", "medium": "mid", "high": "high"}
ECO_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}
SENS_MAP = {"high": "high", "medium": "medium", "low": "low"}

RAIN_MAP = {
    "avoid_rain": "avoid_rain",
    "ok_with_rain": "ok_with_rain",
    "okay_with_rain": "ok_with_rain",
    "prefer_rain": "prefer_rain",
}

TEMP_MAP = {"cool": "cool", "moderate": "moderate", "warm": "warm"}

ACTIVITY_PREF = {"outdoor": "outdoor", "indoor": "indoor", "mixed": "mixed"}
PACE_PREF = {"relaxed": "relaxed", "balanced": "balanced", "packed": "packed"}
ADV_LEVEL = {"low": "low", "medium": "medium", "high": "high"}
RELATIVE_DAY_WORDS = {"today", "tomorrow", "yesterday", "day after tomorrow"}

STAR_PREF = {"any": "any", "3_star_plus": "3_star_plus", "4_star_plus": "4_star_plus", "5_star_only": "5_star_only"}
CANCEL_PREF = {"any": "any", "flexible": "flexible", "strict": "strict"}

ACCOM_TYPE = {"hotel","resort","villa","guesthouse","hostel","eco_lodge","homestay","any"}

ENTITY_BUDGET_MAP = {
    "low": "low",
    "mid": "mid",
    "medium": "mid",
    "high": "high",
    "unknown": "unknown",
}

def _normalize_entity_budget_level(entities: Dict[str, Any]) -> None:
    v = entities.get("budget_level")
    if v is None:
        return
    if not isinstance(v, str):
        entities["budget_level"] = None
        return

    norm = ENTITY_BUDGET_MAP.get(v.strip().lower())
    entities["budget_level"] = norm if norm else None


def _as_list(v):
    if v is None:
        return None
    if isinstance(v, list):
        return v
    return [v]

def normalize_preference_overrides(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert raw LLM prefs (strings like 'medium', 'high') into your DB canonical schema types.
    """
    raw = dict(raw or {})
    out: Dict[str, Any] = {}

    # travel_style list[str]
    ts = raw.get("travel_style")
    out["travel_style"] = ts if isinstance(ts, list) else ([ts] if ts else [])

    # avoid_crowds bool
    out["avoid_crowds"] = raw.get("avoid_crowds")

    # eco_preference -> float 0..1
    eco = raw.get("eco_preference")
    if isinstance(eco, (int, float)):
        out["eco_preference"] = float(eco)
    elif isinstance(eco, str):
        out["eco_preference"] = ECO_MAP.get(eco.strip().lower())
    else:
        out["eco_preference"] = None

    # activity / pace / adventure enums
    ap = raw.get("activity_preference")
    out["activity_preference"] = ACTIVITY_PREF.get(ap.strip().lower()) if isinstance(ap, str) else "unknown"

    pp = raw.get("pace_preference")
    out["pace_preference"] = PACE_PREF.get(pp.strip().lower()) if isinstance(pp, str) else "unknown"

    al = raw.get("adventure_level")
    out["adventure_level"] = ADV_LEVEL.get(al.strip().lower()) if isinstance(al, str) else "unknown"

    # budget_level canonical (low/mid/high/unknown)
    bl = raw.get("budget_level")
    if isinstance(bl, str):
        out["budget_level"] = CANON_BUDGET.get(bl.strip().lower(), None)
    else:
        out["budget_level"] = None

    # numeric budgets
    out["budget_per_night_lkr"] = raw.get("budget_per_night_lkr")
    out["budget_flexibility"] = raw.get("budget_flexibility")

    # lists
    fp = raw.get("food_preferences")
    out["food_preferences"] = fp if isinstance(fp, list) else ([fp] if fp else [])

    pt = raw.get("preferred_transport")
    out["preferred_transport"] = pt if isinstance(pt, list) else ([pt] if pt else [])

    # accessibility needs can be list|null in DB (you used Optional[List[str]])
    out["accessibility_needs"] = _as_list(raw.get("accessibility_needs"))

    out["walking_tolerance_minutes"] = raw.get("walking_tolerance_minutes")

    # accommodation prefs
    acc = raw.get("accommodation_type")
    if isinstance(acc, str):
        acc_norm = acc.strip().lower()
        out["accommodation_type"] = acc_norm if acc_norm in ACCOM_TYPE else "any"
    else:
        out["accommodation_type"] = "any"

    sp = raw.get("star_preference")
    out["star_preference"] = STAR_PREF.get(sp.strip().lower(), "any") if isinstance(sp, str) else "any"

    mha = raw.get("must_have_amenities")
    out["must_have_amenities"] = mha if isinstance(mha, list) else ([mha] if mha else [])

    cp = raw.get("cancellation_preference")
    out["cancellation_preference"] = CANCEL_PREF.get(cp.strip().lower(), "any") if isinstance(cp, str) else "any"

    # weather tolerance
    sun = raw.get("sun_sensitivity")
    out["sun_sensitivity"] = SENS_MAP.get(sun.strip().lower()) if isinstance(sun, str) else None

    rain = raw.get("rain_preference")
    out["rain_preference"] = RAIN_MAP.get(rain.strip().lower()) if isinstance(rain, str) else None

    temp = raw.get("temperature_preference")
    out["temperature_preference"] = TEMP_MAP.get(temp.strip().lower()) if isinstance(temp, str) else None

    out["motion_sickness"] = raw.get("motion_sickness")

    return out


def llm_extract_entities(text: str) -> Dict[str, Any]:
    llm_client = build_llm_client()

    if llm_client is None:
        logger.warning("No LLM client available for entity extraction.")
        return {
            "domain_category": None,
            "entities": {},
            "preference_overrides": {},
        }

    system_prompt = (
        "You are a precise JSON information extractor for a Sri Lanka tourism assistant. "
        "Return only valid JSON. No markdown, no explanations."
    )

    user_prompt = f"{BASE_PROMPT}\n\nUser query:\n{text.strip()}"

    try:
        data = llm_client.chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    except Exception as e:
        logger.exception("Entity extraction failed: %s", e)
        return {
            "domain_category": None,
            "entities": {},
            "preference_overrides": {},
        }

    if not isinstance(data, dict):
        logger.warning("LLM returned non-dict JSON.")
        return {
            "domain_category": None,
            "entities": {},
            "preference_overrides": {},
        }

    data.setdefault("domain_category", None)
    data.setdefault("entities", {})
    data.setdefault("preference_overrides", {})
    return data
DUAL_CITIZENSHIP_PATTERN = re.compile(r"\bdual\s+citizenship\b", re.IGNORECASE)
CITIZENSHIP_PATTERN = re.compile(r"\bcitizenship\b", re.IGNORECASE)

def _override_citizenship_entities(data: Dict[str, Any], text: str) -> None:
    entities = data.setdefault("entities", {})
    t = text.lower()

    if DUAL_CITIZENSHIP_PATTERN.search(t):
        entities["legal_service"] = "citizenship"
        entities["citizenship_type"] = "dual_citizenship"
        return

    # fallback: any citizenship mention
    if CITIZENSHIP_PATTERN.search(t):
        entities["legal_service"] = "citizenship"
        entities["citizenship_type"] = "citizenship_general"


# ---- 3. Rule-based overrides (Pattern B: LLM first, then rules) ----

RELATIVE_DATE_PATTERNS = {
    "today": re.compile(r"\btoday\b", re.IGNORECASE),
    "tomorrow": re.compile(r"\btomorrow\b", re.IGNORECASE),
    "this_weekend": re.compile(r"\bthis\s+weekend\b", re.IGNORECASE),
    "next_week": re.compile(r"\bnext\s+week\b", re.IGNORECASE),
    "next_weekend": re.compile(r"\bnext\s+weekend\b", re.IGNORECASE),
}


TIME_OF_DAY_PATTERNS = {
    "morning": re.compile(r"\bmorning\b", re.IGNORECASE),
    "afternoon": re.compile(r"\bafternoon\b", re.IGNORECASE),
    "evening": re.compile(r"\bevening\b", re.IGNORECASE),
    "night": re.compile(r"\bnight\b|\btonight\b", re.IGNORECASE),
}
WEEKDAY_NAME_TO_NUM = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

WEEKDAY_RELATIVE_PATTERN = re.compile(
    r"\b(?:(next|this)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)

PRICE_UNDER_PATTERN = re.compile(
    r'(?:under|below|less than|up to|upto|max(?:imum)?)\s+(\d[\d, ]*[kK]?)',
    re.IGNORECASE,
)

PRICE_ANY_PATTERN = re.compile(r'(\d[\d, ]*[kK]?)', re.IGNORECASE)

STAR_RANGE_PATTERN = re.compile(
    r'(\d)\s*(?:to|-|–)\s*(\d)\s*star',
    re.IGNORECASE,
)
STAR_SINGLE_PATTERN = re.compile(
    r'(\d)\s*[- ]?\s*star',
    re.IGNORECASE,
)
CURRENCY_PATTERN = re.compile(
    r'\b(rs|lkr|rupees?|usd|dollars?)\b',
    re.IGNORECASE,
)
NEXT_MONTH_PATTERN = re.compile(
    r"\bnext\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE
)
THIS_MONTH_PATTERN = re.compile(
    r"\bthis\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE
)

PRICE_CONTEXT_PATTERN = re.compile(
    r'\b(rs|lkr|rupees?|usd|dollars?|price|per night|pernight|budget)\b',
    re.IGNORECASE,
)
MONTH_DAY_RANGE_PATTERN = re.compile(
    r'\b('
    r'january|february|march|april|may|june|july|august|september|october|november|december'
    r')\s+(\d{1,2})\s*(?:to|-|–)\s*(\d{1,2})\b',
    re.IGNORECASE,
)
MONTH_NAME_TO_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
# --- NEW: Month + Year detection (e.g., "February 2026", "Feb 2026") ---
MONTH_YEAR_PATTERN = re.compile(
    r"\b("
    r"january|february|march|april|may|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
    r")\s+(20\d{2})\b",
    re.IGNORECASE
)

MONTH_ABBR_TO_FULL = {
    "jan": "january", "feb": "february", "mar": "march", "apr": "april",
    "jun": "june", "jul": "july", "aug": "august", "sep": "september",
    "sept": "september", "oct": "october", "nov": "november", "dec": "december",
}

# --- NEW: Nationality extraction patterns ---
CITIZEN_OF_PATTERN = re.compile(r"\bcitizen\s+of\s+([A-Za-z ]+)\b", re.IGNORECASE)
NATIONALITY_ADJ_PATTERN = re.compile(
    r"\b(i\s*am|i’m|im|we\s*are|we’re)\s+an?\s+([A-Za-z]+)\s+(citizen|national)\b",
    re.IGNORECASE,
)
PASSPORT_PATTERN = re.compile(r"\b([A-Za-z]+)\s+passport\b", re.IGNORECASE)

# Minimal adjective → country mapping (expand later)
NATIONALITY_ADJ_TO_COUNTRY = {
    "indian": "India",
    "sri": "Sri Lanka",  # (rare phrasing; optional)
    "srilankan": "Sri Lanka",
    "american": "United States",
    "british": "United Kingdom",
    "australian": "Australia",
    "canadian": "Canada",
}

NEXT_MONTH_GENERIC = re.compile(r"\bnext\s+month\b", re.IGNORECASE)

ROUTE_BOTH_PATTERN = re.compile(
    r"\b(both|both ways|both directions|to and fro|round\s*trip|going and coming back|go and return)\b",
    re.IGNORECASE,
)

ROUTE_RETURN_PATTERN = re.compile(
    r"\b(coming back|on the way back|on return|return trip|while returning|back home|back to)\b",
    re.IGNORECASE,
)

ROUTE_OUTBOUND_PATTERN = re.compile(
    r"\b(on the way(?: there)?|while going|en route|on the way to|include stops|stops on the way|stop by|pit stop)\b",
    re.IGNORECASE,
)
STOP_DURATION_PATTERNS = [
    re.compile(r"\b(?:stay|spend)\s+(?:in|at)\s+([A-Za-z][A-Za-z\s\-]+?)\s+for\s+(\d+)\s+days?\b", re.IGNORECASE),
    re.compile(r"\b(?:stay|spend)\s+(\d+)\s+days?\s+(?:in|at)\s+([A-Za-z][A-Za-z\s\-]+?)\b", re.IGNORECASE),
    re.compile(r"\bstop\s+(?:in|at)\s+([A-Za-z][A-Za-z\s\-]+?)\s+for\s+(\d+)\s+days?\b", re.IGNORECASE),
]

def _override_stop_durations(data: Dict[str, Any], text: str) -> None:
    entities = data.setdefault("entities", {})
    stop_map = entities.get("stop_durations_days")
    if not isinstance(stop_map, dict):
        stop_map = {}

    # Ensure waypoints list exists
    wps = entities.get("waypoints")
    if not isinstance(wps, list):
        wps = [] if wps is None else [wps]

    for pat in STOP_DURATION_PATTERNS:
        for m in pat.finditer(text):
            # pattern order differs: sometimes (place, days) or (days, place)
            g1, g2 = m.group(1), m.group(2)

            if g1.isdigit():
                days = int(g1)
                place = g2
            else:
                place = g1
                days = int(g2)

            place_clean = re.sub(r"\s+", " ", place.strip()).title()
            if not place_clean:
                continue

            # add to waypoints if not already
            if place_clean.lower() not in {w.lower() for w in wps}:
                wps.append(place_clean)

            # set duration
            if days > 0:
                stop_map[place_clean] = days

    entities["waypoints"] = wps
    entities["stop_durations_days"] = stop_map

    # include_stops auto
    if entities.get("include_stops") is None:
        entities["include_stops"] = bool(wps)
def _override_route_direction(data: Dict[str, Any], text: str) -> None:
    entities = data.setdefault("entities", {})
    t = text.lower()

    # strongest first
    if ROUTE_BOTH_PATTERN.search(t):
        entities["route_direction"] = "both"
        return

    if ROUTE_RETURN_PATTERN.search(t):
        entities["route_direction"] = "return"
        return

    if ROUTE_OUTBOUND_PATTERN.search(t):
        entities["route_direction"] = "outbound"
        return

    # If they said "include stops on the way" but didn't specify direction,
    # choose your default behavior:
    if entities.get("include_stops") is True and entities.get("route_direction") is None:
        entities["route_direction"] = "outbound"   # or keep None if you want to ask follow-up

def _override_next_month_generic(data: Dict[str, Any], text: str, now: datetime) -> None:
    if not NEXT_MONTH_GENERIC.search(text):
        return

    entities = data.setdefault("entities", {})
    year = now.year
    month = now.month + 1
    if month == 13:
        month = 1
        year += 1

    last_day = calendar.monthrange(year, month)[1]
    entities["travel_month"] = datetime(year, month, 1).strftime("%B")
    if not entities.get("start_date") and not entities.get("end_date"):
        entities["start_date"] = f"{year:04d}-{month:02d}-01"
        entities["end_date"] = f"{year:04d}-{month:02d}-{last_day:02d}"

def _override_month_year_dates(data: Dict[str, Any], text: str, now: datetime) -> None:
    """
    If text contains 'February 2026' (or 'Feb 2026') and the LLM missed it,
    set travel_month + start_date/end_date to that month range.

    This is especially useful for visa queries where policy can change over time.
    """
    entities = data.setdefault("entities", {})
    t = text.lower()

    m = MONTH_YEAR_PATTERN.search(t)
    if not m:
        return

    month_raw = m.group(1).lower()
    year = int(m.group(2))

    # normalize month
    if month_raw in MONTH_ABBR_TO_FULL:
        month_name = MONTH_ABBR_TO_FULL[month_raw]
    else:
        month_name = month_raw

    month_num = MONTH_NAME_TO_NUM.get(month_name)
    if not month_num:
        return

    # Set travel_month always
    entities["travel_month"] = month_name.capitalize()

    # Only set start/end if not already a more precise date
    # (If user said "Feb 12 2026", you'd handle that elsewhere.)
    if not entities.get("start_date") and not entities.get("end_date"):
        last_day = calendar.monthrange(year, month_num)[1]
        entities["start_date"] = f"{year:04d}-{month_num:02d}-01"
        entities["end_date"] = f"{year:04d}-{month_num:02d}-{last_day:02d}"
def _override_nationality(data: Dict[str, Any], text: str) -> None:
    """
    Extract nationality explicitly for visa logic.
    Examples:
      - "I’m an Indian citizen" -> India
      - "citizen of India" -> India
      - "Indian passport" -> India
    """
    entities = data.setdefault("entities", {})
    t = text.strip()

    # citizen of X
    m = CITIZEN_OF_PATTERN.search(t)
    if m:
        country = m.group(1).strip()
        entities["nationality_country"] = country
        return

    # "I'm an Indian citizen"
    m2 = NATIONALITY_ADJ_PATTERN.search(t)
    if m2:
        adj = m2.group(2).strip().lower()
        country = NATIONALITY_ADJ_TO_COUNTRY.get(adj)
        if country:
            entities["nationality_country"] = country
        else:
            # fallback: store adjective as-is if unknown
            entities["nationality_country"] = adj.capitalize()
        return

    # "Indian passport"
    m3 = PASSPORT_PATTERN.search(t)
    if m3:
        adj = m3.group(1).strip().lower()
        country = NATIONALITY_ADJ_TO_COUNTRY.get(adj)
        if country:
            entities["nationality_country"] = country
        else:
            entities["nationality_country"] = adj.capitalize()



def _parse_price_cap(text: str) -> Optional[int]:
    """
    Extract a numeric price cap like '18500', '18,500', '18 500', or '20k' from text.
    - Prefer the number after 'under/below/less than/...'.
    - Only fall back to 'last number' if there is clear price/currency context.
    - Support 'k' suffix meaning 'thousand' (e.g., '20k' -> 20000).
    """
    t = text.lower()

    m = PRICE_UNDER_PATTERN.search(t)
    raw: Optional[str] = None

    if m:
        raw = m.group(1)
    else:
        # Only allow fallback if text clearly talks about money/price
        if not PRICE_CONTEXT_PATTERN.search(t):
            return None

        matches = PRICE_ANY_PATTERN.findall(t)
        if matches:
            raw = matches[-1]

    if not raw:
        return None

    cleaned = raw.lower().replace(",", "").replace(" ", "")

    multiplier = 1
    if cleaned.endswith("k"):
        multiplier = 1000
        cleaned = cleaned[:-1]

    if not cleaned:
        return None

    try:
        return int(cleaned) * multiplier
    except ValueError:
        return None




def _parse_star_range(text: str) -> tuple[Optional[int], Optional[int]]:
    """
    Extract star rating range like '3 to 5 star' or single '4-star'.
    Returns (min_star, max_star).
    """
    t = text.lower()

    # 1) Range: "3 to 5 star"
    m = STAR_RANGE_PATTERN.search(t)
    if m:
        try:
            low = int(m.group(1))
            high = int(m.group(2))
            if low > high:
                low, high = high, low
            return low, high
        except ValueError:
            pass

    # 2) Single star: "4 star", "5-star"
    m2 = STAR_SINGLE_PATTERN.search(t)
    if m2:
        try:
            val = int(m2.group(1))
            return val, val
        except ValueError:
            pass

    return None, None


def _detect_currency(text: str) -> Optional[str]:
    t = text.lower()
    if re.search(r'\b(usd|dollars?)\b', t):
        return "USD"
    if re.search(r'\b(lkr|rs|rupees?)\b', t):
        return "LKR"
    return None

def _sanitize_time_of_day(data: Dict[str, Any]) -> None:
    """
    Ensure entities.time_of_day is only one of:
    morning/afternoon/evening/night or None.
    If LLM put 'tomorrow' etc into time_of_day, clear it.
    """
    entities = data.setdefault("entities", {})
    tod = entities.get("time_of_day")

    if tod is None:
        return

    if not isinstance(tod, str):
        entities["time_of_day"] = None
        return

    tod_norm = tod.strip().lower()

    # If LLM wrongly put relative-day words into time_of_day, remove it.
    if tod_norm in RELATIVE_DAY_WORDS:
        entities["time_of_day"] = None
        return

    # Allow only valid buckets
    allowed = {"morning", "afternoon", "evening", "night"}
    entities["time_of_day"] = tod_norm if tod_norm in allowed else None

def _override_relative_dates(
    data: Dict[str, Any],
    text: str,
    now: datetime,
) -> None:
    """
    Deterministic date overrides based on relative phrases and simple patterns.
    """
    entities = data.setdefault("entities", {})
    t = text.lower()

    today = now.date()
    wd = today.weekday()  # Mon=0 ... Sun=6

    start_date = entities.get("start_date")
    end_date = entities.get("end_date")
    travel_month = entities.get("travel_month")

    def set_range(d1, d2):
        nonlocal start_date, end_date, travel_month
        start_date = d1.strftime("%Y-%m-%d")
        end_date = d2.strftime("%Y-%m-%d")
        travel_month = d1.strftime("%B")

    # --- today / tomorrow ---
    if RELATIVE_DATE_PATTERNS["tomorrow"].search(t):
        d = today + timedelta(days=1)
        set_range(d, d)

    elif RELATIVE_DATE_PATTERNS["today"].search(t):
        set_range(today, today)

    # --- this weekend (upcoming Sat-Sun) ---
    elif RELATIVE_DATE_PATTERNS["this_weekend"].search(t):
        days_until_sat = (5 - wd) % 7
        sat = today + timedelta(days=days_until_sat)
        sun = sat + timedelta(days=1)
        set_range(sat, sun)

    # --- next weekend (Sat-Sun of next week) ---
    elif RELATIVE_DATE_PATTERNS["next_weekend"].search(t):
        days_until_sat = (5 - wd) % 7
        sat_this = today + timedelta(days=days_until_sat)
        sat_next = sat_this + timedelta(days=7)
        sun_next = sat_next + timedelta(days=1)
        set_range(sat_next, sun_next)

    # --- next week (Mon-Sun of upcoming week) ---
    elif RELATIVE_DATE_PATTERNS["next_week"].search(t):
        days_until_next_monday = (7 - wd) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7
        start_dt = today + timedelta(days=days_until_next_monday)
        end_dt = start_dt + timedelta(days=6)
        set_range(start_dt, end_dt)

    # --- explicit month/day range like "January 12 to 15" ---
    m = MONTH_DAY_RANGE_PATTERN.search(t)
    if m:
        month_name = m.group(1).lower()
        day_start = int(m.group(2))
        day_end = int(m.group(3))
        month_num = MONTH_NAME_TO_NUM.get(month_name)
        if month_num:
            year = now.year
            try:
                start_dt = datetime(year, month_num, day_start).date()
                end_dt = datetime(year, month_num, day_end).date()
                if end_dt < today:
                    year += 1
                    start_dt = datetime(year, month_num, day_start).date()
                    end_dt = datetime(year, month_num, day_end).date()
                set_range(start_dt, end_dt)
            except ValueError:
                pass

    # --- weekday like "next Monday" / "this Friday" ---
    m_w = WEEKDAY_RELATIVE_PATTERN.search(t)
    if m_w:
        modifier = (m_w.group(1) or "").lower()
        weekday_name = m_w.group(2).lower()
        target_wd = WEEKDAY_NAME_TO_NUM[weekday_name]

        days_ahead = (target_wd - wd) % 7
        if modifier == "next" and days_ahead == 0:
            days_ahead = 7
        elif modifier == "this" and target_wd < wd:
            days_ahead += 7

        d = today + timedelta(days=days_ahead)
        set_range(d, d)

    # --- next/this month by name ---
    m_next = NEXT_MONTH_PATTERN.search(t)
    m_this = THIS_MONTH_PATTERN.search(t)
    if m_next or m_this:
        month_name = (m_next.group(1) if m_next else m_this.group(1)).lower()
        month_num = MONTH_NAME_TO_NUM[month_name]
        year = now.year

        if m_next:
            if month_num <= now.month:
                year += 1
        else:
            if month_num < now.month:
                year += 1

        last_day = calendar.monthrange(year, month_num)[1]
        set_range(datetime(year, month_num, 1).date(), datetime(year, month_num, last_day).date())

    # write back
    entities["start_date"] = start_date
    entities["end_date"] = end_date
    entities["travel_month"] = travel_month

    def set_range(d1, d2):
        nonlocal start_date, end_date, travel_month
        start_date = d1.strftime("%Y-%m-%d")
        end_date = d2.strftime("%Y-%m-%d")
        travel_month = d1.strftime("%B")

    # --- today / tomorrow ---
    if RELATIVE_DATE_PATTERNS["tomorrow"].search(t):
        d = today + timedelta(days=1)
        set_range(d, d)

    elif RELATIVE_DATE_PATTERNS["today"].search(t):
        set_range(today, today)

    # --- this weekend (upcoming Sat-Sun) ---
    elif RELATIVE_DATE_PATTERNS["this_weekend"].search(t):
        days_until_sat = (5 - wd) % 7
        sat = today + timedelta(days=days_until_sat)
        sun = sat + timedelta(days=1)
        set_range(sat, sun)

    # --- next weekend (Sat-Sun of next week) ✅ ---
    elif RELATIVE_DATE_PATTERNS["next_weekend"].search(t):
        days_until_sat = (5 - wd) % 7
        sat_this = today + timedelta(days=days_until_sat)
        sat_next = sat_this + timedelta(days=7)
        sun_next = sat_next + timedelta(days=1)
        set_range(sat_next, sun_next)

    # --- next week (Mon-Sun of upcoming week) ---
    elif RELATIVE_DATE_PATTERNS["next_week"].search(t):
        days_until_next_monday = (7 - wd) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7
        start_dt = today + timedelta(days=days_until_next_monday)
        end_dt = start_dt + timedelta(days=6)
        set_range(start_dt, end_dt)

    # --- explicit month/day like "January 12 to 15" ---
    m = MONTH_DAY_RANGE_PATTERN.search(t)
    if m:
        month_name = m.group(1).lower()
        day_start = int(m.group(2))
        day_end = int(m.group(3))

        month_num = MONTH_NAME_TO_NUM.get(month_name)
        if month_num:
            year = now.year
            try:
                start_dt = datetime(year, month_num, day_start).date()
                end_dt = datetime(year, month_num, day_end).date()

                # if already past, move to next year
                if end_dt < today:
                    year += 1
                    start_dt = datetime(year, month_num, day_start).date()
                    end_dt = datetime(year, month_num, day_end).date()

                set_range(start_dt, end_dt)
            except ValueError:
                pass

    else:
        # --- weekday like "next Monday", "this Friday", "on Monday" ---
        m_w = WEEKDAY_RELATIVE_PATTERN.search(t)
        if m_w:
            modifier = (m_w.group(1) or "").lower()  # "next", "this", or ""
            weekday_name = m_w.group(2).lower()
            target_wd = WEEKDAY_NAME_TO_NUM[weekday_name]

            # next occurrence (including today)
            days_ahead = (target_wd - wd) % 7

            if modifier == "next":
                # always strictly future
                if days_ahead == 0:
                    days_ahead = 7
            elif modifier == "this":
                # if "this Monday" but today is after Monday in the same week -> go to next week's Monday
                if days_ahead == 0:
                    days_ahead = 0
                # NOTE: days_ahead from %7 is never negative; to detect "already passed",
                # we check if target is earlier in week (target_wd < wd).
                elif target_wd < wd:
                    days_ahead += 7
            else:
                # no modifier: upcoming occurrence (today allowed)
                pass

            d = today + timedelta(days=days_ahead)
            set_range(d, d)

    # --- write back ---
    entities["start_date"] = start_date
    entities["end_date"] = end_date
    entities["travel_month"] = travel_month

def _sanitize_route_direction(data: Dict[str, Any]) -> None:
    entities = data.setdefault("entities", {})
    v = entities.get("route_direction")
    if v is None:
        return
    if not isinstance(v, str):
        entities["route_direction"] = None
        return
    v = v.strip().lower()
    entities["route_direction"] = v if v in {"outbound", "return", "both"} else None


def _override_time_of_day(data: Dict[str, Any], text: str) -> None:
    """
    Force time_of_day based on explicit words, if present.
    """
    entities = data.setdefault("entities", {})
    t = text.lower()
    tod = entities.get("time_of_day")

    for label, pattern in TIME_OF_DAY_PATTERNS.items():
        if pattern.search(t):
            tod = label
            break

    if tod is not None:
        entities["time_of_day"] = tod

def _mentions_location(text: str, loc: Optional[str]) -> bool:
    if not loc or not isinstance(loc, str):
        return False
    t = text.lower()
    # normalize small punctuation/spacing
    needle = re.sub(r"\s+", " ", loc.strip().lower())
    return needle in re.sub(r"\s+", " ", t)

DATE_SIGNAL_PATTERN = re.compile(
    r"(\b20\d{2}\b|\b\d{4}-\d{2}-\d{2}\b|"
    r"\btoday\b|\btomorrow\b|\bnext week\b|\bthis weekend\b|\bnext weekend\b|"
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b)",
    re.IGNORECASE
)

def _strip_unmentioned_city_destination_and_dates(data: Dict[str, Any], text: str) -> None:
    entities = data.setdefault("entities", {})
    t = text.strip()

    # --- 1) City/Destination hallucination guard ---
    # If LLM picked a city/destination that the user never typed, drop it.
    for key in ("city", "destination", "origin_city", "origin", "region"):
        v = entities.get(key)
        if isinstance(v, str) and v.strip() and not _mentions_location(t, v):
            entities[key] = None

    # --- 2) Date hallucination guard ---
    # If the user text has ZERO date signals, don't keep LLM-proposed start/end.
    if not DATE_SIGNAL_PATTERN.search(t):
        entities["start_date"] = None
        entities["end_date"] = None
        entities["travel_month"] = None

    data["entities"] = entities


# ---- 4. Public entrypoint used by IntentParserAgent ----
DAY_MONTH_PATTERN = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)

def _normalize_partial_date_year(text: str, now: datetime) -> str:
    m = DAY_MONTH_PATTERN.search(text)
    if not m:
        return text

    day = int(m.group(1))
    month_name = m.group(2).lower()
    month_num = MONTH_NAME_TO_NUM.get(month_name)
    if not month_num:
        return text

    year = now.year
    try:
        candidate = datetime(year, month_num, day)
    except ValueError:
        return text

    if candidate.date() < now.date():
        year += 1

    normalized = f"{day} {month_name} {year}"
    return DAY_MONTH_PATTERN.sub(normalized, text, count=1)
def extract_entities_and_prefs(
    text: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    High-level function:
      1) Ask Mistral (via Ollama) for full JSON (LLM-first).
      2) Normalize domain_category.
      3) Override relative dates + time_of_day using deterministic rules.
      4) Add hotel-specific numeric constraints (star rating, price, currency).
      5) Ensure all expected keys exist with correct types (no None for lists).
    """
    if now is None:
        now = datetime.now()
    text = _normalize_partial_date_year(text, now)

    data = llm_extract_entities(text)

    # -------- DOMAIN CATEGORY NORMALIZATION --------
    ALLOWED_DOMAIN_CATEGORIES = {
        "attraction",
        "hotel",
        "restaurant",
        "transport",
        "visa",
        "weather",
        "itinerary",
        "profile",
        "general_fact",
    }

    domain = data.get("domain_category")
    if isinstance(domain, str):
        domain_lower = domain.strip().lower()
        if domain_lower in ALLOWED_DOMAIN_CATEGORIES:
            data["domain_category"] = domain_lower
        else:
            data["domain_category"] = None
    else:
        data["domain_category"] = None

    # 1) Rule-based overrides you already had
    # 1) Deterministic overrides
    _override_month_year_dates(data, text, now)   # ✅ NEW
    _override_next_month_generic(data, text, now)

    _override_relative_dates(data, text, now)
    _override_nationality(data, text)            # ✅ NEW
    _override_citizenship_entities(data, text)
    _sanitize_time_of_day(data) 


    entities = data.setdefault("entities", {})
    _override_route_direction(data, text) 
    _sanitize_route_direction(data)
    _override_stop_durations(data, text)
    _strip_unmentioned_city_destination_and_dates(data, text)

    # If user asked for N days and we have a start_date but end_date is missing/same, compute it
    try:
        days = entities.get("days")
        start_date = entities.get("start_date")
        end_date = entities.get("end_date")

        if days and start_date and (not end_date or end_date == start_date):
            sd = datetime.strptime(start_date, "%Y-%m-%d").date()
            ed = sd + timedelta(days=int(days) - 1)
            entities["end_date"] = ed.strftime("%Y-%m-%d")
    except Exception:
        pass
    _override_time_of_day(data, text)
    _override_weather_tags_and_prefs(data, text)

    # 1b) Hotel-specific constraints: star rating & price cap
    entities = data.setdefault("entities", {})
    _normalize_entity_budget_level(entities)
    prefs = data.setdefault("preference_overrides", {})

    # Parse star ratings from raw text (range or single)
    min_star, max_star = _parse_star_range(text)
    if entities.get("min_star_rating") is None and min_star is not None:
        entities["min_star_rating"] = min_star
    if entities.get("max_star_rating") is None and max_star is not None:
        entities["max_star_rating"] = max_star

    # Parse price cap from raw text
    price_cap = _parse_price_cap(text)
    if entities.get("max_price_lkr") is None and price_cap is not None:
        entities["max_price_lkr"] = price_cap

    # Currency detection
    if entities.get("currency") is None:
        detected_currency = _detect_currency(text)
        if detected_currency is not None:
            entities["currency"] = detected_currency

    # -------- ENTITIES: ensure keys + types --------
    entity_defaults = {
        "city": None,
        "region": None,
        "country": None,
        "poi_name": None,
        "poi_category": None,
        "activity_type": None,
        "start_date": None,
        "end_date": None,
        "travel_month": None,
        "days": None,
        "time_of_day": None,
        "num_travelers": None,
        "nationality_country": None,
        "travel_with": None,
        "origin": None,
        "destination": None,
        "budget_level": None,
        "tags": [],
        "legal_service": None,
        "citizenship_type": None,
        "origin_city": None,
        "include_stops": None,
        "route_direction": None,
        "waypoints": [],
        "stop_durations_days": {},


        # NEW hotel-specific constraints
        "min_star_rating": None,
        "max_star_rating": None,
        "max_price_lkr": None,
        "currency": None,
    }

    for key, default in entity_defaults.items():
        if key not in entities or entities[key] is None:
            entities[key] = default

    # Force list-typed fields in entities to always be lists
    if not isinstance(entities["tags"], list):
        entities["tags"] = [entities["tags"]] if entities["tags"] is not None else []

    # Optional: coerce activity_type list → single string if LLM misbehaves
    if isinstance(entities["activity_type"], list):
        if len(entities["activity_type"]) == 0:
            entities["activity_type"] = None
        elif len(entities["activity_type"]) == 1:
            entities["activity_type"] = entities["activity_type"][0]
        else:
            entities["activity_type"] = ", ".join(entities["activity_type"])

    # -------- PREFS: ensure keys + types --------
    # ✅ keep raw (optional but helpful for debugging)
    raw_prefs = dict(prefs or {})

    # ✅ normalize to your DB PreferenceOverrides schema
    prefs = normalize_preference_overrides(raw_prefs)


    data["entities"] = entities
    data["preference_overrides"] = prefs
    data["raw_preference_overrides"] = raw_prefs 
    return data
def _override_weather_tags_and_prefs(data: Dict[str, Any], text: str) -> None:
    """
    Add simple weather-related tags and preferences based on keywords.
    We *do not* set rain_preference just because the word 'rain' appears.
    Only set preferences when user clearly expresses like/dislike.
    """
    entities = data.setdefault("entities", {})
    prefs = data.setdefault("preference_overrides", {})

    t = text.lower()

    # Ensure tags list exists
    tags = entities.get("tags")
    if not isinstance(tags, list):
        tags = [] if tags is None else [tags]

    # Basic 'rain' topic tagging
    if "rain" in t or "raining" in t:
        if "rain" not in tags:
            tags.append("rain")

    # Optional: detect explicit avoidance preferences
    # e.g. "I want to avoid rain", "I don't like rain"
    avoid_patterns = [
        r"\bavoid rain\b",
        r"\bdon't like rain\b",
        r"\bhate rain\b",
        r"\bwant to skip rainy days\b",
    ]
    if any(re.search(p, t) for p in avoid_patterns):
        prefs["rain_preference"] = "avoid_rain"

    entities["tags"] = tags
    data["entities"] = entities
    data["preference_overrides"] = prefs

