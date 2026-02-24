import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

SLOTS = {"morning", "afternoon", "evening", "night"}

def _extract_iso_date(text: str) -> Optional[str]:
    t = _norm(text)
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", t)
    return m.group(1) if m else None

def _plan_start_date(existing_plan: Dict[str, Any]) -> Optional[str]:
    # you store start_date in meta.start_date in your plan JSON
    meta = (existing_plan or {}).get("meta") or {}
    sd = meta.get("start_date")
    return str(sd) if sd else None

def _extract_trip_shift(text: str) -> Optional[int]:
    """
    "shift this trip 3 days forward"
    "move the trip 2 days back"
    "push it by 1 week"
    Returns delta_days (+ forward, - backward)
    """
    t = _norm(text)

    # days
    m = re.search(r"\b(shift|move|push|postpone|delay|bring\s+forward)\b.*?\b(\d{1,2})\s*day(?:s)?\b.*?\b(forward|ahead|later|back|backward|earlier)\b", t)
    if m:
        n = int(m.group(2))
        direction = m.group(3)
        return +n if direction in {"forward", "ahead", "later"} else -n

    # "by N days" without explicit direction words
    m = re.search(r"\b(shift|move|push|postpone|delay)\b.*?\bby\s+(\d{1,2})\s*day(?:s)?\b", t)
    if m:
        return int(m.group(2))  # default forward

    # weeks
    m = re.search(r"\b(shift|move|push|postpone|delay)\b.*?\b(\d{1,2})\s*week(?:s)?\b.*?\b(forward|ahead|later|back|backward|earlier)\b", t)
    if m:
        n = int(m.group(2)) * 7
        direction = m.group(3)
        return +n if direction in {"forward", "ahead", "later"} else -n

    m = re.search(r"\b(shift|move|push|postpone|delay)\b.*?\bby\s+(\d{1,2})\s*week(?:s)?\b", t)
    if m:
        return int(m.group(2)) * 7

    return None

def _add_days(iso_date: str, delta_days: int) -> str:
    d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return (d + timedelta(days=delta_days)).isoformat()

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _extract_day_numbers(text: str) -> List[int]:
    # supports "day 3", "day3", "day 1 and 2"
    nums = re.findall(r"\bday\s*([0-9]{1,2})\b", text, flags=re.I)
    return [int(n) for n in nums]

def _extract_slot(text: str) -> Optional[str]:
    t = _norm(text)
    for slot in SLOTS:
        if re.search(rf"\b{slot}\b", t):
            return slot
    return None

def _extract_remove_targets(text: str) -> List[str]:
    """
    Capture phrases like:
      remove colombo
      remove "temple of tooth"
      remove restaurants
      delete pinnawala
      drop galle face
    """
    t = _norm(text)
    targets: List[str] = []

    patterns = [
        r"\bremove\s+(.+?)(?:,| and | then | but |\.|$)",
        r"\bdelete\s+(.+?)(?:,| and | then | but |\.|$)",
        r"\bdrop\s+(.+?)(?:,| and | then | but |\.|$)",
        r"\bexclude\s+(.+?)(?:,| and | then | but |\.|$)",
    ]
    for p in patterns:
        m = re.search(p, t)
        if m:
            chunk = m.group(1).strip()
            # avoid capturing "make it 3 days"
            chunk = re.sub(r"\bmake it\b.*$", "", chunk).strip()
            chunk = re.sub(r"\bmake\b.*$", "", chunk).strip()
            if chunk:
                targets.append(chunk)

    # split multi targets: "remove x and y"
    expanded: List[str] = []
    for tg in targets:
        parts = [p.strip() for p in re.split(r"\band\b|\/|&", tg) if p.strip()]
        expanded.extend(parts)

    # de-dupe
    uniq = []
    for x in expanded:
        if x not in uniq:
            uniq.append(x)
    return uniq

def _extract_swap_days(text: str) -> Optional[Tuple[int, int]]:
    """
    "swap day 1 and day 2"
    "swap day 1 with day 2"
    """
    t = _norm(text)
    m = re.search(r"\bswap\s+day\s*([0-9]{1,2})\s+(?:and|with)\s+day\s*([0-9]{1,2})\b", t)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

def _extract_regenerate_day(text: str) -> Optional[int]:
    """
    "redo day 3"
    "regenerate day 2"
    "replan day 4"
    """
    t = _norm(text)
    m = re.search(r"\b(redo|regenerate|replan)\s+day\s*([0-9]{1,2})\b", t)
    if not m:
        return None
    return int(m.group(2))
def _extract_replace_pair(text: str) -> Optional[Tuple[str, str]]:
    """
    "replace colombo with nuwara eliya"
    "replace 'temple of tooth' with 'pinnawala'"
    "swap colombo for nuwara eliya"  (optional)
    """
    t = _norm(text)

    # replace X with Y
    m = re.search(r"\breplace\s+(.+?)\s+with\s+(.+?)(?:,| and | then |\.|$)", t)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # swap X for Y (optional)
    m = re.search(r"\bswap\s+(.+?)\s+for\s+(.+?)(?:,| and | then |\.|$)", t)
    if m:
        return m.group(1).strip(), m.group(2).strip()
def _find_item_id(existing_plan: Dict[str, Any], query: str) -> Optional[str]:
    q = _norm(query)

    # your plan has itinerary list → items → raw.attraction_id and title
    itinerary = (existing_plan or {}).get("itinerary") or []
    for day in itinerary:
        for item in (day.get("items") or []):
            raw = item.get("raw") or {}
            aid = raw.get("attraction_id") or item.get("attraction_id")
            title = item.get("title") or raw.get("title")
            if aid and _norm(aid) == q:
                return str(aid)
            if title and _norm(title) == q:
                return str(aid) if aid else _norm(title)
    return None
    return None
def _extract_move_item(text: str) -> Optional[Dict[str, Any]]:
    """
    "move pinnawala to day 1 morning"
    "move temple of tooth to evening"
    "put galle face on day 2"
    lightweight, uses text query if no stable IDs available.
    """
    t = _norm(text)

    # move/put X to (day N)? (slot)?
    m = re.search(
        r"\b(move|put)\s+(.+?)\s+(?:to|on)\s+(?:day\s*([0-9]{1,2})\s*)?(morning|afternoon|evening|night)?\b",
        t
    )
    if not m:
        return None

    query = m.group(2).strip()
    day = int(m.group(3)) if m.group(3) else None
    slot = m.group(4) if m.group(4) else _extract_slot(t)

    if not query:
        return None

    payload: Dict[str, Any] = {"op": "move_item_by_text", "query": query}
    if day is not None:
        payload["to_day"] = day
    if slot is not None:
        payload["to_slot"] = slot
    return payload

def build_modify_ops(
    parsed_entities: Dict[str, Any],
    preference_overrides: Dict[str, Any],
    raw_text: str,
    existing_plan: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Goal: generate a compact ops list.
    - Always safe: if uncertain, don't create risky ops; keep it in notes.
    - Prefer stable IDs when possible; fallback to *_by_text.
    """
    ops: List[Dict[str, Any]] = []
    text = raw_text or ""
    tnorm = _norm(text)
    # --- NEW: replace X with Y ---
    rp = _extract_replace_pair(text)
    if rp:
        from_q, to_q = rp

        from_id = _find_item_id(existing_plan, from_q)  # tries to map "Colombo" → "colombo"
        if from_id:
            ops.append({"op": "replace_item", "from_id": from_id, "to_query": to_q})
        else:
            # fallback: still do replace by text if you don't have IDs
            ops.append({"op": "replace_item_by_text", "from_query": from_q, "to_query": to_q})

        # optional: usually you want a regen after replacement so schedule is rebuilt
        ops.append({"op": "regenerate_plan"})
    # 0) Detect trip date shifting FIRST (so it doesn't get mistaken as set_days)
    delta = _extract_trip_shift(text)
    if delta is not None:
        base = _plan_start_date(existing_plan) or _extract_iso_date(text)
        if base:
            ops.append({"op": "set_start_date", "start_date": _add_days(base, delta)})
        else:
            # no start_date to anchor on -> safer to regenerate than guess
            ops.append({"op": "regenerate_plan"})
        # IMPORTANT: don't add set_days from entities for shift requests
    else:
        # --- A) Structured ops (from entities) ---
        days = parsed_entities.get("days")
        if isinstance(days, int) and days > 0:
            ops.append({"op": "set_days", "days": days})

        # Only set start_date if the user actually typed a date
        explicit_date = _extract_iso_date(text)
        if explicit_date:
            ops.append({"op": "set_start_date", "start_date": explicit_date})

    # prefer_tags: from entities.tags OR travel_style override
    tags = parsed_entities.get("tags") or []
    if not tags:
        tags = (preference_overrides or {}).get("travel_style") or []
    tags = [t for t in tags if isinstance(t, str) and t.strip()]
    if tags:
        ops.append({"op": "prefer_tags", "tags": tags})

    # --- B) Rule-based intent from raw text ---
    swap = _extract_swap_days(text)
    if swap:
        a, b = swap
        ops.append({"op": "swap_days", "day_a": a, "day_b": b})

    regen_day = _extract_regenerate_day(text)
    if regen_day:
        ops.append({"op": "regenerate_day", "day": regen_day})

    move_op = _extract_move_item(text)
    if move_op:
        ops.append(move_op)

    # remove targets
    remove_targets = _extract_remove_targets(text)
    for target in remove_targets:
        # if user says remove "restaurants" -> treat as tag
        if target in {"restaurants", "restaurant"}:
            ops.append({"op": "remove_by_tag", "tags": ["restaurant"]})
        else:
            ops.append({"op": "remove_items_by_text", "query": target})

    # --- C) Optional: If user says "remove colombo" AND destination is Colombo,
    # recommend a regenerate_plan so recommender can pick a new base city/day-trips.
    tnorm = _norm(text)
    if "remove colombo" in tnorm or "exclude colombo" in tnorm:
        ops.append({"op": "regenerate_plan"})

    # De-dupe simple identical ops
    dedup: List[Dict[str, Any]] = []
    seen = set()
    for op in ops:
        key = str(op)
        if key not in seen:
            dedup.append(op)
            seen.add(key)

    return dedup