"""
Itinerary modification logic.
Works with the dict-based itinerary format produced by build_itinerary_from_payload / build_two_plans_from_payload.
"""

from __future__ import annotations
import math
import logging
from copy import deepcopy
from datetime import date, timedelta, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def modify_itinerary(
    existing_itinerary: Dict[str, Any],
    ops: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Apply modification operations to an existing itinerary.

    Args:
        existing_itinerary: The full itinerary response dict (as returned by build_two_plans_from_payload).
        ops: List of operations from the orchestrator, e.g. [{"op": "set_days", "days": 2}]
        context: Optional context dict with user prefs, session info, etc.

    Returns:
        Modified itinerary dict.
    """
    result = deepcopy(existing_itinerary)

    for operation in ops:
        op_type = operation.get("op")

        if op_type == "set_days":
            target_days = int(operation["days"])
            result = _apply_set_days(result, target_days)
        # Future ops go here:
        # elif op_type == "prefer_tags":
        #     ...
        # elif op_type == "swap_attraction":
        #     ...
        else:
            logger.warning(f"Unknown modify op: {op_type}, skipping.")

    return result


def _apply_set_days(itinerary: Dict[str, Any], target_days: int) -> Dict[str, Any]:
    """
    Adjust the destination_plan (and optionally route plans) to fit `target_days`.
    """
    if target_days < 1:
        raise ValueError("target_days must be >= 1")

    plans = itinerary.get("plans", {})

    # --- Modify destination_plan ---
    dest_plan = plans.get("destination_plan")
    if dest_plan and isinstance(dest_plan, dict):
        itinerary_days = dest_plan.get("itinerary", [])
        if isinstance(itinerary_days, list):
            modified_days = _resize_day_list(itinerary_days, target_days)
            dest_plan["itinerary"] = modified_days
            dest_plan["days"] = target_days

    # --- Update top-level meta ---
    meta = itinerary.get("meta", {})
    meta["days"] = target_days

    # Recalculate start_date-based dates if present
    start_date_str = meta.get("start_date")
    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            _redate_days(dest_plan.get("itinerary", []), start_dt)
        except Exception:
            pass

    return itinerary


def _resize_day_list(
    day_list: List[Dict[str, Any]], target_days: int
) -> List[Dict[str, Any]]:
    """
    Shrink or expand a list of day dicts to match target_days.
    Each day dict may use either "attractions" or "items" as its list key.
    """
    current_days = len(day_list)

    if target_days == current_days:
        return day_list

    # Detect which key the original days use ("items" or "attractions")
    items_key = "attractions"
    for day in day_list:
        if "items" in day:
            items_key = "items"
            break

    # Collect all attractions/items in order
    all_attractions: List[Dict[str, Any]] = []
    for day in day_list:
        attractions = day.get(items_key, []) or day.get("attractions", []) or day.get("items", [])
        if isinstance(attractions, list):
            all_attractions.extend(attractions)

    if not all_attractions:
        # Nothing to redistribute — just return empty days
        return [
            {"day": i + 1, items_key: [], "district": None}
            for i in range(target_days)
        ]

    # Distribute attractions evenly across target_days
    per_day = max(1, math.ceil(len(all_attractions) / target_days))
    new_days: List[Dict[str, Any]] = []
    idx = 0

    for day_num in range(1, target_days + 1):
        chunk = all_attractions[idx : idx + per_day]
        idx += per_day

        # If we've run out of attractions, create a free/explore day
        if not chunk and day_num > 1:
            chunk = [
                {
                    "name": "Free Time / Local Exploration",
                    "type": "leisure",
                    "description": "Explore the area at your own pace, visit local markets, or relax.",
                    "duration_hours": 4.0,
                }
            ]

        # Try to infer district from first attraction
        district = None
        for a in chunk:
            district = a.get("district") or a.get("city")
            if district:
                break

        new_days.append(
            {
                "day": day_num,
                "district": district,
                items_key: chunk,
            }
        )

    return new_days


def _redate_days(
    day_list: List[Dict[str, Any]], start_dt: date
) -> None:
    """Re-assign date strings to each day based on start_dt."""
    for day_dict in day_list:
        day_num = day_dict.get("day", 1)
        day_date = start_dt + timedelta(days=day_num - 1)
        day_dict["date"] = day_date.isoformat()