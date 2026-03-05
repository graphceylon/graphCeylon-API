from __future__ import annotations
import os
import time
import httpx
from typing import Any, Dict, List, Optional

from ..runtime.tools.models import ToolCall

HOTEL_EXTERNAL_BASE_URL = (os.getenv("HOTEL_EXTERNAL_BASE_URL") or "http://190.92.219.12:8087").rstrip("/")
HOTEL_EXTERNAL_TOKEN = (os.getenv("HOTEL_EXTERNAL_TOKEN") or "").strip()

HOTEL_OAUTH_TOKEN_URL = (os.getenv("HOTEL_OAUTH_TOKEN_URL") or f"{HOTEL_EXTERNAL_BASE_URL}/token").strip()
HOTEL_OAUTH_USERNAME = (os.getenv("HOTEL_OAUTH_USERNAME") or "externalAPI").strip()
HOTEL_OAUTH_PASSWORD = (os.getenv("HOTEL_OAUTH_PASSWORD") or "e@x$&n!l&12E").strip()
HOTEL_OAUTH_GRANT_TYPE = (os.getenv("HOTEL_OAUTH_GRANT_TYPE") or "password").strip()
HOTEL_OAUTH_CLIENT_ID = (os.getenv("HOTEL_OAUTH_CLIENT_ID") or "").strip()
HOTEL_OAUTH_CLIENT_SECRET = (os.getenv("HOTEL_OAUTH_CLIENT_SECRET") or "").strip()

_token_cache: Dict[str, Any] = {"token": None, "exp": 0.0}

def _get_access_token(client: httpx.Client) -> str:
    if HOTEL_EXTERNAL_TOKEN:
        return HOTEL_EXTERNAL_TOKEN

    now = time.time()
    if _token_cache["token"] and now < _token_cache["exp"]:
        return _token_cache["token"]

    if not HOTEL_OAUTH_PASSWORD:
        raise RuntimeError("HOTEL_OAUTH_PASSWORD not set (and no HOTEL_EXTERNAL_TOKEN provided).")

    data = {
        "grant_type": HOTEL_OAUTH_GRANT_TYPE,
        "username": HOTEL_OAUTH_USERNAME,
        "password": HOTEL_OAUTH_PASSWORD,
    }
    if HOTEL_OAUTH_CLIENT_ID:
        data["client_id"] = HOTEL_OAUTH_CLIENT_ID
    if HOTEL_OAUTH_CLIENT_SECRET:
        data["client_secret"] = HOTEL_OAUTH_CLIENT_SECRET

    r = client.post(
        HOTEL_OAUTH_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    j = r.json()

    token = j.get("access_token")
    if not token:
        raise RuntimeError(f"Token response missing access_token: {j}")

    expires_in = int(j.get("expires_in") or 3600)
    _token_cache["token"] = token
    _token_cache["exp"] = now + max(60, expires_in - 30)
    return token

def _auth_headers(client: httpx.Client) -> Dict[str, str]:
    token = _get_access_token(client)
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

def _unwrap_data_list(payload: Any) -> List[Dict[str, Any]]:
    # Your API: {"HttpCode":"200","Description":"Success","Data":[...]}
    if isinstance(payload, dict) and isinstance(payload.get("Data"), list):
        return payload["Data"]
    if isinstance(payload, list):
        return payload
    return []

def _safe_first(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return items[0] if items else None
def _pick_best_items(items, n=3):
    def score(x):
        return int(bool(x.get("IsApplicableForIBE"))) * 2 + int(bool(x.get("IsActive")))
    items_sorted = sorted(items, key=score, reverse=True)
    return items_sorted[:n] if items_sorted else []

def _build_combos(room_categories, room_types, meal_plans, rate_codes):
    cats = _pick_best_items(room_categories, 3)
    types = _pick_best_items(room_types, 3)
    meals = _pick_best_items(meal_plans, 3)
    rates = _pick_best_items(rate_codes, 2)

    combos = []
    for c in cats:
        for t in types:
            for m in meals:
                combos.append({
                    "RoomCategoryId": c.get("Id"),
                    "RoomTypeId": t.get("Id"),
                    "MealPlanId": m.get("Id"),
                    "RateCodeId": (rates[0].get("Id") if rates else None),
                    "meta": {"cat": c, "type": t, "meal": m, "rate": (rates[0] if rates else None)},
                })

    return combos[:12]

def _has_price_data(price_json):
    if not isinstance(price_json, dict):
        return False
    if str(price_json.get("HttpCode")) != "200":
        return False
    data = price_json.get("Data")
    return isinstance(data, list) and len(data) > 0
# =========================
# NEW: budget + roomrates picking helpers
# =========================

def _to_float(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    if isinstance(v, str):
        try:
            f = float(v)
            return f if f > 0 else None
        except Exception:
            return None
    return None

def _extract_budget_from_args(args: Dict[str, Any]) -> Optional[float]:
    """
    Priority EXACTLY:
      1) args.max_price_lkr   (query-time budget)
      2) args.budget_per_night_lkr (long-term DB preference)
      3) None -> choose cheapest
    NOTE: because ToolCall args are what you have here (not ParsedIntent),
    we read budgets from args directly.
    """
    v = _to_float(args.get("max_price_lkr"))
    if v:
        return v

    v = _to_float(args.get("budget_per_night_lkr"))
    if v:
        return v

    return None
def _budget_source_from_args(args: Dict[str, Any]) -> str:
    # max_price_lkr = query-time (user typed budget)
    if _to_float(args.get("max_price_lkr")):
        return "query"
    # budget_per_night_lkr = long-term preference (DB)
    if _to_float(args.get("budget_per_night_lkr")):
        return "db"
    return "none"


def _id_to_name(items: List[Dict[str, Any]], _id: Any) -> Optional[str]:
    try:
        target = int(_id)
    except Exception:
        return None
    for it in items or []:
        if int(it.get("Id") or -1) == target:
            return it.get("Name")
    return None


def _build_selection_reason_from_roomrates(
    *,
    picked: Dict[str, Any],
    rates: List[Dict[str, Any]],
    budget_lkr: Optional[float],
    budget_source: str,
) -> Dict[str, Any]:
    usable = [
        r for r in rates
        if isinstance(r.get("AdultRate"), (int, float)) and float(r["AdultRate"]) > 0
    ]
    cheapest_rate = min((float(r["AdultRate"]) for r in usable), default=None)

    chosen_rate = float(picked.get("_adult_rate") or picked.get("AdultRate") or 0.0)
    exceeds_budget = bool(picked.get("_exceeds_budget", False))

    bullets: List[str] = []

    if budget_lkr is None:
        reason_type = "cheapest_option"
        bullets.append("Selected the cheapest available option for your dates (no budget provided).")
        confidence = 0.95
    else:
        if exceeds_budget:
            reason_type = "cheapest_but_over_budget"
            bullets.append(f"All available options exceed your budget (LKR {int(budget_lkr):,}), so I selected the cheapest one.")
            confidence = 0.90
        else:
            reason_type = "best_within_budget"
            bullets.append(f"Fits within your budget (source: {budget_source}). I picked the best-priced option under your limit.")
            confidence = 0.90

    if cheapest_rate is not None:
        bullets.append(f"Cheapest rate: LKR {cheapest_rate:,.0f} (per adult). Selected: LKR {chosen_rate:,.0f} (per adult).")

    if budget_lkr is not None:
        diff = budget_lkr - chosen_rate
        if diff >= 0:
            bullets.append(f"Remaining vs budget: about LKR {diff:,.0f} (per adult).")
        else:
            bullets.append(f"Over budget by: about LKR {abs(diff):,.0f} (per adult).")

    return {
        "type": reason_type,
        "confidence": confidence,
        "budget_source": budget_source,
        "budget_lkr": budget_lkr,
        "selected_adult_rate_lkr": chosen_rate,
        "cheapest_adult_rate_lkr": cheapest_rate,
        "exceeds_budget": exceeds_budget,
        "bullets": bullets,
        "message": bullets[0] if bullets else "Selected option.",
    }
def _pick_rate_combo_from_roomrates(rates: List[Dict[str, Any]], budget_lkr: Optional[float]) -> Dict[str, Any]:
    usable = [
        r for r in rates
        if isinstance(r.get("AdultRate"), (int, float)) and r["AdultRate"] > 0
    ]
    if not usable:
        return {}

    for r in usable:
        r["_adult_rate"] = float(r["AdultRate"])

    cheapest = min(usable, key=lambda r: (r["_adult_rate"], r.get("MealPlanId", 0), r.get("RoomTypeId", 0)))

    if budget_lkr is None:
        cheapest["_exceeds_budget"] = False
        cheapest["_budget_lkr"] = None
        return cheapest

    under = [r for r in usable if r["_adult_rate"] <= budget_lkr]
    if under:
        best = max(under, key=lambda r: r["_adult_rate"])
        best["_exceeds_budget"] = False
        best["_budget_lkr"] = budget_lkr
        return best

    # EVERYTHING exceeds budget -> choose cheapest, but flag it
    cheapest["_exceeds_budget"] = True
    cheapest["_budget_lkr"] = budget_lkr
    return cheapest

def _pick_default_rate(rate_codes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rate_codes:
        return None
    for r in rate_codes:
        if r.get("IsDefault") is True or r.get("Default") is True:
            return r
    return rate_codes[0]

def _rate_code_id_for_roomrates(default_rate: Optional[Dict[str, Any]]) -> int:
    """
    roomrates takes RateCodeId.
    Your ratecodes list here is RateCodeHeader objects (Id = header id),
    but sometimes it ALSO includes RateCodeId/CodeId. If not, fallback to 1.
    """
    if default_rate:
        for k in ("RateCodeId", "RateCodeID", "RateCode_Id", "CodeId", "CodeID"):
            v = default_rate.get(k)
            if isinstance(v, int) and v > 0:
                return v
    return 1
def _build_booking_draft_from_pick(
    args: Dict[str, Any],
    chosen_property: Dict[str, Any],
    property_prefix: str,
    arrival: str,
    departure: str,
    adults: int,
    picked: Dict[str, Any],
    rate_code_header_id: Optional[int],
    price_json: Dict[str, Any],
) -> Dict[str, Any]:
    # price_json Data: [{"RoomRateDate": "...", "RoomRate": 20050}, ...]
    breakdown = []
    total = 0.0
    for x in (price_json.get("Data") or []):
        r = _to_float(x.get("RoomRate")) or 0.0
        total += r
        breakdown.append({"date": (x.get("RoomRateDate") or "")[:10], "rate_lkr": r})

    # draft "rooms" format expected by your /confirm endpoint
    rooms = [{
        "RoomCategoryId": int(picked["RoomCategoryId"]),
        "RoomTypeId": int(picked["RoomTypeId"]),
        "MealPlanId": int(picked["MealPlanId"]),
        "RateCodeHeaderId": int(rate_code_header_id or 1),
        "Adults": adults
    }]

    return {
        "country_code": args.get("country_code") or "LKA",
        "arrival": arrival,
        "departure": departure,
        "property_id": int(chosen_property.get("Id")),
        "property_code": property_prefix,
        "property_name": chosen_property.get("Name"),
        "rooms": rooms,
        "pricing": {
            "currency": "LKR",
            "total_lkr": total,
            "breakdown": breakdown
        },
        "editable_fields": ["arrival", "departure", "rooms", "remarks"],
        "remarks": "Reservation created by Graph Ceylon (pending HITL approval)"
    }
def book_hotel_flow(call: ToolCall) -> Dict[str, Any]:
    args = call.args or {}
    trace = args.get("trace") or {}
    if isinstance(trace, dict) and args.get("max_price_lkr") is None:
        args["max_price_lkr"] = trace.get("max_price_lkr")
    warning: Optional[str] = None 

    arrival = args.get("arrival") or args.get("check_in") or args.get("start_date")
    departure = args.get("departure") or args.get("check_out") or args.get("end_date")
    adults = int(args.get("adults") or args.get("guests") or 2)

    # optional user picks
    selected_room_category_id = args.get("room_category_id")
    selected_room_type_id = args.get("room_type_id")
    selected_meal_plan_id = args.get("meal_plan_id")
    selected_rate_code_id = args.get("rate_code_id")  # optional, but useful
    currency_id = args.get("currency_id")             # optional future use

    # if not arrival or not departure:
    #     return {
    #         "ok": False,
    #         "status": "missing_fields",
    #         "missing_fields": ["arrival", "departure"],
    #         "message": "Missing arrival/departure dates for pricing.",
    #     }

    if not arrival or not departure:
        # keep whatever we already know so the next user message can fill only dates
        partial = {
            "city": args.get("city"),
            "property_id": args.get("property_id"),
            "property_code": args.get("property_code") or args.get("property_prefix"),
            "adults": adults,
            "max_price_lkr": args.get("max_price_lkr"),
            "budget_per_night_lkr": args.get("budget_per_night_lkr"),
        }

        return {
            "ok": False,
            "status": "needs_clarification",
            "missing_fields": ["arrival", "departure"],
            "message": "What are your check-in and check-out dates? (e.g., 2026-06-04 to 2026-06-06)",
            "followups": [
                "Please provide check-in and check-out dates (YYYY-MM-DD). Example: 2026-06-04 to 2026-06-06"
            ],
            "draft": {
                "arrival": arrival,
                "departure": departure,
                "adults": adults,
                "known": partial,
            },
            # IMPORTANT: gives orchestrator something to store for the next turn
            "session_state_patch": {
                "pending_tool": "book_hotel",
                "pending_args": partial,
                "pending_missing_fields": ["arrival", "departure"],
            },
        }

    base = HOTEL_EXTERNAL_BASE_URL

    def post_json(client: httpx.Client, headers: Dict[str, str], path: str, payload: Dict[str, Any]) -> Any:
        url = f"{base}{path}"
        print("[hotel-api] POST", url, "payload=", payload)
        resp = client.post(url, headers=headers, json=payload)
        print("[hotel-api] ->", resp.status_code, resp.text[:250])
        resp.raise_for_status()
        return resp.json()

    # ---- Determine property ----
    # Prefer explicit property_id/prefix from args; else fallback to first from allproperties.
    property_id = args.get("property_id")
    property_prefix = args.get("property_code") or args.get("property_prefix")

    try:
        with httpx.Client(timeout=60.0) as client:
            headers = _auth_headers(client)

            # Get properties (so your demo isn't hardcoded to "ABR")
            props_raw = post_json(client, headers, "/api/external/allproperties", {})
            properties = _unwrap_data_list(props_raw)

            chosen_property = None
            if property_id is not None:
                pid = int(property_id)
                chosen_property = next((p for p in properties if p.get("Id") == pid), None)

            if not chosen_property and property_prefix:
                chosen_property = next((p for p in properties if (p.get("Prefix") or "").strip() == property_prefix), None)

            chosen_property = chosen_property or _safe_first(properties)

            if not chosen_property:
                return {"ok": False, "status": "no_properties", "message": "No properties returned by external API."}

            property_id = int(chosen_property["Id"])
            property_prefix = (chosen_property.get("Prefix") or "").strip()
            property_name = chosen_property.get("Name") or "Hotel"

            # 1) room categories
            rc_raw = post_json(client, headers, "/api/external/roomcategories", {"PropertyId": property_id})
            room_categories = _unwrap_data_list(rc_raw)

            # 2) room types
            rt_raw = post_json(client, headers, "/api/external/roomtypes", {"PropertyId": property_id})
            room_types = _unwrap_data_list(rt_raw)

            # 3) meal plans
            mp_raw = post_json(client, headers, "/api/external/mealplans", {"PropertyId": property_id})
            meal_plans = _unwrap_data_list(mp_raw)

            # 4) rate codes  ✅ POST (your API)
            rcodes_raw = post_json(client, headers, "/api/external/ratecodes", {"PropertyId": property_id})
            rate_codes = _unwrap_data_list(rcodes_raw)

            # Defaults (IDs are "Id")
            default_cat = next((x for x in room_categories if x.get("Id") == selected_room_category_id), None) if selected_room_category_id else None
            default_cat = default_cat or _safe_first(room_categories)

            default_type = next((x for x in room_types if x.get("Id") == selected_room_type_id), None) if selected_room_type_id else None
            default_type = default_type or _safe_first(room_types)

            default_meal = next((x for x in meal_plans if x.get("Id") == selected_meal_plan_id), None) if selected_meal_plan_id else None
            default_meal = default_meal or _safe_first(meal_plans)

            default_rate = next((x for x in rate_codes if x.get("Id") == selected_rate_code_id), None) if selected_rate_code_id else None
            default_rate = default_rate or _safe_first(rate_codes)

            if not default_cat or not default_type or not default_meal:
                return {
                    "ok": False,
                    "status": "no_options",
                    "message": "Could not fetch room options (categories/types/meal plans).",
                    "debug": {
                        "room_categories_count": len(room_categories),
                        "room_types_count": len(room_types),
                        "meal_plans_count": len(meal_plans),
                        "rate_codes_count": len(rate_codes),
                    },
                }

            # 5) pricing call
            # Your API expects these names based on earlier usage.
            # (RateCodeId isn't shown in your pricing endpoint, so only include if your endpoint supports it.)
            country_code = args.get("country_code") or "LKA"

            # ----------------------------
            # NEW FLOW: roomrates -> pick -> ONE calc call
            # ----------------------------

            # pick rate header id (needed later for reservation)
            default_rate = next((x for x in rate_codes if x.get("Id") == selected_rate_code_id), None) if selected_rate_code_id else None
            default_rate = default_rate or _pick_default_rate(rate_codes)

            rate_code_header_id = default_rate.get("Id") if default_rate else None  # for createReservationForAI later
            rate_code_id_for_roomrates = _rate_code_id_for_roomrates(default_rate)  # for /roomrates

            # budget priority: max_price_lkr > budget_per_night_lkr > None
            budget_lkr = _extract_budget_from_args(args)
            budget_source = _budget_source_from_args(args)

            # 1) call roomrates FIRST
            rates_raw = post_json(
                client,
                headers,
                "/api/external/roomrates",
                {
                    "PropertyId": property_id,
                    "RateCodeId": rate_code_id_for_roomrates,
                    "PackageId": 1,
                    "From": arrival,
                    "To": departure,
                },
            )
            rates = _unwrap_data_list(rates_raw)

            if not rates:
                return {
                    "ok": False,
                    "status": "no_rates",
                    "message": f"{property_name} has no rates for these dates.",
                }

            # 2) pick best combo (or cheapest and flag if exceeds budget)
            picked = _pick_rate_combo_from_roomrates(rates, budget_lkr=budget_lkr)
            if not picked:
                return {
                    "ok": False,
                    "status": "no_rates",
                    "message": f"{property_name} returned rates but none usable.",
                }

            exceeds_budget = bool(picked.get("_exceeds_budget", False))
            used_budget = picked.get("_budget_lkr", budget_lkr)
            selection_reason = _build_selection_reason_from_roomrates(
                picked=picked,
                rates=rates,
                budget_lkr=used_budget,
                budget_source=budget_source,
            )

            # 3) ONE pricing call using picked combo
            price_payload = {
                "CountryCode": country_code,
                "Arrival": arrival,
                "Departure": departure,
                "RoomCategoryId": picked["RoomCategoryId"],
                "RoomTypeId": picked["RoomTypeId"],
                "MealPlanId": picked["MealPlanId"],
                "PropertyCode": property_prefix,
                "Uuid": "external",
            }
            best_price = post_json(client, headers, "/api/external/roomratecalculationforai", price_payload)

            if not _has_price_data(best_price):
                return {
                    "ok": False,
                    "status": "no_availability",
                    "message": f"{property_name} has no available rates for these dates.",
                }

            # set selected to match your existing response structure
            default_cat = {"Id": picked["RoomCategoryId"]}
            default_type = {"Id": picked["RoomTypeId"]}
            default_meal = {"Id": picked["MealPlanId"]}

            price = best_price

            draft = _build_booking_draft_from_pick(
                args=args,
                chosen_property=chosen_property,
                property_prefix=property_prefix,
                arrival=arrival,
                departure=departure,
                adults=adults,
                picked=picked,
                rate_code_header_id=rate_code_header_id,
                price_json=best_price,
                
            )
            draft["display"] = {
                "room_category": _id_to_name(room_categories, picked["RoomCategoryId"]),
                "room_type": _id_to_name(room_types, picked["RoomTypeId"]),
                "meal_plan": _id_to_name(meal_plans, picked["MealPlanId"]),
                "rate_code": _id_to_name(rate_codes, rate_code_header_id),
            }

            draft["selection_reason"] = selection_reason

            # message when everything exceeds budget (your exact requirement)
            warning: Optional[str] = None
            if used_budget and exceeds_budget:
                warning = f"This is the only option I have, but it exceeds your budget of LKR {int(used_budget):,}."


            # picked came from /roomrates and contains the IDs we need
            default_cat = {"Id": picked["RoomCategoryId"]}
            default_type = {"Id": picked["RoomTypeId"]}
            default_meal = {"Id": picked["MealPlanId"]}

            price = best_price

    except httpx.HTTPStatusError as e:
        return {
            "ok": False,
            "status": "tool_error",
            "message": f"Hotel API returned HTTP {e.response.status_code}.",
            "warning": warning,
            "exceeds_budget": bool(warning),
            "debug": {"body": e.response.text[:800]},
        }
    except Exception as e:
        return {"ok": False, "status": "tool_error", "message": f"{type(e).__name__}: {e}"}

    return {
        "ok": True,
        "status": "pricing_ready",
        "draft": draft,
        "hotel": {
            "property_id": property_id,
            "property_code": property_prefix,
            "name": property_name,
            "address": chosen_property.get("Address"),
            "image": chosen_property.get("Image"),
            "phone": chosen_property.get("ContactNos"),
            "website": chosen_property.get("WebsiteURL"),
        },
        "search": {"arrival": arrival, "departure": departure, "adults": adults},
        "selectors": {
            "properties": properties,
            "room_categories": room_categories,
            "room_types": room_types,
            "meal_plans": meal_plans,
            "rate_codes": rate_codes,
        },
        "selected": {
            "property_id": property_id,
            "property_code": property_prefix,
            "room_category_id": default_cat.get("Id"),
            "room_type_id": default_type.get("Id"),
            "meal_plan_id": default_meal.get("Id"),
            "rate_code_id": rate_code_header_id,
        },
        "price": price,
        "next_actions": [
            {
                "type": "proceed_to_booking",
                "label": "Proceed to booking",
                "payload": {
                    "property_id": property_id,
                    "property_code": property_prefix,
                    "arrival": arrival,
                    "departure": departure,
                    "adults": adults,
                    "room_category_id": default_cat.get("Id"),
                    "room_type_id": default_type.get("Id"),
                    "meal_plan_id": default_meal.get("Id"),
                    "rate_code_id": rate_code_header_id,
                },
            }
        ],
        "message": draft.get("selection_reason", {}).get("message") or "Select options and proceed to booking.",
        "warning": warning,
        "exceeds_budget": bool(warning),
    }
