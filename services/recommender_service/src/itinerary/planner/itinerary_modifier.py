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
        ops: List of operations from the orchestrator, e.g. [
            {"op": "set_days", "days": 2},
            {"op": "remove_items_by_text", "query": "colombo"},
            {"op": "remove_by_tag", "tags": ["restaurant"]},
            {"op": "add_items", "tags": ["nature"]},
            {"op": "replace_item", "from_id": "colombo", "to_query": "Nuwara Eliya"},
            {"op": "regenerate_plan"}
        ]
        context: Optional context dict with user prefs, session info, etc.

    Returns:
        Modified itinerary dict.
    """
    result = deepcopy(existing_itinerary)

    for operation in ops:
        op_type = operation.get("op")

        try:
            if op_type == "set_days":
                target_days = int(operation["days"])
                result = _apply_set_days(result, target_days)
            
            elif op_type == "set_start_date":
                new_start = operation.get("start_date")
                if new_start:
                    result = _apply_set_start_date(result, new_start)
            
            elif op_type == "remove_items_by_text":
                query = operation.get("query", "")
                result = _apply_remove_items_by_text(result, query)
            
            elif op_type == "remove_by_tag":
                tags = operation.get("tags", [])
                result = _apply_remove_by_tag(result, tags)
            
            elif op_type == "add_items":
                tags = operation.get("tags", [])
                result = _apply_add_items(result, tags, context)
            
            elif op_type == "replace_item":
                from_id = operation.get("from_id", "")
                to_query = operation.get("to_query", "")
                
                # Check if this is actually an origin_city replacement
                meta = result.get("meta", {})
                current_origin = str(meta.get("origin_city") or "").strip()
                
                # If from_id matches origin_city, treat as origin_city replacement
                if current_origin.lower() == from_id.lower():
                    logger.info(f"Detected origin_city replacement: {from_id} → {to_query}")
                    result = _apply_replace_origin_city(result, from_id, to_query)
                else:
                    # Otherwise treat as regular item replacement
                    result = _apply_replace_item(result, from_id, to_query)
            
            elif op_type == "regenerate_plan":
                result = _apply_regenerate_plan(result)
            
            else:
                logger.warning(f"Unknown modify op: {op_type}, skipping.")
        
        except Exception as e:
            logger.error(f"Error applying operation {op_type}: {e}")
            raise

    return result


# ============================================================
# EXISTING OPERATIONS
# ============================================================

def _apply_set_days(itinerary: Dict[str, Any], target_days: int) -> Dict[str, Any]:
    """
    Adjust the destination_plan (and optionally route plans) to fit `target_days`.
    When expanding days, tries to use unscheduled candidates before creating Free Time placeholders.
    """
    if target_days < 1:
        raise ValueError("target_days must be >= 1")

    plans = itinerary.get("plans", {})

    # --- Modify destination_plan ---
    dest_plan = plans.get("destination_plan")
    if dest_plan and isinstance(dest_plan, dict):
        itinerary_days = dest_plan.get("itinerary", [])
        if isinstance(itinerary_days, list):
            # Get available candidates from top-level itinerary or dest_plan
            available_candidates = itinerary.get("_available_candidates", []) or dest_plan.get("_available_candidates", [])
            modified_days = _resize_day_list(itinerary_days, target_days, available_candidates)
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
    day_list: List[Dict[str, Any]], 
    target_days: int,
    available_candidates: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Shrink or expand a list of day dicts to match target_days.
    When expanding, pulls from available_candidates (unscheduled attractions) before creating Free Time.
    
    Priority:
    1. Use attractions already scheduled
    2. If expanding, pull from available_candidates (e.g., ranked but unscheduled from KG)
    3. If still need more, create Free Time / Local Exploration placeholders
    """
    if available_candidates is None:
        available_candidates = []
    
    current_days = len(day_list)

    if target_days == current_days:
        return day_list

    # Detect which key the original days use ("items" or "attractions")
    items_key = "attractions"
    for day in day_list:
        if "items" in day:
            items_key = "items"
            break

    # Collect all attractions/items currently scheduled
    all_attractions: List[Dict[str, Any]] = []
    for day in day_list:
        attractions = day.get(items_key, []) or day.get("attractions", []) or day.get("items", [])
        if isinstance(attractions, list):
            all_attractions.extend(attractions)

    # If expanding (target_days > current_days), add unscheduled candidates
    if target_days > current_days and available_candidates:
        num_to_add = (target_days - current_days) * max(1, len(all_attractions) // max(current_days, 1))
        candidates_to_use = available_candidates[:num_to_add]
        logger.info(
            f"set_days expanding {current_days}→{target_days}: "
            f"using {len(candidates_to_use)} unscheduled candidates from KG results"
        )
        all_attractions.extend(candidates_to_use)

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


# ============================================================
# NEW OPERATIONS: Remove / Add / Replace
# ============================================================

def _get_items_key(day: Dict[str, Any]) -> str:
    """Detect whether a day uses 'items' or 'attractions' key."""
    if "items" in day:
        return "items"
    elif "attractions" in day:
        return "attractions"
    return "items"  # default


def _extract_all_items(itinerary: Dict[str, Any]) -> tuple[List[Dict[str, Any]], str]:
    """
    Extract all attractions/items from the destination plan.
    Returns (flat_list, items_key).
    """
    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    
    all_items: List[Dict[str, Any]] = []
    items_key = "items"
    
    if dest_plan and isinstance(dest_plan, dict):
        itin_days = dest_plan.get("itinerary", [])
        if isinstance(itin_days, list) and itin_days:
            items_key = _get_items_key(itin_days[0])
            
            for day in itin_days:
                day_items = day.get(items_key, []) or day.get("attractions", []) or day.get("items", [])
                if isinstance(day_items, list):
                    all_items.extend(day_items)
    
    return all_items, items_key


def _text_matches(item: Dict[str, Any], query: str) -> bool:
    """
    Check if an item matches a text query (case-insensitive).
    Searches in: name, title, city, district, category, description.
    """
    query_lower = query.lower().strip()
    if not query_lower:
        return False
    
    searchable_fields = [
        "name", "title", "city", "district", "category", 
        "description", "poi_id", "attraction_id"
    ]
    
    for field in searchable_fields:
        value = str(item.get(field) or "").lower()
        if query_lower in value:
            return True
    
    return False


def _item_has_tag(item: Dict[str, Any], tags: List[str]) -> bool:
    """
    Check if an item has any of the specified tags.
    Searches in item's tags and category.
    """
    item_tags = item.get("tags") or []
    if isinstance(item_tags, str):
        item_tags = [item_tags]
    
    item_category = str(item.get("category") or "").lower()
    
    for tag in tags:
        tag_lower = tag.lower().strip()
        # Check either in tags list or category
        if any(tag_lower == t.lower().strip() for t in item_tags):
            return True
        if tag_lower in item_category:
            return True
    
    return False


def _apply_remove_items_by_text(
    itinerary: Dict[str, Any], query: str
) -> Dict[str, Any]:
    """
    Remove all items matching the text query from the destination plan.
    Then redistributes remaining items evenly across days.
    """
    if not query or not query.strip():
        logger.warning("remove_items_by_text: empty query, skipping")
        return itinerary
    
    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    
    if not dest_plan or not isinstance(dest_plan, dict):
        return itinerary
    
    itin_days = dest_plan.get("itinerary", [])
    if not isinstance(itin_days, list):
        return itinerary
    
    items_key = _get_items_key(itin_days[0]) if itin_days else "items"
    total_target_days = len(itin_days)
    
    # Collect all items and filter out matches
    remaining_items: List[Dict[str, Any]] = []
    removed_count = 0
    
    for day in itin_days:
        day_items = day.get(items_key, []) or []
        for item in day_items:
            if _text_matches(item, query):
                removed_count += 1
                logger.info(f"Removed item: {item.get('title') or item.get('name')}")
            else:
                remaining_items.append(item)
    
    logger.info(f"Removed {removed_count} items matching '{query}'")
    
    # Re-distribute remaining items across days
    if not remaining_items:
        # All items removed — create free days
        new_days = [
            {
                "day": i + 1,
                "date": d.get("date"),
                "district": None,
                items_key: [
                    {
                        "name": "Free Time / Local Exploration",
                        "type": "leisure",
                        "description": "Explore the area at your own pace.",
                        "duration_hours": 4.0,
                    }
                ],
            }
            for i, d in enumerate(itin_days)
        ]
    else:
        per_day = max(1, math.ceil(len(remaining_items) / total_target_days))
        new_days: List[Dict[str, Any]] = []
        idx = 0
        
        for i, orig_day in enumerate(itin_days):
            day_num = i + 1
            chunk = remaining_items[idx : idx + per_day]
            idx += per_day
            
            if not chunk and day_num > 1:
                chunk = [
                    {
                        "name": "Free Time / Local Exploration",
                        "type": "leisure",
                        "description": "Explore at your own pace.",
                        "duration_hours": 4.0,
                    }
                ]
            
            district = None
            if chunk:
                district = chunk[0].get("district") or chunk[0].get("city")
            
            new_days.append({
                "day": day_num,
                "date": orig_day.get("date"),
                "city": orig_day.get("city"),
                "district": district,
                items_key: chunk,
            })
    
    dest_plan["itinerary"] = new_days
    return itinerary


def _apply_remove_by_tag(
    itinerary: Dict[str, Any], tags: List[str]
) -> Dict[str, Any]:
    """
    Remove all items with specified tags from the destination plan.
    Then redistributes remaining items evenly across days.
    """
    if not tags or not any(t.strip() for t in tags):
        logger.warning("remove_by_tag: empty tags, skipping")
        return itinerary
    
    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    
    if not dest_plan or not isinstance(dest_plan, dict):
        return itinerary
    
    itin_days = dest_plan.get("itinerary", [])
    if not isinstance(itin_days, list):
        return itinerary
    
    items_key = _get_items_key(itin_days[0]) if itin_days else "items"
    total_target_days = len(itin_days)
    
    # Collect all items and filter out matches
    remaining_items: List[Dict[str, Any]] = []
    removed_count = 0
    
    for day in itin_days:
        day_items = day.get(items_key, []) or []
        for item in day_items:
            if _item_has_tag(item, tags):
                removed_count += 1
                logger.info(f"Removed item with tags {tags}: {item.get('title') or item.get('name')}")
            else:
                remaining_items.append(item)
    
    logger.info(f"Removed {removed_count} items with tags {tags}")
    
    # Re-distribute remaining items across days
    if not remaining_items:
        new_days = [
            {
                "day": i + 1,
                "date": d.get("date"),
                "district": None,
                items_key: [
                    {
                        "name": "Free Time / Local Exploration",
                        "type": "leisure",
                        "description": "Explore the area at your own pace.",
                        "duration_hours": 4.0,
                    }
                ],
            }
            for i, d in enumerate(itin_days)
        ]
    else:
        per_day = max(1, math.ceil(len(remaining_items) / total_target_days))
        new_days: List[Dict[str, Any]] = []
        idx = 0
        
        for i, orig_day in enumerate(itin_days):
            day_num = i + 1
            chunk = remaining_items[idx : idx + per_day]
            idx += per_day
            
            if not chunk and day_num > 1:
                chunk = [
                    {
                        "name": "Free Time / Local Exploration",
                        "type": "leisure",
                        "description": "Explore at your own pace.",
                        "duration_hours": 4.0,
                    }
                ]
            
            district = None
            if chunk:
                district = chunk[0].get("district") or chunk[0].get("city")
            
            new_days.append({
                "day": day_num,
                "date": orig_day.get("date"),
                "city": orig_day.get("city"),
                "district": district,
                items_key: chunk,
            })
    
    dest_plan["itinerary"] = new_days
    return itinerary


def _apply_add_items(
    itinerary: Dict[str, Any], tags: List[str], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Add new items with specified tags to the itinerary.
    
    NOTE: In a real implementation, this would fetch new items from the KG.
    For now, it logs a suggestion and returns unchanged itinerary.
    In production, you should:
    1. Query KG with the tag/category filter
    2. Create new candidates
    3. Score and rank them
    4. Distribute across days
    """
    if not tags or not any(t.strip() for t in tags):
        logger.warning("add_items: empty tags, skipping")
        return itinerary
    
    logger.info(f"add_items: Would fetch new items with tags {tags}")
    logger.info(f"  [TODO] Implement KG query to fetch attractions with tags: {tags}")
    logger.info(f"  [TODO] Currently returning itinerary unchanged")
    
    # Placeholder: In a real scenario, call your KG to fetch new items
    # For example:
    #   new_candidates = fetch_attractions_by_tags(tags, ...)
    #   scored_candidates = score_candidates(new_candidates, context, ...)
    #   return _add_scored_candidates_to_itinerary(itinerary, scored_candidates)
    
    return itinerary


def _apply_replace_item(
    itinerary: Dict[str, Any], from_id: str, to_query: str
) -> Dict[str, Any]:
    """
    Replace an item (matched by ID/name) with a new item (matched by query text).
    
    Strategy:
    1. Find item matching from_id
    2. Remove it
    3. Try to find a replacement matching to_query
    4. If replacement found, insert at same position; otherwise redistribute
    
    NOTE: Like add_items, this would ideally query the KG for better candidates.
    For now, it performs a simple text-based search within available items or logs a placeholder.
    """
    if not from_id or not to_query:
        logger.warning("replace_item: missing from_id or to_query, skipping")
        return itinerary
    
    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    
    if not dest_plan or not isinstance(dest_plan, dict):
        return itinerary
    
    itin_days = dest_plan.get("itinerary", [])
    if not isinstance(itin_days, list):
        return itinerary
    
    items_key = _get_items_key(itin_days[0]) if itin_days else "items"
    
    # Find and remove the item matching from_id
    removed_item = None
    removed_day_idx = None
    removed_item_idx = None
    
    for day_idx, day in enumerate(itin_days):
        day_items = day.get(items_key, []) or []
        for item_idx, item in enumerate(day_items):
            if _text_matches(item, from_id):
                removed_item = item
                removed_day_idx = day_idx
                removed_item_idx = item_idx
                break
        if removed_item:
            break
    
    if removed_item is None:
        logger.warning(f"replace_item: could not find item matching '{from_id}'")
        return itinerary
    
    logger.info(f"Removing item: {removed_item.get('title') or removed_item.get('name')}")
    
    # Remove from the day
    day_items = itin_days[removed_day_idx].get(items_key, []) or []
    day_items.pop(removed_item_idx)
    
    # Try to find a replacement candidate
    # First check if to_query matches an existing unscheduled item or KG item
    # For now, create a placeholder or log the need to query KG
    
    replacement_item = None
    
    # Strategy 1: Create a basic placeholder with the query as the name
    # In production, query KG to find real attractions
    replacement_item = {
        "name": to_query,
        "title": to_query,
        "type": "attraction",
        "description": f"Attraction related to {to_query}",
        "district": removed_item.get("district"),
        "city": removed_item.get("city"),
        "_note": "Placeholder: KG query needed to get full details",
    }
    
    logger.info(f"Adding replacement item: {to_query}")
    
    # Insert at the same position
    if day_items is not None:
        day_items.insert(removed_item_idx, replacement_item)
    else:
        day_items = [replacement_item]
        itin_days[removed_day_idx][items_key] = day_items
    
    return itinerary
def _apply_replace_origin_city(
    itinerary: Dict[str, Any], from_city: str, to_city: str
) -> Dict[str, Any]:
    """
    Replace the origin_city in metadata and update corridor plans if they exist.
    
    When origin_city changes:
    1. Update meta.origin_city
    2. Invalidate outbound/return corridor plans (they would be from old origin)
    3. Mark for regeneration of route plans
    """
    if not from_city or not to_city:
        logger.warning("replace_origin_city: missing from_city or to_city, skipping")
        return itinerary
    
    # Check if from_city matches current origin_city
    meta = itinerary.get("meta", {})
    current_origin = str(meta.get("origin_city") or "").strip()
    from_city_norm = from_city.strip().lower()
    
    if current_origin.lower() != from_city_norm:
        logger.warning(
            f"replace_origin_city: from_city '{from_city}' doesn't match current "
            f"origin_city '{current_origin}'"
        )
        return itinerary
    
    # Update origin_city
    meta["origin_city"] = to_city
    logger.info(f"Replaced origin_city: {from_city} → {to_city}")
    
    # Invalidate outbound/return plans (they'd be outdated with new origin)
    plans = itinerary.get("plans", {})
    if plans.get("outbound_plan"):
        plans["outbound_plan"] = None
        logger.info("Cleared outbound_plan (will need regeneration with new origin)")
    if plans.get("return_plan"):
        plans["return_plan"] = None
        logger.info("Cleared return_plan (will need regeneration with new origin)")
    if plans.get("route_plan"):
        plans["route_plan"] = None
        logger.info("Cleared route_plan (will need regeneration with new origin)")
    if plans.get("route_return_plan"):
        plans["route_return_plan"] = None
        logger.info("Cleared route_return_plan (will need regeneration with new origin)")
    
    # Mark for reconstruction
    meta["_needs_corridor_regeneration"] = True
    
    return itinerary

def _apply_regenerate_plan(itinerary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Regenerate the plan by re-distributing items and optionally re-scoring.
    
    This operation:
    1. Collects all current items
    2. Re-distributes them evenly across days (as set in meta.days)
    3. Optionally re-scores items based on thematic alignment (if implemented)
    
    NOTE: For full regeneration with new candidates, you would need to
    call the planner pipeline again. This is a simpler redistribution.
    """
    all_items, items_key = _extract_all_items(itinerary)
    target_days = itinerary.get("meta", {}).get("days", 3)
    
    if target_days < 1:
        target_days = 1
    
    logger.info(f"Regenerating plan: redistributing {len(all_items)} items across {target_days} days")
    
    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    
    if not dest_plan:
        return itinerary
    
    itin_days = dest_plan.get("itinerary", []) or []
    
    if not all_items:
        # No items to redistribute — fill with free days
        new_days = [
            {
                "day": i + 1,
                "date": (itin_days[i].get("date") if i < len(itin_days) else None),
                "district": None,
                items_key: [
                    {
                        "name": "Free Time / Local Exploration",
                        "type": "leisure",
                        "description": "Explore the area at your own pace.",
                        "duration_hours": 4.0,
                    }
                ],
            }
            for i in range(target_days)
        ]
    else:
        per_day = max(1, math.ceil(len(all_items) / target_days))
        new_days: List[Dict[str, Any]] = []
        idx = 0
        
        for day_num in range(1, target_days + 1):
            chunk = all_items[idx : idx + per_day]
            idx += per_day
            
            if not chunk and day_num > 1:
                chunk = [
                    {
                        "name": "Free Time / Local Exploration",
                        "type": "leisure",
                        "description": "Explore at your own pace.",
                        "duration_hours": 4.0,
                    }
                ]
            
            # Infer district from first item
            district = None
            if chunk:
                district = chunk[0].get("district") or chunk[0].get("city")
            
            # Preserve date if available
            orig_day = itin_days[day_num - 1] if day_num - 1 < len(itin_days) else {}
            day_date = orig_day.get("date")
            if not day_date and day_num <= len(itin_days):
                day_date = itin_days[day_num - 1].get("date")
            
            new_days.append({
                "day": day_num,
                "date": day_date,
                "city": orig_day.get("city"),
                "district": district,
                items_key: chunk,
            })
    
    dest_plan["itinerary"] = new_days
    dest_plan["days"] = target_days
    
    return itinerary