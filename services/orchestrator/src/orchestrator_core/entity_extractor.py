# orchestrator_core/entity_extractor.py

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

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

    "budget_level": string|null,     // "low" | "medium" | "high" or null

    "tags": string[]                 // descriptive tags like ["nature", "culture", "family-friendly"]

  },

  "preference_overrides": {
    "travel_style": string[],        // e.g. ["nature", "culture", "adventure"]
    "avoid_crowds": bool|null,
    "budget_level": string|null,     // "low" | "medium" | "high" or null
    "eco_preference": string|null,
    "accessibility_needs": string|null,
    "food_preferences": string[],    // e.g. ["vegetarian", "seafood"]
    "preferred_transport": string[], // e.g. ["train", "bus"]
    "sun_sensitivity": string|null,  // "high", "medium", "low"
    "rain_preference": string|null,  // "avoid_rain", "okay_with_rain"
    "temperature_preference": string|null,  // "cool", "warm"
    "avoid_stray_animals": bool|null,
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
"""


# ---- 2. Call Ollama (mistral) and parse JSON ----

def _run_ollama_mistral(prompt: str, model: str = "mistral") -> str:
    """
    Low-level helper that calls `ollama run mistral` and returns raw stdout.
    """
    try:
        proc = subprocess.run(
            ["ollama", "run", model],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as e:
        logger.error("ollama not found on PATH: %s", e)
        raise

    stdout = proc.stdout.decode("utf-8").strip()
    stderr = proc.stderr.decode("utf-8").strip()
    if stderr:
        logger.debug("ollama stderr: %s", stderr)

    return stdout


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


def llm_extract_entities(text: str) -> Dict[str, Any]:
    """
    Call Mistral via Ollama to get the raw entities + preference_overrides JSON.
    """
    prompt = f"{BASE_PROMPT}\n\nUser query:\n{text.strip()}"
    raw = _run_ollama_mistral(prompt)
    data = _safe_json_extract(raw)

    # Ensure keys exist
    data.setdefault("domain_category", None)
    data.setdefault("entities", {})
    data.setdefault("preference_overrides", {})

    return data


# ---- 3. Rule-based overrides (Pattern B: LLM first, then rules) ----

RELATIVE_DATE_PATTERNS = {
    "today": re.compile(r"\btoday\b", re.IGNORECASE),
    "tomorrow": re.compile(r"\btomorrow\b", re.IGNORECASE),
    "this_weekend": re.compile(r"\bthis\s+weekend\b", re.IGNORECASE),
}

TIME_OF_DAY_PATTERNS = {
    "morning": re.compile(r"\bmorning\b", re.IGNORECASE),
    "afternoon": re.compile(r"\bafternoon\b", re.IGNORECASE),
    "evening": re.compile(r"\bevening\b", re.IGNORECASE),
    "night": re.compile(r"\bnight\b|\btonight\b", re.IGNORECASE),
}
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




def _override_relative_dates(
    data: Dict[str, Any],
    text: str,
    now: datetime,
) -> None:
    """
    Override start_date, end_date, travel_month when relative phrases exist.
    We trust backend 'now' more than LLM's guesses.
    """
    entities = data.setdefault("entities", {})

    # Only override if we detect relative expressions
    t = text.lower()

    start_date: Optional[str] = entities.get("start_date")
    end_date: Optional[str] = entities.get("end_date")
    travel_month: Optional[str] = entities.get("travel_month")

    if RELATIVE_DATE_PATTERNS["tomorrow"].search(t):
        d = now + timedelta(days=1)
        iso = d.strftime("%Y-%m-%d")
        month = d.strftime("%B")
        start_date = end_date = iso
        travel_month = month

    elif RELATIVE_DATE_PATTERNS["today"].search(t):
        d = now
        iso = d.strftime("%Y-%m-%d")
        month = d.strftime("%B")
        start_date = end_date = iso
        travel_month = month

    elif RELATIVE_DATE_PATTERNS["this_weekend"].search(t):
        # Simple heuristic: assume Saturday/Sunday of the same week.
        weekday = now.weekday()  # Monday=0 ... Sunday=6
        days_until_saturday = (5 - weekday) % 7
        saturday = now + timedelta(days=days_until_saturday)
        sunday = saturday + timedelta(days=1)
        start_date = saturday.strftime("%Y-%m-%d")
        end_date = sunday.strftime("%Y-%m-%d")
        travel_month = saturday.strftime("%B")

    if start_date is not None:
        entities["start_date"] = start_date
    if end_date is not None:
        entities["end_date"] = end_date
    if travel_month is not None:
        entities["travel_month"] = travel_month
    # If still no explicit year in text, handle patterns like "January 12 to 15"
    # We ignore whatever year the LLM guessed and recompute from `now`.
    m = MONTH_DAY_RANGE_PATTERN.search(t)
    if m:
        month_name = m.group(1).lower()
        day_start = int(m.group(2))
        day_end = int(m.group(3))

        month_num = MONTH_NAME_TO_NUM.get(month_name)
        if month_num:
            year = now.year

            try:
                start_dt = datetime(year, month_num, day_start)
                end_dt = datetime(year, month_num, day_end)

                # If this range is already in the past, move to next year
                if end_dt.date() < now.date():
                    year += 1
                    start_dt = datetime(year, month_num, day_start)
                    end_dt = datetime(year, month_num, day_end)

                entities["start_date"] = start_dt.strftime("%Y-%m-%d")
                entities["end_date"] = end_dt.strftime("%Y-%m-%d")
                entities["travel_month"] = month_name.capitalize()
            except ValueError:
                # Invalid day/month (e.g. Feb 30) – just ignore
                pass


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


# ---- 4. Public entrypoint used by IntentParserAgent ----

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
    _override_relative_dates(data, text, now)
    _override_time_of_day(data, text)

    # 1b) Hotel-specific constraints: star rating & price cap
    entities = data.setdefault("entities", {})
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
        "travel_with": None,
        "origin": None,
        "destination": None,
        "budget_level": None,
        "tags": [],

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
    prefs_defaults = {
        "travel_style": [],          # list[str]
        "avoid_crowds": None,
        "budget_level": None,
        "eco_preference": None,
        "accessibility_needs": None,
        "food_preferences": [],      # list[str]
        "preferred_transport": [],   # list[str]
        "sun_sensitivity": None,
        "rain_preference": None,
        "temperature_preference": None,
        "avoid_stray_animals": None,
        "motion_sickness": None,
    }

    for key, default in prefs_defaults.items():
        if key not in prefs or prefs[key] is None:
            prefs[key] = default

    # Force list-typed fields in prefs to always be lists
    for list_key in ["travel_style", "food_preferences", "preferred_transport"]:
        if not isinstance(prefs[list_key], list):
            prefs[list_key] = [prefs[list_key]] if prefs[list_key] is not None else []

    # OPTIONAL: normalize budget_level to low/medium/high only
    ALLOWED_BUDGET_LEVELS = {"low", "medium", "high"}
    raw_budget = prefs.get("budget_level")
    if isinstance(raw_budget, str):
        b = raw_budget.strip().lower()
        if b not in ALLOWED_BUDGET_LEVELS:
            prefs["budget_level"] = None
        else:
            prefs["budget_level"] = b

    data["entities"] = entities
    data["preference_overrides"] = prefs
    return data

