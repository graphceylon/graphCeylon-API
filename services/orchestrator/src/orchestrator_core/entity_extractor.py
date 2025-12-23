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


load_dotenv() 

logger = logging.getLogger(__name__)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ENTITY_LLM_PROVIDER = os.getenv("ENTITY_LLM_PROVIDER", "groq")
logger.warning(f"GROQ_API_KEY loaded? {bool(GROQ_API_KEY)}")
logger.warning(f"ENTITY_LLM_PROVIDER={ENTITY_LLM_PROVIDER}")
print("GROQ_API_KEY loaded?", bool(GROQ_API_KEY))
print("GROQ_API_KEY repr:", repr(GROQ_API_KEY))
print("ENTITY_LLM_PROVIDER:", ENTITY_LLM_PROVIDER)




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
    "legal_service": string|null   // "visa" | "citizenship" | null
    "citizenship_type": string|null // "dual_citizenship" | "citizenship_registration" | null


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
def _run_groq_chat_completion(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in environment")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",   # <<< IMPORTANT
    }
    payload = {
    "model": "llama-3.3-70b-versatile",  # ✅ updated model name
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0,
}

    r = requests.post(url, json=payload, headers=headers)

    # temporary debug
    if r.status_code != 200:
        logger.error(
            "Groq API error %s: %s",
            r.status_code,
            r.text,
        )

    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]



def llm_extract_entities(text: str) -> Dict[str, Any]:
    prompt = f"{BASE_PROMPT}\n\nUser query:\n{text.strip()}"

    provider = ENTITY_LLM_PROVIDER.lower()

    if provider == "ollama":
        raw = _run_ollama_mistral(prompt)
    elif provider == "groq":
        raw = _run_groq_chat_completion(prompt)
    elif provider == "openai":
        raw = _run_openai_chat_completion(prompt)  # TODO
    else:
        raise ValueError(f"Unknown ENTITY_LLM_PROVIDER={ENTITY_LLM_PROVIDER}")

    data = _safe_json_extract(raw)
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
    # 1) Deterministic overrides
    _override_month_year_dates(data, text, now)   # ✅ NEW
    _override_relative_dates(data, text, now)
    _override_nationality(data, text)            # ✅ NEW
    _override_citizenship_entities(data, text)


    entities = data.setdefault("entities", {})

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

