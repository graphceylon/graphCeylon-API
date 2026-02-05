from typing import Any, Dict
from .travel_mode import TravelMode

def resolve_travel_mode(payload: Dict[str, Any]) -> TravelMode:
    # Prefer explicit destination fields
    dest = str(
        payload.get("destination")
        or payload.get("city")
        or payload.get("destination_city")
        or ""
    ).strip() or "Colombo"

    tm = payload.get("travel_mode") or {}
    geo_mode = (payload.get("geo_scope") or {}).get("mode")

    tm_type = str(tm.get("type") or geo_mode or "city").lower()

    origin_city = str(
        tm.get("origin_city")
        or payload.get("origin_city")
        or payload.get("origin")
        or ""
    ).strip() or None

    include_stops = bool(tm.get("include_stops")) or bool(payload.get("on_the_way"))

    assumptions = []
    origin_conf = "unknown"

    # ✅ If origin provided
    if origin_city:
        origin_conf = "explicit"

        # ✅ Route trip detected (origin != dest) => corridor
        if origin_city.lower() != dest.lower():
            tm_type = "corridor"
            # ✅ default stops ON for corridor trips unless explicitly forced off
            include_stops = True if tm.get("include_stops") is None else bool(tm.get("include_stops"))

    # If user explicitly asked for corridor even without origin
    wants_corridor = (tm_type == "corridor") or include_stops

    # Safe default: destination-only plan
    if not origin_city and not wants_corridor:
        origin_city = dest
        origin_conf = "assumed"
        assumptions.append(f"Assumed you are already in {dest} (destination-only plan).")
        tm_type = "city"

    return TravelMode(
        type="corridor" if wants_corridor else "city",
        origin_city=origin_city,
        destination_city=dest,
        include_stops=bool(include_stops) if wants_corridor else False,
        origin_confidence=origin_conf,
        assumptions=assumptions,
    )
