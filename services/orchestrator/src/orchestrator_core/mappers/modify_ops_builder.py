import re
from typing import Any, Dict, List, Optional, Tuple

SLOTS = {"morning", "afternoon", "evening", "night"}

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
        r"\b(move|put|shift)\s+(.+?)\s+(?:to|on)\s+(?:day\s*([0-9]{1,2})\s*)?(morning|afternoon|evening|night)?\b",
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

    # --- A) Structured ops (from entities) ---
    days = parsed_entities.get("days")
    if isinstance(days, int) and days > 0:
        ops.append({"op": "set_days", "days": days})

    # Only set start_date if the USER explicitly said a start date.
    # If entities.start_date is None, do nothing.
    start_date = parsed_entities.get("start_date")
    if start_date:
        ops.append({"op": "set_start_date", "start_date": str(start_date)})

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