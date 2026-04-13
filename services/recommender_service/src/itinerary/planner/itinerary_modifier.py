"""
Itinerary modification logic.
Works with the dict-based itinerary format produced by build_itinerary_from_payload / build_two_plans_from_payload.
"""

from __future__ import annotations
import math
import logging
from copy import deepcopy
from datetime import date, timedelta, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

OpHandler = Callable[[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]], Dict[str, Any]]


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
        op_type = str(operation.get("op", "")).strip()
        if not op_type:
            logger.warning("Modify op without 'op' key, skipping: %s", operation)
            continue

        handler = OP_HANDLERS.get(op_type)
        if not handler:
            logger.warning("Unknown modify op: %s, skipping.", op_type)
            _append_meta_note(result, f"Unknown modify op skipped: {op_type}")
            continue

        try:
            result = handler(result, operation, context)
            _record_applied_op(result, operation)
        except Exception as exc:
            logger.exception("Failed to apply modify op '%s': %s", op_type, exc)
            _append_meta_note(result, f"Failed op {op_type}: {exc}")

    return result


def _record_applied_op(itinerary: Dict[str, Any], operation: Dict[str, Any]) -> None:
    meta = itinerary.setdefault("meta", {})
    applied_ops = meta.setdefault("applied_ops", [])
    if isinstance(applied_ops, list):
        applied_ops.append(deepcopy(operation))


def _append_meta_note(itinerary: Dict[str, Any], note: str) -> None:
    meta = itinerary.setdefault("meta", {})
    notes = meta.setdefault("notes", [])
    if isinstance(notes, list):
        notes.append(note)


def _ensure_meta_defaults(itinerary: Dict[str, Any]) -> Dict[str, Any]:
    return itinerary.setdefault("meta", {})


def _get_destination_days(itinerary: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    plans = itinerary.get("plans", {})
    if not isinstance(plans, dict):
        return [], "items"

    dest_plan = plans.get("destination_plan")
    if not isinstance(dest_plan, dict):
        return [], "items"

    day_list = dest_plan.get("itinerary", [])
    if not isinstance(day_list, list):
        return [], "items"

    items_key = "attractions"
    for day in day_list:
        if isinstance(day, dict) and "items" in day:
            items_key = "items"
            break

    return day_list, items_key


def _iter_day_items(day: Dict[str, Any], items_key: str) -> List[Dict[str, Any]]:
    items = day.get(items_key)
    if not isinstance(items, list):
        items = day.get("items")
    if not isinstance(items, list):
        items = day.get("attractions")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _item_matches_text(item: Dict[str, Any], query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return False

    text_candidates = [
        str(item.get("id", "")),
        str(item.get("name", "")),
        str(item.get("title", "")),
        str(item.get("district", "")),
        str(item.get("city", "")),
    ]
    combined = " ".join(text_candidates).lower()
    return q in combined


def _item_has_any_tag(item: Dict[str, Any], tags: List[str]) -> bool:
    wanted = {t.strip().lower() for t in tags if isinstance(t, str) and t.strip()}
    if not wanted:
        return False

    existing_raw = item.get("tags")
    existing: set[str] = set()
    if isinstance(existing_raw, list):
        existing = {str(t).strip().lower() for t in existing_raw}
    elif isinstance(existing_raw, str):
        existing = {existing_raw.strip().lower()}

    if isinstance(item.get("type"), str):
        existing.add(item["type"].strip().lower())

    return bool(existing.intersection(wanted))


def _get_or_create_day(day_list: List[Dict[str, Any]], day_num: int, items_key: str) -> Dict[str, Any]:
    for day in day_list:
        if isinstance(day, dict) and int(day.get("day", 0) or 0) == day_num:
            if not isinstance(day.get(items_key), list):
                day[items_key] = _iter_day_items(day, items_key)
            return day

    new_day: Dict[str, Any] = {"day": day_num, "district": None, items_key: []}
    day_list.append(new_day)
    day_list.sort(key=lambda d: int(d.get("day", 0) or 0))
    return new_day


def _set_day_ordering_and_dates(itinerary: Dict[str, Any]) -> None:
    day_list, _ = _get_destination_days(itinerary)
    if not day_list:
        return

    day_list.sort(key=lambda d: int(d.get("day", 0) or 0))
    for i, day in enumerate(day_list, start=1):
        day["day"] = i

    meta = itinerary.get("meta", {})
    start_date_str = meta.get("start_date") if isinstance(meta, dict) else None
    if isinstance(start_date_str, str):
        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            _redate_days(day_list, start_dt)
        except ValueError:
            logger.warning("Could not redate days, invalid start_date in meta: %s", start_date_str)


def _find_and_remove_item_by_text(
    itinerary: Dict[str, Any], query: str
) -> Optional[Tuple[Dict[str, Any], int]]:
    day_list, items_key = _get_destination_days(itinerary)
    if not day_list:
        return None

    for day in day_list:
        items = _iter_day_items(day, items_key)
        kept: List[Dict[str, Any]] = []
        removed: Optional[Dict[str, Any]] = None
        for item in items:
            if removed is None and _item_matches_text(item, query):
                removed = item
                continue
            kept.append(item)

        if removed is not None:
            day[items_key] = kept
            return removed, int(day.get("day", 0) or 0)

    return None


def _apply_set_days_op(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    target_days = int(operation["days"])
    return _apply_set_days(itinerary, target_days)


def _apply_set_start_date_op(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    new_start = operation.get("start_date")
    if not isinstance(new_start, str) or not new_start.strip():
        raise ValueError("set_start_date requires non-empty start_date")
    return _apply_set_start_date(itinerary, new_start)


def _apply_shift_dates_by_days(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    meta = _ensure_meta_defaults(itinerary)
    delta = int(operation.get("delta", 0))

    start_date_str = meta.get("start_date")
    if not isinstance(start_date_str, str):
        _append_meta_note(itinerary, "shift_dates_by_days skipped: missing meta.start_date")
        return itinerary

    try:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        _append_meta_note(itinerary, "shift_dates_by_days skipped: invalid meta.start_date")
        return itinerary

    shifted_start = start_dt + timedelta(days=delta)
    return _apply_set_start_date(itinerary, shifted_start.isoformat())


def _apply_remove_items_by_text(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    query = str(operation.get("query", "")).strip()
    if not query:
        raise ValueError("remove_items_by_text requires query")

    day_list, items_key = _get_destination_days(itinerary)
    removed_count = 0
    for day in day_list:
        items = _iter_day_items(day, items_key)
        kept = [item for item in items if not _item_matches_text(item, query)]
        removed_count += len(items) - len(kept)
        day[items_key] = kept

    _append_meta_note(itinerary, f"remove_items_by_text removed {removed_count} items for query '{query}'")
    return itinerary


def _apply_remove_by_tag(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    tags = operation.get("tags")
    if not isinstance(tags, list):
        raise ValueError("remove_by_tag requires tags list")

    day_list, items_key = _get_destination_days(itinerary)
    removed_count = 0
    for day in day_list:
        items = _iter_day_items(day, items_key)
        kept = [item for item in items if not _item_has_any_tag(item, tags)]
        removed_count += len(items) - len(kept)
        day[items_key] = kept

    _append_meta_note(itinerary, f"remove_by_tag removed {removed_count} items")
    return itinerary


def _apply_add_items(
    itinerary: Dict[str, Any], operation: Dict[str, Any], context: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    tags = operation.get("tags")
    if not isinstance(tags, list):
        raise ValueError("add_items requires tags list")

    return _apply_prefer_tags(itinerary, {"tags": tags}, context)


def _apply_replace_item(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    from_id = str(operation.get("from_id", "")).strip()
    to_query = str(operation.get("to_query", "")).strip()
    if not from_id or not to_query:
        raise ValueError("replace_item requires from_id and to_query")

    found = _find_and_remove_item_by_text(itinerary, from_id)
    if not found:
        _append_meta_note(itinerary, f"replace_item could not find '{from_id}', requested '{to_query}'")
        _mark_regeneration_needed(itinerary, reason="replace_item")
        return itinerary

    removed_item, day_num = found
    day_list, items_key = _get_destination_days(itinerary)
    target_day = _get_or_create_day(day_list, day_num=max(1, day_num), items_key=items_key)
    placeholder = deepcopy(removed_item)
    placeholder["name"] = to_query
    placeholder["query"] = to_query
    placeholder["placeholder"] = True
    target_day.setdefault(items_key, []).append(placeholder)
    _mark_regeneration_needed(itinerary, reason="replace_item")
    return itinerary


def _apply_swap_days(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    day_a = int(operation.get("day_a"))
    day_b = int(operation.get("day_b"))
    if day_a == day_b:
        return itinerary

    day_list, items_key = _get_destination_days(itinerary)
    if not day_list:
        return itinerary

    a_day = _get_or_create_day(day_list, max(1, day_a), items_key)
    b_day = _get_or_create_day(day_list, max(1, day_b), items_key)

    a_items = list(_iter_day_items(a_day, items_key))
    b_items = list(_iter_day_items(b_day, items_key))
    a_day[items_key], b_day[items_key] = b_items, a_items
    a_day["district"], b_day["district"] = b_day.get("district"), a_day.get("district")

    _set_day_ordering_and_dates(itinerary)
    return itinerary


def _apply_regenerate_day(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    day_num = int(operation.get("day"))
    day_list, items_key = _get_destination_days(itinerary)
    if not day_list:
        return itinerary

    target_day = _get_or_create_day(day_list, max(1, day_num), items_key)
    target_day["needs_regeneration"] = True
    target_day["regen_reason"] = "manual_modify_request"
    _mark_regeneration_needed(itinerary, reason=f"regenerate_day:{day_num}")
    return itinerary


def _apply_move_item_by_text(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    query = str(operation.get("query", "")).strip()
    if not query:
        raise ValueError("move_item_by_text requires query")

    found = _find_and_remove_item_by_text(itinerary, query)
    if not found:
        _append_meta_note(itinerary, f"move_item_by_text: no item matched '{query}'")
        return itinerary

    removed_item, src_day = found
    day_list, items_key = _get_destination_days(itinerary)
    to_day = int(operation.get("to_day", src_day or 1))
    target_day = _get_or_create_day(day_list, max(1, to_day), items_key)

    to_slot = operation.get("to_slot")
    if isinstance(to_slot, str) and to_slot.strip():
        removed_item["slot"] = to_slot.strip().lower()

    target_items = _iter_day_items(target_day, items_key)
    target_items.append(removed_item)
    target_day[items_key] = _order_items_by_slot(target_items)

    _set_day_ordering_and_dates(itinerary)
    return itinerary


def _order_items_by_slot(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    slot_order = {"morning": 1, "afternoon": 2, "evening": 3, "night": 4}

    def _key(item: Dict[str, Any]) -> Tuple[int, str]:
        slot = str(item.get("slot", "")).strip().lower()
        return slot_order.get(slot, 99), str(item.get("name", "")).lower()

    return sorted(items, key=_key)


def _apply_preference_patch(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    patch = operation.get("patch")
    if not isinstance(patch, dict):
        raise ValueError("preference_patch requires patch object")

    meta = _ensure_meta_defaults(itinerary)
    prefs = meta.setdefault("preferences", {})
    if isinstance(prefs, dict):
        prefs.update(patch)

    _mark_regeneration_needed(itinerary, reason="preference_patch")
    return itinerary


def _apply_prefer_tags(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    tags = operation.get("tags")
    if not isinstance(tags, list):
        raise ValueError("prefer_tags requires tags list")

    meta = _ensure_meta_defaults(itinerary)
    prefs = meta.setdefault("preferences", {})
    if not isinstance(prefs, dict):
        prefs = {}
        meta["preferences"] = prefs

    existing = prefs.get("prefer_tags")
    merged: List[str] = []
    if isinstance(existing, list):
        merged.extend([str(t) for t in existing])
    merged.extend([str(t) for t in tags])
    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped: List[str] = []
    for tag in merged:
        key = tag.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(tag)
    prefs["prefer_tags"] = deduped

    _mark_regeneration_needed(itinerary, reason="prefer_tags")
    return itinerary


def _apply_route_patch(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    mode = operation.get("mode")
    if not isinstance(mode, str) or not mode.strip():
        raise ValueError("route_patch requires mode")

    meta = _ensure_meta_defaults(itinerary)
    route = meta.setdefault("route_constraints", {})
    if isinstance(route, dict):
        route["mode"] = mode.strip().lower()

    _mark_regeneration_needed(itinerary, reason="route_patch")
    return itinerary


def _apply_set_max_travel_minutes_per_leg(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    value = int(operation.get("value"))
    if value <= 0:
        raise ValueError("set_max_travel_minutes_per_leg requires value > 0")

    meta = _ensure_meta_defaults(itinerary)
    route = meta.setdefault("route_constraints", {})
    if isinstance(route, dict):
        route["max_travel_minutes_per_leg"] = value

    _mark_regeneration_needed(itinerary, reason="set_max_travel_minutes_per_leg")
    return itinerary


def _apply_regenerate_plan(
    itinerary: Dict[str, Any], operation: Dict[str, Any], _: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    preserve_rules = operation.get("preserve_rules")
    _mark_regeneration_needed(itinerary, reason="regenerate_plan")
    if isinstance(preserve_rules, dict):
        meta = _ensure_meta_defaults(itinerary)
        meta["preserve_rules"] = deepcopy(preserve_rules)
    return itinerary


def _mark_regeneration_needed(itinerary: Dict[str, Any], reason: str) -> None:
    meta = _ensure_meta_defaults(itinerary)
    meta["needs_regeneration"] = True
    reasons = meta.setdefault("regeneration_reasons", [])
    if isinstance(reasons, list):
        reasons.append(reason)


OP_HANDLERS: Dict[str, OpHandler] = {
    "set_days": _apply_set_days_op,
    "set_start_date": _apply_set_start_date_op,
    "shift_dates_by_days": _apply_shift_dates_by_days,
    "remove_items_by_text": _apply_remove_items_by_text,
    "remove_by_tag": _apply_remove_by_tag,
    "add_items": _apply_add_items,
    "replace_item": _apply_replace_item,
    "swap_days": _apply_swap_days,
    "regenerate_day": _apply_regenerate_day,
    "move_item_by_text": _apply_move_item_by_text,
    "preference_patch": _apply_preference_patch,
    "prefer_tags": _apply_prefer_tags,
    "route_patch": _apply_route_patch,
    "set_max_travel_minutes_per_leg": _apply_set_max_travel_minutes_per_leg,
    "regenerate_plan": _apply_regenerate_plan,
}


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


def _apply_set_start_date(itinerary: Dict[str, Any], new_start: str) -> Dict[str, Any]:
    """
    Change the trip start date and re-date all itinerary days accordingly.
    """
    try:
        start_dt = datetime.strptime(new_start, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid start_date format: {new_start!r}  (expected YYYY-MM-DD)")

    meta = itinerary.get("meta", {})
    days = meta.get("days", 1)

    # Update meta dates
    meta["start_date"] = start_dt.isoformat()
    end_dt = start_dt + timedelta(days=max(days, 1) - 1)
    meta["end_date"] = end_dt.isoformat()

    # Re-date destination_plan itinerary
    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    if dest_plan and isinstance(dest_plan, dict):
        dest_plan["start_date"] = start_dt.isoformat()
        itin_days = dest_plan.get("itinerary", [])
        if isinstance(itin_days, list):
            _redate_days(itin_days, start_dt)

    return itinerary


def _redate_days(
    day_list: List[Dict[str, Any]], start_dt: date
) -> None:
    """Re-assign date strings to each day based on start_dt."""
    for i, day_dict in enumerate(day_list):
        day_num = day_dict.get("day") or (i + 1)
        day_date = start_dt + timedelta(days=day_num - 1)
        day_dict["date"] = day_date.isoformat()