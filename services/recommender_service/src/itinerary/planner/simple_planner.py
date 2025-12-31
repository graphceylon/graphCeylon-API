from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List


def _date_range(start_date: str, days: int) -> List[str]:
    s = datetime.fromisoformat(start_date).date()
    return [(s + timedelta(days=i)).isoformat() for i in range(days)]


def build_itinerary(
    ranked_attractions: List[Dict[str, Any]],
    days: int,
    start_date: str,
    final_prefs: Dict[str, Any],
) -> Dict[str, Any]:
    """
    MVP planner:
    - 2 slots per day: morning + afternoon
    - Fill in ranked order
    - Applies simple preference rules:
        * relaxed pace => 1 POI/day
        * avoid crowds => push VeryHigh/Extreme to later slots (soft)
    """
    pace = (final_prefs.get("pace_preference") or "").lower()
    avoid_crowds = bool(final_prefs.get("avoid_crowds") or False)

    # slots/day
    slots_per_day = 1 if pace == "relaxed" else 2
    need = days * slots_per_day

    chosen = ranked_attractions[:need]

    # soft crowd-aware rearrange (only if avoid_crowds)
    if avoid_crowds:
        def crowd_bad(p):
            lvl = (p.get("context", {}).get("crowd", {}).get("level") or "").lower()
            return lvl in ("veryhigh", "extreme")
        good = [p for p in chosen if not crowd_bad(p)]
        bad = [p for p in chosen if crowd_bad(p)]
        chosen = good + bad

    dates = _date_range(start_date, days)

    out_days: List[Dict[str, Any]] = []
    idx = 0
    for d in dates:
        day_plan = {"date": d, "morning": None, "afternoon": None}

        if idx < len(chosen):
            day_plan["morning"] = chosen[idx]
            idx += 1

        if slots_per_day == 2 and idx < len(chosen):
            day_plan["afternoon"] = chosen[idx]
            idx += 1

        out_days.append(day_plan)

    return {
        "days": out_days,
        "slots_per_day": slots_per_day,
        "num_selected": len(chosen),
    }
