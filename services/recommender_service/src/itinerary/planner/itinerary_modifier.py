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
    result = deepcopy(existing_itinerary)

    for operation in ops:
        op_type = operation.get("op")

        if op_type == "set_days":
            target_days = int(operation["days"])
            result = _apply_set_days(result, target_days, context=context)

        elif op_type == "set_start_date":
            new_start = operation.get("start_date")
            if new_start:
                result = _apply_set_start_date(result, new_start)

        elif op_type == "remove_items_by_text":
            query = operation.get("query", "")
            result = _apply_remove_items_by_text(result, query)

        elif op_type == "prefer_tags":
            tags = operation.get("tags", [])
            result = _apply_prefer_tags(result, tags)

        elif op_type == "add_category_places":
            tags = operation.get("tags", [])
            result = _apply_add_category_places(result, tags, context=context)

        elif op_type == "swap_days":
            day_a = int(operation.get("day_a", 0))
            day_b = int(operation.get("day_b", 0))
            if day_a and day_b and day_a != day_b:
                result = _apply_swap_days(result, day_a, day_b)

        elif op_type == "regenerate_plan":
            logger.info("regenerate_plan op — returning existing plan unchanged")

        else:
            logger.warning(f"Unknown modify op: {op_type}, skipping.")

    return result


def _get_used_attraction_ids(dest_plan: Dict[str, Any]) -> set:
    """Collect all attraction IDs already in the plan to avoid duplicates."""
    used = set()
    for day in (dest_plan.get("itinerary") or []):
        for item in (day.get("items") or day.get("attractions") or []):
            aid = item.get("attraction_id")
            if aid:
                used.add(aid)
    return used


def _fetch_extra_attractions(
    city: str,
    country: str,
    used_ids: set,
    needed: int,
    context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch fresh attractions from KG for the given city,
    excluding already-used IDs.
    Uses the same fetch_city_attractions_from_kg from itinerary_planner.
    """
    try:
        from services.recommender_service.src.itinerary.planner.itinerary_planner import (
            fetch_city_attractions_from_kg,
            _eco_score_hint,
            extract_priorities,
            compute_rank_score,
            _theme_alignment_score,
            _geo_fit_score,
            _title_quality_penalty,
        )
        from services.recommender_service.src.itinerary.enrichment.enrich_candidates import (
            enrich_and_rerank_candidates,
            EnrichConfig,
        )

        payload = dict(context or {})
        payload.setdefault("city", city)
        payload.setdefault("destination", city)
        payload.setdefault("country", country)

        candidates, _ = fetch_city_attractions_from_kg(
            city=city,
            country=country,
            limit=max(needed * 4, 40),  # fetch more than needed to have options
            timeout=90.0,
            payload=payload,
        )

        # Filter out already-used attractions
        candidates = [
            c for c in candidates
            if c.get("attraction_id") not in used_ids
        ]

        if not candidates:
            return []

        # Basic scoring using planner logic
        for c in candidates:
            c["_eco_hint"] = _eco_score_hint(c)
            c["_score"] = float(c.get("_score", 0.0))

        # Enrich and rerank
        reranked = enrich_and_rerank_candidates(
            candidates=candidates,
            payload=payload,
            cfg=EnrichConfig(
                w_sustainability=1.2,
                w_crowd_avoid=0.8,
                w_rain_avoid=0.6,
            ),
            day_offset=0,
        )

        priorities = extract_priorities(payload)
        eco_pref = float(payload.get("eco_preference") or 0.5)

        for c in reranked:
            retrieval = float(c.get("_retrieval_score", c.get("_final_score", 0.0)))
            theme_align = _theme_alignment_score(c, payload)
            geo_fit = _geo_fit_score(c, destination_city=city, days=3)
            title_penalty = _title_quality_penalty(c)

            c["_planner_final"] = (
                (0.40 * retrieval)
                + (0.25 * float(c.get("_final_score", 0.0)))
                + (0.25 * theme_align)
                + (0.10 * geo_fit)
                - title_penalty
            )

        reranked.sort(key=lambda x: float(x.get("_planner_final", 0.0)), reverse=True)

        logger.info(
            f"[set_days expand] fetched {len(candidates)} new attractions "
            f"for city='{city}', returning top {needed}"
        )

        return reranked[:needed]

    except Exception as e:
        logger.warning(f"[set_days expand] KG fetch failed: {e} — will use placeholders")
        return []


def _apply_set_days(
    itinerary: Dict[str, Any],
    target_days: int,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if target_days < 1:
        raise ValueError("target_days must be >= 1")

    plans = itinerary.get("plans", {})
    meta = itinerary.get("meta", {})

    dest_plan = plans.get("destination_plan")
    if not dest_plan or not isinstance(dest_plan, dict):
        meta["days"] = target_days
        return itinerary

    itin_days = dest_plan.get("itinerary", [])
    current_days = len(itin_days)

    # ✅ FIX NULL DAY NUMBERS FIRST
    for i, day in enumerate(itin_days):
        if day.get("day") is None:
            day["day"] = i + 1

    # ── Detect items key ──────────────────────────────────────
    items_key = "attractions"
    for day in itin_days:
        if "items" in day:
            items_key = "items"
            break

    if target_days == current_days:
        meta["days"] = target_days
        return itinerary

    # ── SHRINKING ─────────────────────────────────────────────
    # SHRINKING with redistribution
    if target_days < current_days:
        # Collect ALL attractions from all days
        all_attractions = []
        for day in itin_days:
            items = day.get(items_key) or day.get("attractions") or day.get("items") or []
            all_attractions.extend(items)

        # Sort by score to keep the best ones
        all_attractions.sort(
            key=lambda x: float(x.get("_planner_final") or x.get("rank_score_final") or x.get("rating") or 0),
            reverse=True
        )

        # Redistribute top attractions across target_days
        per_day = max(2, math.ceil(len(all_attractions) / target_days))
        new_days = []
        idx = 0

        for day_num in range(1, target_days + 1):
            chunk = all_attractions[idx: idx + per_day]
            idx += per_day

            district = None
            for a in chunk:
                district = a.get("district") or a.get("city")
                if district:
                    break

            new_days.append({
                "day": day_num,
                "district": district,
                items_key: chunk,
            })

        dest_plan["itinerary"] = new_days
        dest_plan["days"] = target_days
        meta["days"] = target_days

        start_date_str = meta.get("start_date")
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                _redate_days(dest_plan["itinerary"], start_dt)
            except Exception:
                pass

        return itinerary

    # ── EXPANDING ─────────────────────────────────────────────
    # ── EXPANDING ─────────────────────────────────────────────
        # ── EXPANDING ─────────────────────────────────────────────
    extra_days_needed = target_days - current_days

    city = (
        meta.get("destination")
        or dest_plan.get("destination")
        or (context or {}).get("city")
        or (context or {}).get("destination")
        or ""
    )
    country = (context or {}).get("country") or meta.get("country") or "Sri Lanka"

    existing_counts = []
    for day in itin_days:
        items = day.get(items_key) or day.get("attractions") or day.get("items") or []
        if items:
            existing_counts.append(len(items))

    existing_per_day = (
        max(1, round(sum(existing_counts) / len(existing_counts)))
        if existing_counts else 2
    )
    needed = extra_days_needed * existing_per_day
    logger.info(f"[set_days expand] target_days={target_days}, current_days={current_days}")
    logger.info(f"[set_days expand] city={city}, country={country}")
    logger.info(f"[set_days expand] needed attractions={needed}")

    kg_succeeded = False
    new_attractions = []

    if city:
        used_ids = _get_used_attraction_ids(dest_plan)

        kg_context = dict(context or {})
        kg_context.setdefault("city", city)
        kg_context.setdefault("destination", city)
        kg_context.setdefault("country", country)

        if meta.get("start_date"):
            kg_context.setdefault("start_date", meta.get("start_date"))

        new_attractions = _fetch_extra_attractions(
            city=city,
            country=country,
            used_ids=used_ids,
            needed=needed,
            context=kg_context,
        )
        kg_succeeded = len(new_attractions) > 0
        logger.info(f"[set_days expand] KG returned {len(new_attractions)} attractions")
        logger.info(f"[set_days expand] kg_succeeded={kg_succeeded}")

    # ✅ KG failed — fall back to redistribution
    if not kg_succeeded:
        logger.info("[set_days expand] KG failed — falling back to redistribution")

        all_attractions = []
        for day in itin_days:
            items = day.get(items_key) or day.get("attractions") or day.get("items") or []
            all_attractions.extend(items)

        per_day = max(1, math.ceil(len(all_attractions) / target_days))
        new_days = []
        idx = 0

        for day_num in range(1, target_days + 1):
            chunk = all_attractions[idx: idx + per_day]
            idx += per_day

            if not chunk:
                chunk = [
                    {
                        "name": "Free Time / Local Exploration",
                        "type": "leisure",
                        "description": "Explore the area at your own pace, visit local markets, or relax.",
                        "duration_hours": 4.0,
                    }
                ]

            district = None
            for a in chunk:
                district = a.get("district") or a.get("city")
                if district:
                    break

            new_days.append({
                "day": day_num,
                "district": district,
                items_key: chunk,
            })

        dest_plan["itinerary"] = new_days
        dest_plan["days"] = target_days
        meta["days"] = target_days

        start_date_str = meta.get("start_date")
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                _redate_days(dest_plan["itinerary"], start_dt)
            except Exception:
                pass

        return itinerary

    # ✅ KG succeeded — append new days with real attractions
    start_date_str = meta.get("start_date")
    start_dt = None
    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except Exception:
            pass

    idx = 0
    for day_num in range(current_days + 1, target_days + 1):
        chunk = new_attractions[idx: idx + existing_per_day]
        idx += existing_per_day

        if not chunk:
            chunk = [
                {
                    "name": "Free Time / Local Exploration",
                    "type": "leisure",
                    "description": "Explore the area at your own pace, visit local markets, or relax.",
                    "duration_hours": 4.0,
                }
            ]

        district = None
        for a in chunk:
            district = a.get("district") or a.get("city")
            if district:
                break

        new_day: Dict[str, Any] = {
            "day": day_num,
            "district": district,
            items_key: chunk,
        }

        if start_dt:
            new_day["date"] = (start_dt + timedelta(days=day_num - 1)).isoformat()

        itin_days.append(new_day)

    dest_plan["itinerary"] = itin_days
    dest_plan["days"] = target_days
    meta["days"] = target_days

    if start_dt:
        _redate_days(itin_days, start_dt)

    return itinerary


def _apply_set_start_date(itinerary: Dict[str, Any], new_start: str) -> Dict[str, Any]:
    try:
        start_dt = datetime.strptime(new_start, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid start_date format: {new_start!r}  (expected YYYY-MM-DD)")

    meta = itinerary.get("meta", {})
    days = meta.get("days", 1)

    meta["start_date"] = start_dt.isoformat()
    end_dt = start_dt + timedelta(days=max(days, 1) - 1)
    meta["end_date"] = end_dt.isoformat()

    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    if dest_plan and isinstance(dest_plan, dict):
        dest_plan["start_date"] = start_dt.isoformat()
        itin_days = dest_plan.get("itinerary", [])
        if isinstance(itin_days, list):
            _redate_days(itin_days, start_dt)

    return itinerary


def _apply_remove_items_by_text(
    itinerary: Dict[str, Any], query: str
) -> Dict[str, Any]:
    if not query:
        return itinerary
    q = query.strip().lower()
    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    if not dest_plan or not isinstance(dest_plan, dict):
        return itinerary
    itin_days = dest_plan.get("itinerary", [])
    items_key = "attractions"
    for day in itin_days:
        if "items" in day:
            items_key = "items"
            break
    for day in itin_days:
        original = day.get(items_key, []) or []
        day[items_key] = [
            a for a in original
            if q not in (a.get("title") or a.get("name") or "").lower()
        ]
    logger.info(f"remove_items_by_text: query='{query}'")
    return itinerary


def _apply_prefer_tags(
    itinerary: Dict[str, Any], tags: List[str]
) -> Dict[str, Any]:
    if not tags:
        return itinerary
    tag_set = {t.strip().lower() for t in tags}
    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    if not dest_plan or not isinstance(dest_plan, dict):
        return itinerary
    itin_days = dest_plan.get("itinerary", [])
    items_key = "attractions"
    for day in itin_days:
        if "items" in day:
            items_key = "items"
            break
    for day in itin_days:
        items = day.get(items_key, []) or []

        def _score(a):
            category = (a.get("category") or a.get("type") or "").lower()
            tags_field = [t.lower() for t in (a.get("tags") or [])]
            if category in tag_set:
                return 0
            if any(t in tag_set for t in tags_field):
                return 1
            return 2

        day[items_key] = sorted(items, key=_score)
    logger.info(f"prefer_tags: tags={tags}")
    return itinerary
def _apply_add_category_places(
    itinerary: Dict[str, Any],
    tags: List[str],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not tags:
        return itinerary

    plans = itinerary.get("plans", {})
    meta = itinerary.get("meta", {})
    dest_plan = plans.get("destination_plan")
    if not dest_plan or not isinstance(dest_plan, dict):
        return itinerary

    itin_days = dest_plan.get("itinerary", [])
    if not itin_days:
        return itinerary

    items_key = "attractions"
    for day in itin_days:
        if "items" in day:
            items_key = "items"
            break

    city = (
        meta.get("destination")
        or (context or {}).get("city")
        or (context or {}).get("destination")
        or ""
    )
    country = (context or {}).get("country") or "Sri Lanka"

    if not city:
        logger.warning("[add_category_places] city not found")
        return itinerary

    used_ids = _get_used_attraction_ids(dest_plan)

    payload = dict(context or {})
    payload.setdefault("city", city)
    payload.setdefault("destination", city)
    payload.setdefault("country", country)
    payload.setdefault("tags", tags)
    payload.setdefault("raw_text", f"{', '.join(tags)} attractions in {city}")

    try:
        from services.recommender_service.src.itinerary.planner.itinerary_planner import (
            fetch_attractions_by_preferences_vector,
        )

        candidates, dbg = fetch_attractions_by_preferences_vector(
            payload=payload,
            country=country,
            limit=20,
            similarity_threshold=0.5,
            timeout=90.0,
        )

        city_l = city.strip().lower()
        fresh = []
        for c in candidates:
            aid = c.get("attraction_id")
            cand_city = str(c.get("city") or "").strip().lower()
            cand_dist = str(c.get("district") or "").strip().lower()

            if aid and aid in used_ids:
                continue

            if city_l and not (cand_city == city_l or cand_dist == city_l):
                continue

            fresh.append(c)

        if not fresh:
            logger.info(f"[add_category_places] no new places found for city={city}, tags={tags}")
            return itinerary

        # add to least-filled days
        itin_days_sorted = sorted(itin_days, key=lambda d: len(d.get(items_key) or []))

        add_count = min(4, len(fresh))
        for i in range(add_count):
            target_day = itin_days_sorted[i % len(itin_days_sorted)]
            target_day.setdefault(items_key, []).append(fresh[i])

        logger.info(
            f"[add_category_places] added {add_count} places for city={city}, tags={tags}"
        )
        return itinerary

    except Exception as e:
        logger.warning(f"[add_category_places] failed: {e}")
        return itinerary

def _apply_swap_days(
    itinerary: Dict[str, Any], day_a: int, day_b: int
) -> Dict[str, Any]:
    plans = itinerary.get("plans", {})
    dest_plan = plans.get("destination_plan")
    if not dest_plan or not isinstance(dest_plan, dict):
        return itinerary
    itin_days = dest_plan.get("itinerary", [])

    # ✅ Fix null day numbers first
    for i, day in enumerate(itin_days):
        if day.get("day") is None:
            day["day"] = i + 1

    items_key = "attractions"
    for day in itin_days:
        if "items" in day:
            items_key = "items"
            break

    day_a_obj = next((d for d in itin_days if d.get("day") == day_a), None)
    day_b_obj = next((d for d in itin_days if d.get("day") == day_b), None)
    if not day_a_obj or not day_b_obj:
        logger.warning(f"swap_days: day {day_a} or {day_b} not found")
        return itinerary
    items_a = deepcopy(day_a_obj.get(items_key, []))
    items_b = deepcopy(day_b_obj.get(items_key, []))
    day_a_obj[items_key] = items_b
    day_b_obj[items_key] = items_a
    logger.info(f"swap_days: swapped day {day_a} <-> day {day_b}")
    return itinerary


def _redate_days(
    day_list: List[Dict[str, Any]], start_dt: date
) -> None:
    for i, day_dict in enumerate(day_list):
        day_num = day_dict.get("day") or (i + 1)
        day_date = start_dt + timedelta(days=day_num - 1)
        day_dict["date"] = day_date.isoformat()