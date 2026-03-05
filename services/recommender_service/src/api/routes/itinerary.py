from datetime import date, timedelta
from typing import Any, Dict, Optional, List, Union
from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator
from pprint import pprint

from services.recommender_service.src.itinerary.planner.itinerary_planner import (
    build_itinerary_from_payload,
    PlannerConfig,
)
from services.recommender_service.src.itinerary.planner.itinerary_modifier import (
    modify_itinerary,
)
from fastapi.encoders import jsonable_encoder
import json

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


class ItineraryPlanRequest(BaseModel):
    intent: str = Field(default="plan_itinerary")
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: Optional[str] = None

    city: Optional[str] = None
    destination: Optional[str] = None
    country: str = "Sri Lanka"
    origin_city: Optional[str] = None


    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None
    days: int = 3

    eco_preference: float = 0.5
    travel_style: Optional[List[str]] = None
    food_preferences: Optional[List[str]] = None

    max_trip_budget_lkr: Optional[int] = None
    currency: str = "LKR"


class C3RequestEnvelope(BaseModel):
    intent: str = Field(default="plan_itinerary")
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    query: Dict[str, Any] = Field(default_factory=dict)
    prefs: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    trace: Dict[str, Any] = Field(default_factory=dict)


class ItineraryModifyRequest(BaseModel):
    """Request body for POST /itinerary/modify

    Accepts both the recommender-native shape:
        { ops, existing_itinerary, context, notes }
    and the orchestrator shape:
        { existing_plan, change_request: {ops, notes, strict}, context, ... }
    A model_validator normalises the latter into the former.
    """
    # ── canonical fields ──
    ops: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of modification operations, e.g. [{'op': 'set_days', 'days': 2}]",
    )
    existing_itinerary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The full itinerary dict to modify (as returned by /itinerary/plan)",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional user context, prefs, session info"
    )
    notes: Optional[str] = Field(
        default=None, description="Human-readable note from orchestrator"
    )

    # ── orchestrator-compat fields ──
    existing_plan: Optional[Dict[str, Any]] = Field(default=None, exclude=True)
    change_request: Optional[Dict[str, Any]] = Field(default=None, exclude=True)
    trip_id: Optional[str] = Field(default=None)
    preference_sources: Optional[Dict[str, Any]] = Field(default=None, exclude=True)
    semantic_context: Optional[Dict[str, Any]] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _normalise_orchestrator_shape(self):
        # existing_plan -> existing_itinerary
        if not self.existing_itinerary and self.existing_plan:
            self.existing_itinerary = self.existing_plan
        # change_request.ops -> ops
        if self.change_request and isinstance(self.change_request, dict):
            if not self.ops:
                self.ops = self.change_request.get("ops", [])
            if not self.notes:
                self.notes = self.change_request.get("notes")
        # final guard
        if not self.ops:
            self.ops = []
        if not self.existing_itinerary:
            self.existing_itinerary = {}
        return self


def normalize_payload(req: Union[ItineraryPlanRequest, C3RequestEnvelope]) -> Dict[str, Any]:
    # If envelope: merge query+prefs+constraints into a single dict your planner expects
    if isinstance(req, C3RequestEnvelope):
        payload = {}
        payload.update(req.query or {})
        payload.update(req.prefs or {})
        payload.update(req.constraints or {})

        # carry identity + intent
        payload["intent"] = req.intent
        payload["user_id"] = req.user_id
        payload["session_id"] = req.session_id

        # optional: keep trace for debug (won't hurt)
        payload["trace"] = req.trace or {}
        return payload

    # Else: flat request
    return req.model_dump()

def _print_compact_plan(plan: Dict[str, Any], label: str) -> None:
    if not plan:
        print(f"\n[{label}] <empty>")
        return

    dbg = plan.get("debug", {}) or {}
    print(f"\n========== {label} (COMPACT) ==========")
    print(f"[debug] kg_mode={dbg.get('kg_mode')} anchor={dbg.get('route_anchor_coords')}")

    print("date       | city   | district | slot      | attraction_id | title")
    print("-" * 90)

    for day in plan.get("itinerary", []) or []:
        day_date = day.get("date", "")
        city = day.get("city", "")
        district = day.get("district", "")

        for item in day.get("items", []) or []:
            print(
                f"{day_date} | {str(city):<6} | {str(district):<8} | "
                f"{str(item.get('slot','')):<9} | {str(item.get('attraction_id') or item.get('poi_id') or '')} | "
                f"{str(item.get('title',''))}"
            )
    print("=" * 90)

def _print_waypoint_plans(waypoint_plans: List[Dict[str, Any]]) -> None:
    print("\n========== WAYPOINT_PLANS ==========")
    if not waypoint_plans:
        print("<none>")
        print("=" * 40)
        return

    for i, wp in enumerate(waypoint_plans, start=1):
        wp_city = wp.get("waypoint_city") or f"wp_{i}"
        _print_compact_plan(wp, f"WAYPOINT_{i}: {wp_city}")
    print("=" * 40)

def _print_shop_dine(plan: Dict[str, Any], label: str = "SHOP & DINE ON ROUTE") -> None:
    sd = (plan.get("shopping_dining_on_route") or {})
    items = sd.get("items") or []
    dbg = sd.get("debug") or {}

    print(f"\n========== {label} ==========")
    print(f"[debug] count={len(items)} kg_url={dbg.get('kg_url')}")
    print("route_idx | cat        | rating |District | city | poi_id        | title")
    print("-" * 90)

    for p in items[:40]:  # show first 40
        print(
            f"{str(p.get('_nearest_point_index', p.get('_route_point_index', ''))):<8} | "
            f"{str(p.get('category','')):<10} | "
            f"{str(p.get('rating','')):<6} | "
            f"{str(p.get('district','')):<8} | "
            f"{str(p.get('city','')):<4} | "
            f"{str(p.get('poi_id','')):<12} | "
            f"{str(p.get('title',''))}"
        )
    print("=" * 90)


def _print_hotels(plan: Dict[str, Any], label: str = "HOTELS") -> None:
    hotels = plan.get("hotels") or {}
    items = hotels.get("items") or []
    dbg = hotels.get("debug") or {}

    print(f"\n========== {label} ==========")
    print(f"[debug] count={len(items)} url={dbg.get('hotel_search_url')} ok={dbg.get('ok')} err={dbg.get('error')}")

    if not items:
        print("<no hotels>")
        print("=" * 90)
        return

    print(f"{'name':<30} | {'city':<10} | {'stars':<5} | {'price_range':<20} | {'amenities':<30} | kg_id")
    print("-" * 130)

    for h in items[:20]:
        price = h.get("price_range_lkr") or {}
        price_str = f"{price.get('min', '?')}-{price.get('max', '?')}" if price else "N/A"
        amenities = ", ".join((h.get("amenities") or [])[:4])
        print(
            f"{str(h.get('name','')):<30} | "
            f"{str(h.get('city','')):<10} | "
            f"{str(h.get('star_rating','')):<5} | "
            f"{price_str:<20} | "
            f"{amenities:<30} | "
            f"{str(h.get('kg_id',''))}"
        )
    print("=" * 130)


def _print_modify_summary(original: Dict[str, Any], modified: Dict[str, Any], ops: List[Dict[str, Any]]) -> None:
    """Print a compact summary of what the modify endpoint changed."""
    print("\n========== ITINERARY MODIFY SUMMARY ==========")
    print(f"[ops] {ops}")

    orig_meta = original.get("meta", {})
    mod_meta = modified.get("meta", {})
    print(f"[days] {orig_meta.get('days', '?')} -> {mod_meta.get('days', '?')}")

    orig_dest = (original.get("plans", {}) or {}).get("destination_plan", {}) or {}
    mod_dest = (modified.get("plans", {}) or {}).get("destination_plan", {}) or {}

    orig_itin = orig_dest.get("itinerary", []) or []
    mod_itin = mod_dest.get("itinerary", []) or []

    orig_attraction_count = sum(len(d.get("attractions", []) or d.get("items", [])) for d in orig_itin)
    mod_attraction_count = sum(len(d.get("attractions", []) or d.get("items", [])) for d in mod_itin)

    print(f"[destination_plan days] {len(orig_itin)} -> {len(mod_itin)}")
    print(f"[total attractions]    {orig_attraction_count} -> {mod_attraction_count}")

    for day in mod_itin:
        day_num = day.get("day", "?")
        district = day.get("district", "")
        attractions = day.get("attractions", []) or day.get("items", [])
        names = [a.get("name") or a.get("title", "?") for a in attractions]
        print(f"  Day {day_num} ({district}): {names}")

    print("=" * 50)


@router.post("/plan")
def itinerary_plan(req: Union[ItineraryPlanRequest, C3RequestEnvelope]) -> Dict[str, Any]:
    try:
        payload = normalize_payload(req)

        print("\n================ C3 /itinerary/plan RECEIVED PAYLOAD ================")
        pprint(payload)
        print("====================================================================\n")

        # ✅ days: always read from payload (not hardcoded)
        days = int(payload.get("days") or 3)
        if days <= 0:
            days = 1
        payload["days"] = days

        # ✅ default start_date
        if not payload.get("start_date"):
            payload["start_date"] = date.today().isoformat()

        # ✅ default end_date (computed using days)
        if not payload.get("end_date"):
            d0 = date.fromisoformat(payload["start_date"])
            payload["end_date"] = (d0 + timedelta(days=days - 1)).isoformat()

        cfg = PlannerConfig(
            per_day_attractions=int(payload.get("per_day_attractions") or 2),
            meals_per_day=int(payload.get("meals_per_day") or 1),
            max_candidates=int(payload.get("max_candidates") or 80),
        )

        # ✅ build itinerary
        from services.recommender_service.src.itinerary.planner.itinerary_planner import (
            build_two_plans_from_payload
        )

        result = build_two_plans_from_payload(payload, cfg=cfg)
        safe = jsonable_encoder(result)
        plans = safe.get("plans", {}) or {}
        dest_plan = plans.get("destination_plan", {}) or {}

        _print_compact_plan(plans.get("destination_plan", {}), "DESTINATION_PLAN")
        _print_waypoint_plans(dest_plan.get("waypoint_plans") or [])
        _print_compact_plan(plans.get("route_plan", {}), "Outbound Plan ")
        _print_compact_plan(plans.get("route_return_plan", {}), "Return Plan")
        _print_shop_dine(plans.get("route_return_plan", {}), "Return SHOP & DINE")
        _print_hotels(dest_plan, "DESTINATION HOTELS")
        
        print(f"[REQ] city={payload.get('city')} origin={payload.get('origin_city')} days={payload.get('days')} start={payload.get('start_date')}")


        return result

    except Exception as e:
        print("\n🔥 C3 ITINERARY ERROR 🔥")
        print(type(e).__name__, str(e))
        raise


@router.post("/modify")
def itinerary_modify(req: ItineraryModifyRequest) -> Dict[str, Any]:
    """
    Modify an existing itinerary based on orchestrator operations.

    Currently supported ops:
      - {"op": "set_days", "days": <int>}  — redistribute attractions across N days

    Future ops (not yet implemented):
      - {"op": "prefer_tags", "tags": [...]}
      - {"op": "swap_attraction", ...}
    """
    try:
        print("\n================ C3 /itinerary/modify RECEIVED ================")
        print(f"[ops]   {req.ops}")
        print(f"[notes] {req.notes}")
        print(f"[context user_id] {(req.context or {}).get('user_id')}")

        existing_meta = (req.existing_itinerary.get("meta") or {})
        print(f"[existing] days={existing_meta.get('days')} destination={existing_meta.get('destination')}")
        print("================================================================\n")

        modified = modify_itinerary(
            existing_itinerary=req.existing_itinerary,
            ops=req.ops,
            context=req.context,
        )

        safe = jsonable_encoder(modified)

        _print_modify_summary(req.existing_itinerary, safe, req.ops)

        # --- Build diff summary ---
        orig_meta = req.existing_itinerary.get("meta", {}) or {}
        mod_meta = safe.get("meta", {}) or {}
        orig_dest = (req.existing_itinerary.get("plans", {}) or {}).get("destination_plan", {}) or {}
        mod_dest = (safe.get("plans", {}) or {}).get("destination_plan", {}) or {}
        orig_itin = orig_dest.get("itinerary", []) or []
        mod_itin = mod_dest.get("itinerary", []) or []

        # --- Helper to extract compact day summaries ---
        def _day_summaries(itin_days):
            summaries = []
            for day in itin_days:
                items = day.get("items", []) or day.get("attractions", [])
                summaries.append({
                    "day": day.get("day"),
                    "date": day.get("date"),
                    "city": day.get("city"),
                    "district": day.get("district"),
                    "attractions": [
                        {
                            "title": a.get("title") or a.get("name"),
                            "attraction_id": a.get("attraction_id"),
                            "slot": a.get("slot"),
                            "category": (a.get("raw") or {}).get("category") if isinstance(a.get("raw"), dict) else a.get("category"),
                        }
                        for a in items
                    ],
                })
            return summaries

        diff = {
            "days": {"before": orig_meta.get("days"), "after": mod_meta.get("days")},
            "start_date": {"before": orig_meta.get("start_date"), "after": mod_meta.get("start_date")},
            "destination_plan_days": {"before": len(orig_itin), "after": len(mod_itin)},
            "total_attractions": {
                "before": sum(len(d.get("items", []) or d.get("attractions", [])) for d in orig_itin),
                "after": sum(len(d.get("items", []) or d.get("attractions", [])) for d in mod_itin),
            },
            "ops_applied": req.ops,
            "before_itinerary": _day_summaries(orig_itin),
            "after_itinerary": _day_summaries(mod_itin),
        }

        response = {
            "status": "ok",
            "trip_id": getattr(req, "trip_id", None),
            "meta": mod_meta,
            "plan": safe,
            "diff": diff,
        }

        print("\n========== MODIFY RESPONSE TO ORCHESTRATOR ==========")
        print(f"  status  : {response['status']}")
        print(f"  trip_id : {response['trip_id']}")
        print(f"  meta    : {json.dumps(response['meta'], default=str)[:200]}")
        print(f"  plan    : <{len(json.dumps(response['plan'], default=str))} chars>")
        print(f"  diff    : {json.dumps(response['diff'], default=str)}")
        print("=====================================================\n")

        return response

    except ValueError as e:
        print(f"\n⚠️ MODIFY VALIDATION ERROR: {e}")
        return {"status": "error", "trip_id": getattr(req, "trip_id", None), "meta": None, "plan": None, "diff": None, "message": str(e)}
    except Exception as e:
        print(f"\n🔥 C3 ITINERARY MODIFY ERROR 🔥")
        print(type(e).__name__, str(e))
        raise