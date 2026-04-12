from typing import Any, Dict
from .travel_mode import TravelMode

def resolve_travel_mode(payload: Dict[str, Any]) -> TravelMode:
    # ✅ PRESERVE None for vector search mode (multi-city discovery)
    # Only default to Colombo if explicitly needed later
    dest_candidate = str(
        payload.get("destination")
        or payload.get("city")
        or payload.get("destination_city")
        or ""
    ).strip()
    dest = dest_candidate if dest_candidate else None  # Keep None for vector search

    tm = payload.get("travel_mode") or {}
    geo_mode = (payload.get("geo_scope") or {}).get("mode")

    # ✅ read origin early (before any returns)
    origin_city = str(
        tm.get("origin_city")
        or payload.get("origin_city")
        or payload.get("origin")
        or ""
    ).strip() or None

    include_stops = bool(tm.get("include_stops")) or bool(payload.get("on_the_way"))

    # ✅ ONLY treat "city" as a hard override if the CALLER explicitly set travel_mode.type
    explicit_tm_type = (tm.get("type") or "")
    explicit_tm_type = str(explicit_tm_type).lower().strip() if explicit_tm_type else None

    # If caller explicitly forced city mode, respect it (even if origin exists)
    if explicit_tm_type == "city":
        return TravelMode(
            type="city",
            origin_city=origin_city,        # keep it for logging/debug if you want
            destination_city=dest,          # May be None for vector search
            include_stops=False,
            origin_confidence="explicit" if origin_city else "unknown",
            assumptions=[],
        )

    # Otherwise: infer mode from origin/dest + include_stops + geo_scope
    tm_type = str(tm.get("type") or geo_mode or "city").lower()

    assumptions = []
    origin_conf = "unknown"

    if origin_city:
        origin_conf = "explicit"
        # ✅ Only compare if dest exists
        if dest and origin_city.lower() != dest.lower():
            tm_type = "corridor"
            # default include_stops True unless explicitly false
            if tm.get("include_stops") is None:
                include_stops = True
            else:
                include_stops = bool(tm.get("include_stops"))

    wants_corridor = (tm_type == "corridor") or include_stops

    if not origin_city and not wants_corridor:
        # ✅ Only set origin_city = dest if dest exists
        if dest:
            origin_city = dest
            origin_conf = "assumed"
            assumptions.append(f"Assumed you are already in {dest} (destination-only plan).")
        tm_type = "city"

    return TravelMode(
        type="corridor" if wants_corridor else "city",
        origin_city=origin_city,
        destination_city=dest,             # May be None for vector search
        include_stops=bool(include_stops) if wants_corridor else False,
        origin_confidence=origin_conf,
        assumptions=assumptions,
    )