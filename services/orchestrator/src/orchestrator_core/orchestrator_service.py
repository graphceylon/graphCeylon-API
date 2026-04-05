# /Users/dev/Desktop/graphCeylon-API/services/orchestrator/src/orchestrator_core/orchestrator_service.py

from __future__ import annotations
import json
from pathlib import Path
import os

import psycopg
from .context_resolver import resolve_context
from ..api.schemas import Entities 
from .runtime.blackboard import Blackboard
from .mappers.restaurant_mapper import map_restaurant_request
from .mappers.book_hotel_mapper import map_book_hotel_request
from .clients.booking_client import save_booking_draft
from .contracts.book_hotel import BookHotelResponse
from .runtime.tools.providers.mcp_provider import MCPToolProvider
import hashlib
import json
import traceback
from typing import Awaitable
from uuid import uuid4
from .agentic.loop import AgenticLoop
from .verifier.verifier_agent import VerifierAgent
from .agentic.nli_wrapper import DebertaNLIWrapper as NLIWrapper
from .tools.hotel_booking_tool import book_hotel_flow
from .explainability import ExplainPacket
from .explainability import merge_explain

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type
from uuid import uuid4
from .followup_resolver import resolve_followup
import os
import re
from .runtime.trace_pg import PostgresTraceStore
from pydantic import BaseModel
from .runtime.tools.models import ToolCall
from .runtime.tools.router import ToolRouter
from .runtime.tools.providers.a2a_provider import A2AToolProvider
from .runtime.tools.providers.local_provider import LocalToolProvider
from .core_contract import AgentResult, EvidenceItem, EvidenceSource, SafetyFlag, SafetySeverity
# MCP optional
# from .runtime.tools.providers.mcp_provider import MCPToolProvider


from ..api.schemas import (
    OrchestrateRequest,
    OrchestrateResponse,
    ParsedIntent,
    TaskSummary,
)

from .intent_parser.agent import IntentParserAgent


# ---- mappers + contracts ----
from .mappers.weather_mapper import map_weather_request
from .contracts.weather import WeatherForecastResponse
from .memory.session_store import SessionStore
from .memory.session_state import SessionState
from .mappers.crowd_mapper import map_crowd_request
from .contracts.crowd import CrowdForecastResponse
from ..api.schemas import AgentCallError
from .clients.recommender_client import RecommenderClient
from .contracts.itinerary_modify import ItineraryModifyResponse

from .contracts.recommend_pois import RecommendPOIsResponse

# Phase 3 semantic recall (local module)
from ..profile_semantic.embedder import embed_texts, vector_literal
from ..profile_semantic.db import db_conn
from .response_formatter import ResponseFormatter
from .trips.trip_repo import TripRepo


from .mappers.price_mapper import map_price_request
from .contracts.price import PriceForecastResponse

from .mappers.itinerary_mapper import map_itinerary_request
from .contracts.itinerary import ItineraryPlanResponse

from .mappers.transport_mapper import map_transport_request
from .contracts.transport import TransportInfoResponse  # optional
from .mappers.attraction_mapper import map_attraction_request
from .contracts.attraction import AttractionInfoResponse  # optional

from .mappers.itinerary_modify_mapper import map_itinerary_modify_request
from .contracts.itinerary_modify import ItineraryModifyResponse

from .mappers.sustainability_mapper import map_sustainability_request
from .mappers.recommend_pois_mapper import map_recommend_pois_request

from .mappers.accommodation_mapper import map_accommodation_request
from .contracts.accommodation import AccommodationSearchRequest, AccommodationSearchResponse



from .agent_mappers.visa_policy_mapper import map_visa_policy_request
from .agent_contracts.visa_policy import VisaPolicyResponse  # optional (enable later)

# ✅ registry + adapter + tracing (use RELATIVE imports)
from .runtime.registry.registry import AgentRegistry
from .runtime.registry.models import AgentSpec, SLA
from .runtime.adapters.a2a import A2AHttpAdapter
from .runtime.trace import InMemoryTraceStore, TraceEvent

from ..profile.profile_client import ProfileClient


from .memory.preference_merge import merge_preferences
from .memory.profile_event_store import ProfileEventStore, ProfileEvent
from ..profile_agent_phase2.compute import maybe_auto_compute
from typing import Any, Dict, List, Tuple, Callable, Awaitable

import anyio

from .task_executor import TaskExecutor, ExecTask
from .task_graph_builder import TaskGraphBuilder

import re

HandlerFn = Callable[[Any, Any, Dict[str, Any]], Awaitable[AgentResult]]

EDIT_VERBS = [
    "make it", "extend", "shorten", "change", "shift", "move", "swap",
    "redo", "regenerate", "replan", "remove", "delete", "drop", "exclude",
    "modify", "update", "edit"
]

EXPLICIT_HOTEL = ["book hotel", "hotel booking", "reserve hotel", "find hotels", "rooms", "check-in", "check out"]
EXPLICIT_VISA  = ["visa", "eta", "entry requirements"]
EXPLICIT_WEATHER = ["weather", "rain", "temperature", "forecast"]
EXPLICIT_TRANSPORT = ["how to go", "bus", "train", "taxi", "transport", "route"]
_SCHEDULE_DATE = os.getenv("RAILWAY_SCHEDULE_DATE", "2026-01-09")

WRITE_INTENTS = {"booking_create", "booking_confirm", "cancel_booking", "modify_booking"}

ALLOWED_AMENITIES = {"wifi", "ac", "pool", "breakfast", "parking", "gym", "spa", "family_rooms"}

_AMENITY_MAP = {
    "wi-fi": "wifi",
    "wi fi": "wifi",
    "wifi": "wifi",
    "wireless": "wifi",
    "wireless internet": "wifi",
    "ac": "ac",
    "a/c": "ac",
    "air conditioning": "ac",
    "family rooms": "family_rooms",
    "family room": "family_rooms",
}

MULTI_INTENT_ALLOW = {
    "forecast_weather": {"info_attraction", "recommend_pois", "recommend_restaurants"},
    "info_attraction": {"forecast_weather", "recommend_pois"},
    "recommend_pois": {"forecast_weather", "info_attraction"},
}

DISALLOW_SECONDARY = {"plan_itinerary", "modify_itinerary"} | WRITE_INTENTS
import re

PLAN_PHRASES = [
    "plan a trip", "plan trip", "plan an itinerary", "plan itinerary",
    "create a trip", "create an itinerary", "make an itinerary",
    "build an itinerary", "generate an itinerary",
]

# Fuzzy match for common itinerary misspellings
_ITINERARY_PATTERN = re.compile(
    r"\bitin[e]?r+[ae]+r[ay]+\b",  # matches: itinerary, itinereray, itinrerary, etc.
    re.IGNORECASE
)

def has_plan_signal(text: str) -> bool:
    t = norm(text)
    has_itinerary = bool(_ITINERARY_PATTERN.search(t)) or "itinerary" in t
    has_trip = "trip" in t
    return (
        ("plan" in t and (has_itinerary or has_trip))
        or any(p in t for p in PLAN_PHRASES)
    )

def pick_secondary_intents(parsed_intent, handlers: set[str], max_n: int = 2, min_score: float = 0.80) -> list[str]:
    primary = (parsed_intent.intent or "").strip()
    allowed = MULTI_INTENT_ALLOW.get(primary, set())

    scores = parsed_intent.scores or {}
    secs = parsed_intent.secondary_intents or []

    candidates = []
    for s in secs:
        s = (s or "").strip()
        if not s or s == primary:
            continue
        if s in DISALLOW_SECONDARY:
            continue
        if s not in handlers:
            continue
        if allowed and s not in allowed:
            continue

        if float(scores.get(s, 0.0)) >= min_score:
            candidates.append(s)

    candidates.sort(key=lambda x: float(scores.get(x, 0.0)), reverse=True)
    return candidates[:max_n]

def normalize_amenities_with_unknown(items):
    """
    Returns:
      normalized: list[str]  (only allowed amenities)
      unknown:    list[str]  (things user asked that we don't support)
    """
    if not items:
        return [], []

    normalized = []
    unknown = []

    for x in items:
        if not isinstance(x, str):
            continue

        raw = x.strip()
        s = raw.lower().strip()
        s = s.replace("_", " ")
        s = re.sub(r"\s+", " ", s)

        s = _AMENITY_MAP.get(s, s)
        s = re.sub(r"[^a-z0-9_ ]+", "", s).strip()
        s = _AMENITY_MAP.get(s, s)

        if s in ALLOWED_AMENITIES:
            if s not in normalized:
                normalized.append(s)
        else:
            # keep original wording for user clarity
            if raw and raw not in unknown:
                unknown.append(raw)

    return normalized, unknown

def wrap_task(fn, task_type: str, task_id: str):
    async def _wrapped(task, ctx, results):
        try:
            out = await fn(task, ctx, results)

            # ✅ hard-enforce contract even on success path
            if isinstance(out, AgentResult):
                return out

            # If something returns raw dict/string/etc -> convert to AgentResult failure
            return AgentResult(
                ok=False,
                answer="",
                data=None,
                evidence=[],
                missing_fields=[],
                next_actions=[],
                confidence=0.0,
                safety_flags=[
                    SafetyFlag(
                        code="CONTRACT_BREACH",
                        severity=SafetySeverity.medium,
                        message=f"Task '{task_type}' returned {type(out)} instead of AgentResult",
                        meta={
                            "task_type": task_type,
                            "task_id": task_id,
                            "got_type": str(type(out)),
                            "value_preview": str(out)[:500],
                        },
                    )
                ],
                meta={"task_type": task_type, "task_id": task_id},
            )

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[DAG] TASK FAILED type={task_type} id={task_id} err={e}\n{tb}")

            # ✅ Always return AgentResult (never dict)
            return AgentResult(
                ok=False,
                answer="",
                data=None,
                evidence=[],
                missing_fields=[],
                next_actions=[],
                confidence=0.0,
                safety_flags=[
                    SafetyFlag(
                        code="TASK_EXCEPTION",
                        severity=SafetySeverity.high,
                        message=str(e),
                        meta={
                            "task_type": task_type,
                            "task_id": task_id,
                            "traceback": tb,
                        },
                    )
                ],
                meta={"task_type": task_type, "task_id": task_id},
            )

    return _wrapped
def stable_idempotency_key(*, user_id: str | None, session_id: str, intent: str, args: dict) -> str:
    # remove volatile fields that would change between retries
    args_clean = dict(args or {})
    if "trace" in args_clean and isinstance(args_clean["trace"], dict):
        args_clean["trace"] = {k: v for k, v in args_clean["trace"].items() if k not in {"timestamp", "ts"}}

    canonical = {
        "user_id": user_id or "",
        "session_id": session_id,
        "intent": intent,
        "args": args_clean,
    }
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())

def booking_stub(call):  # call: ToolCall
    return {
        "ok": True,
        "status": "verified",
        "booking_id": f"BK-{call.trace_id[:8]}",
        "message": "Booking request sent for human verification. Confirmed.",
    }
def book_hotel_flow_stub(call: ToolCall):
    """
    Demo hotel booking flow stub.
    Simulates the multi-step booking API pipeline.
    """

    args = call.args or {}

    city = args.get("city")
    check_in = args.get("check_in")
    check_out = args.get("check_out")
    guests = args.get("guests", 2)

    # simulate response structure your UI can render
    return {
        "ok": True,
        "status": "booking_options_ready",
        "city": city,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "available_hotels": [
            {
                "hotel_id": "HTL001",
                "name": "Sigiriya Eco Resort",
                "room_type": "Deluxe Room",
                "price_lkr": 22000,
                "meal_plan": "Breakfast Included",
            },
            {
                "hotel_id": "HTL002",
                "name": "Kandy Lake View Hotel",
                "room_type": "Superior Room",
                "price_lkr": 18000,
                "meal_plan": "Half Board",
            },
        ],
        "message": "Select a hotel to proceed with booking.",
    }
def has_explicit_other_intent(text: str) -> bool:
    t = norm(text)
    # if any explicit other-intent phrases exist, don't override
    if any(k in t for k in EXPLICIT_HOTEL): return True
    if any(k in t for k in EXPLICIT_VISA): return True
    if any(k in t for k in EXPLICIT_WEATHER): return True
    if any(k in t for k in EXPLICIT_TRANSPORT): return True
    return False

def apply_intent_policy(parsed_intent: ParsedIntent, req_text: str, session_state: Optional[SessionState]) -> ParsedIntent:
    raw = norm(req_text)
    ents = parsed_intent.entities

    active_trip_id = None
    if session_state:
        active_trip_id = session_state.slots.get("active_trip_id")
    active_trip = bool(active_trip_id)

    # --- signals ---
    plan_like = has_plan_signal(raw)
    edit_like = has_edit_signal(raw, ents)
    print(f"[policy] raw='{raw}' plan={plan_like} edit={edit_like} active_trip={bool(session_state and session_state.slots.get('active_trip_id'))}")

    hotel_like = bool(re.search(r"\b(hotel|book|booking|reserve|reservation|check[-\s]?in|check[-\s]?out)\b", raw))
    weather_like = bool(re.search(r"\b(weather|forecast|rain|temperature|climate)\b", raw))
    visa_like = bool(re.search(r"\b(visa|eta|entry)\b", raw))
    transport_like = bool(re.search(r"\b(bus|train|taxi|transport|route|how to go)\b", raw))

    # --- RULE 0: if user is explicitly asking hotel/weather/visa/transport, never override to itinerary ---
    if hotel_like or weather_like or visa_like or transport_like:
        return parsed_intent

    # --- RULE 1: planning beats modify (even if active trip exists) ---
    if plan_like:
        scores = dict(parsed_intent.scores or {})
        scores["plan_itinerary"] = max(scores.get("plan_itinerary", 0.0), 0.95)

        ents_dict = ents.model_dump(exclude_none=False) if hasattr(ents, "model_dump") else dict(ents or {})
        # do not carry active itinerary into a new plan
        ents_dict.pop("itinerary_id", None)
        ents_dict.pop("current_itinerary", None)
        # ✅ Clear stale session state for fresh plan
        if session_state:
            for key in ("active_trip_id", "city", "active_place", "start_date", "end_date",
                        "pending_fields", "pending_intent", "pending_domain", "pending_clarification"):
                session_state.slots.pop(key, None)

        return parsed_intent.model_copy(update={
            "intent": "plan_itinerary",
            "domain_category": "itinerary",
            "confidence": float(scores.get("plan_itinerary", 0.95)),
            "secondary_intents": [],
            "scores": scores,
            "entities": Entities(**ents_dict),
        })

    # --- RULE 2: modify only when active trip exists + edit signal ---
    if active_trip and edit_like:
        scores = dict(parsed_intent.scores or {})
        scores["modify_itinerary"] = max(scores.get("modify_itinerary", 0.0), 0.95)

        # suppress booking-like secondaries if they exist
        for k in ["book_hotel", "cancel_booking", "modify_booking", "check_availability"]:
            if k in scores:
                scores[k] = min(scores[k], 0.01)

        ents_dict = ents.model_dump(exclude_none=True) if hasattr(ents, "model_dump") else dict(ents or {})
        ents_dict["itinerary_id"] = active_trip_id

        return parsed_intent.model_copy(update={
            "intent": "modify_itinerary",
            "domain_category": "itinerary",
            "confidence": 0.95,
            "secondary_intents": [],
            "scores": scores,
            "entities": Entities(**ents_dict),
        })

    return parsed_intent
def has_edit_signal(text: str, entities) -> bool:
    t = norm(text)

    # explicit edit verbs
    if any(v in t for v in EDIT_VERBS):
        return True

    # explicit day swap like "day 2" / "swap day 1 and day 3"
    if re.search(r"\bday\s*\d+\b", t):
        return True

    # explicit date edit like "start on 2026-03-01"
    # if getattr(entities, "start_date", None):
    #     return True
    # if re.search(r"\b(?:start|begin)\b.*\b\d{4}-\d{2}-\d{2}\b", t):
    #     return True

    # days only counts as edit if accompanied by edit verb ("make it 2 days")
    if getattr(entities, "days", None):
        if re.search(r"\b(make it|change it|set|extend|shorten|reduce|increase)\b", t):
            return True

    return False
PLAN_PHRASES = [
    "plan a trip", "plan trip", "plan an itinerary", "plan itinerary",
    "create a trip", "create an itinerary", "make an itinerary",
    "build an itinerary", "generate an itinerary",
]

def has_plan_signal(text: str) -> bool:
    t = norm(text)
    return ("plan" in t and ("trip" in t or "itinerary" in t)) or any(p in t for p in PLAN_PHRASES)
def apply_domain_overrides(parsed_intent: ParsedIntent) -> ParsedIntent:
    """
    If classifier returns generic_fact_query but we already know the domain,
    map it to a real executable intent that exists in self.handlers.
    """
    dc = (parsed_intent.domain_category or "").strip().lower()
    intent = (parsed_intent.intent or "").strip().lower()

    if intent == "generic_fact_query":
        # ✅ restaurants
        if dc in {"restaurant", "restaurants", "food", "dining"}:
            scores = dict(parsed_intent.scores or {})
            # push a stable score so confidence isn't ~0
            scores["recommend_restaurants"] = max(scores.get("recommend_restaurants", 0.0), 0.95)

            return parsed_intent.model_copy(update={
                "intent": "recommend_restaurants",
                "domain_category": "restaurant",
                "confidence": float(scores["recommend_restaurants"]),
                "scores": scores,
                "secondary_intents": [],
            })

    return parsed_intent
def resolve_intent(parsed_intent, req_text: str, active_trip: bool):
    t = req_text or ""
    entities = parsed_intent.entities

    if not active_trip:
        return parsed_intent

    # 1) If user is clearly planning, DO NOT force modify
    if has_plan_signal(t) and not has_explicit_other_intent(t):
        parsed_intent.intent = "plan_itinerary"
        parsed_intent.domain_category = "itinerary"
        return parsed_intent

    # 2) Otherwise, if edit signals appear, force modify
    if has_edit_signal(t, entities) and not has_explicit_other_intent(t):
        parsed_intent.intent = "modify_itinerary"
        parsed_intent.domain_category = "itinerary"
        return parsed_intent

    return parsed_intent


def normalize_executor_output(out: Any) -> Tuple[Dict[str, Any], List[Any], Any]:
    """
    Normalize TaskExecutor.run() output into:
      (dag_results_dict, exec_results_list, ctx)
    Supports:
      - dict
      - (dict, list)
      - (dict, list, ctx)
      - ((dict, list), ctx)
      - (ctx, (dict, list)) etc.
    """
    # Already dict
    if isinstance(out, dict):
        return out, [], {}

    # Tuple forms
    if isinstance(out, tuple):
        # (dict, list, ctx)
        if len(out) == 3 and isinstance(out[0], dict):
            dag = out[0]
            execs = out[1] if isinstance(out[1], list) else []
            ctx = out[2]
            return dag, execs, ctx

        # (dict, list)
        if len(out) == 2 and isinstance(out[0], dict):
            dag = out[0]
            execs = out[1] if isinstance(out[1], list) else []
            return dag, execs, {}

        # ((dict, list), ctx)
        if len(out) == 2 and isinstance(out[0], tuple) and len(out[0]) == 2 and isinstance(out[0][0], dict):
            dag, execs = out[0]
            execs = execs if isinstance(execs, list) else []
            return dag, execs, out[1]

        # (ctx, (dict, list))
        if len(out) == 2 and isinstance(out[1], tuple) and len(out[1]) == 2 and isinstance(out[1][0], dict):
            dag, execs = out[1]
            execs = execs if isinstance(execs, list) else []
            return dag, execs, out[0]

    return {}, [], {}



def build_exec_tasks(builder: TaskGraphBuilder, parsed_intent) -> List[ExecTask]:
    nodes = builder.get_nodes()

    # map type -> id (parse_intent -> T1, extract_entities -> T2, etc.)
    type_to_id = {n.type: n.id for n in nodes.values()}

    tasks: List[ExecTask] = []
    for n in nodes.values():
        deps = []
        for d in (n.depends_on or []):
            # if depends_on contains types, convert them
            deps.append(type_to_id.get(d, d))

        tasks.append(
            ExecTask(
                id=n.id,
                type=n.type,
                assigned_agent=n.assigned_agent,
                depends_on=deps,
            )
        )
    return tasks



async def run_task_graph(
    *,
    exec_tasks: List[ExecTask],
    handlers: Dict[str, Callable[[], Awaitable[Any]]],
) -> Tuple[Dict[str, Any], Any]:
    """
    Execute the DAG and return:
      - results: Dict[task_id -> handler_output]
      - task_results: List[ExecResult]
    """
    executor = TaskExecutor(handlers=handlers)
    return await executor.run(exec_tasks)


VISA_STUB_JSON = Path(__file__).resolve().parent / "visa_policy" / "visa.json"
# this points to: orchestrator_core/visa_policy/visa.json


RECOMMENDER_BASE_URL = os.getenv(
    "RECOMMENDER_SERVICE_URL",
    "http://127.0.0.1:8003",
).rstrip("/")


# ✅ NEW: Visa/KG base URL (your friend’s KG interface layer service)
VISA_KG_BASE_URL = os.getenv(
    "VISA_KG_SERVICE_URL",
    "http://kg_service:8000",
).rstrip("/")


# ✅ toggle for stub vs real visa service
USE_VISA_STUB = os.getenv("USE_VISA_STUB", "0") == "1"


@dataclass(frozen=True)
class IntentHandler:
    endpoint: str
    mapper: Callable[[ParsedIntent, OrchestrateRequest], BaseModel]
    response_model: Optional[Type[BaseModel]] = None
    timeout: int = 20
    result_field: Optional[str] = None


class OrchestratorService:
    def __init__(
        self,
        intent_parser: IntentParserAgent,
        
        task_graph_builder: TaskGraphBuilder,
        protocol_mode: str = "direct",
    ) -> None:
        self.intent_parser = intent_parser
        TRACE_DSN = os.getenv("ORCH_DB_DSN", "").strip()
        self.trace_pg = PostgresTraceStore(TRACE_DSN) if TRACE_DSN else None
        self.response_formatter = ResponseFormatter()
        self.task_graph_builder = task_graph_builder
        # self.agentic_loop = AgenticLoop()
        # self.agentic_loop.set_nli(self.nli) 
        self.protocol_mode = protocol_mode
        MODEL_DIR = (
            Path(__file__).resolve()
            .parents[4]  # adjust if needed (explained below)
            / "models" / "orchestrator" / "NLI" / "nli_deberta" / "finalrob"
        )

        self.nli = NLIWrapper(model_dir=str(MODEL_DIR))
        self.verifier = VerifierAgent(nli=self.nli)
        self.agentic_loop = AgenticLoop()
        self.agentic_loop.set_nli(self.nli)
        # self.trace_store = InMemoryTraceStore(max_per_session=500)
        self.profile_event_store = ProfileEventStore()
        self.trip_repo = TripRepo()
        self.session_store = SessionStore(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            prefix=os.getenv("SESSION_PREFIX", "gc:sess:"),
            ttl_sec=int(os.getenv("SESSION_TTL_SEC", str(60*60*6))),
        )

        # ✅ Profile client (User Service)
        self.profile_client = ProfileClient()

        # ✅ trace store
        # self.trace_store = InMemoryTraceStore(max_per_session=500)


        # ✅ 1) capability handlers
        self.handlers: Dict[str, IntentHandler] = {
           "info_transport": IntentHandler(
                endpoint="/railway/schedules/orchestrator/call/transport",
                mapper=map_transport_request,
                response_model=None,
                timeout=60,
                result_field="transport_result",
            ),
            "info_transport_bus": IntentHandler(
                endpoint="/bus/schedules/orchestrator/call/bus-schedules",
                mapper=map_transport_request,
                response_model=None,
                timeout=60,
                result_field="transport_result",
            ),
            "info_transport_train": IntentHandler(
                endpoint="/railway/schedules/orchestrator/call/transport",
                mapper=map_transport_request,
                response_model=None,
                timeout=60,
                result_field="transport_result",
            ),
            "recommend_restaurants": IntentHandler(
                endpoint="/restaurants/orchestrator/call/restaurants",  # ✅ your KG endpoint
                mapper=map_restaurant_request,                                 # ✅ you will create this mapper
                response_model=None,                                           # keep None until you define a contract
                timeout=20,
                result_field="restaurant_result",                              # ✅ you’ll also add this to results dict
            ),
            "info_attraction": IntentHandler(
                endpoint="/sub-attractions/orchestrator/call/sub-attractions",
                mapper=map_attraction_request,
                response_model=None,
                timeout=20,
                result_field="attraction_result",
            ),
            "book_hotel": IntentHandler(
                endpoint="/hotel/booking/flow",   # placeholder if you route to a service OR keep local for now
                mapper=map_book_hotel_request,    # you will create this
                response_model=None,              # keep None for now
                timeout=30,
                result_field="booking_result",
            ),
                        "info_accommodation": IntentHandler(
                endpoint="/hotels/orchestrator/call/hotels/search",
                mapper=map_accommodation_request,
                response_model= AccommodationSearchResponse,
                timeout=20,
                result_field="accommodation_result",
            ),

            "forecast_weather": IntentHandler(
                endpoint="/forecast/weather",
                mapper=map_weather_request,
                response_model=WeatherForecastResponse,
                timeout=20,
                result_field="weather_result",
            ),
            "crowd_forecast": IntentHandler(
                endpoint="/forecast/crowd",
                mapper=map_crowd_request,
                response_model=CrowdForecastResponse,
                timeout=20,
                result_field="crowd_result",
            ),
            "forecast_price": IntentHandler(
                endpoint="/forecast/price",
                mapper=map_price_request,
                response_model=PriceForecastResponse,
                timeout=20,
                result_field="price_result",
            ),
            "plan_itinerary": IntentHandler(
                endpoint="/itinerary/plan",
                mapper=map_itinerary_request,
                response_model=ItineraryPlanResponse,
                timeout=60,
                result_field="itinerary_result",
            ),
            "modify_itinerary": IntentHandler(
                endpoint="/itinerary/modify",
                mapper=map_itinerary_modify_request,
                response_model=ItineraryModifyResponse,
                timeout=30,
                result_field="modify_result",
            ),
            # You can keep these without response models for now.
            "forecast_sustainability": IntentHandler(
                endpoint="/forecast/sustainability",
                mapper=map_sustainability_request,
                response_model=None,
                timeout=20,
                result_field=None,
            ),
            "recommend_pois": IntentHandler(
                endpoint="/recommend/pois",
                mapper=map_recommend_pois_request,
                response_model=RecommendPOIsResponse,
                timeout=20,
                result_field="pois_result",
            ),
            # ✅ VisaPolicy handler (calls KG interface layer)
            "info_visa_policy": IntentHandler(
                endpoint="/graphrag/visa-policy",
                mapper=map_visa_policy_request,
                response_model=VisaPolicyResponse,
                timeout=20,
                result_field="visa_result",
            ),
        }

        # ✅ 2) registry
        self.registry = AgentRegistry(
            agents=[
                AgentSpec(
                    agent_id="recommender",
                    base_url=RECOMMENDER_BASE_URL,
                    protocols=["a2a"],  # later: ["a2a", "mcp", "blackboard"]
                     capabilities=[
                        "forecast_weather",
                        "crowd_forecast",
                        "forecast_price",
                        "plan_itinerary",
                        "modify_itinerary",
                        "forecast_sustainability",
                        "recommend_pois",
                    ],
                    sla=SLA(p95_ms=1200, success_rate=0.98),
                    cost_weight=1.0,
                ),
                # ✅ visa KG agent service
                AgentSpec(
                    agent_id="visa_kg",
                    base_url=VISA_KG_BASE_URL,
                    protocols=["a2a"],
                    capabilities=["info_visa_policy", "info_accommodation", "info_attraction","recommend_restaurants" "info_transport", "info_transport_bus", "info_transport_train",],


                    sla=SLA(p95_ms=1500, success_rate=0.98),
                    cost_weight=1.0,
                ),
            ]
        )

        # ✅ 3) A2A adapter
        self.a2a = A2AHttpAdapter()
        tool_endpoints = {k: v.endpoint for k, v in self.handlers.items()}

        a2a_provider = A2AToolProvider(
            registry=self.registry,
            adapter=self.a2a,
            tool_endpoints=tool_endpoints,
        )

        local_provider = LocalToolProvider(
            handlers={
                "booking_stub": booking_stub,
                "book_hotel": book_hotel_flow,
            }
        )

        # ✅ MCP stdio (local tools over subprocess)
        _MCP_SERVER_LOCAL = str(
            Path(__file__).resolve().parent / "servers" / "mcp_server_local.py"
        )
        mcp_stdio_provider = MCPToolProvider(
            transport="stdio",
            server_script=_MCP_SERVER_LOCAL,
            timeout_sec=30.0,
        )

        # ✅ MCP Streamable HTTP (remote agents over MCP protocol)
        # _MCP_SERVER_URL = os.getenv("MCP_SERVER_HTTP_URL", "http://localhost:9101/mcp/")
        # mcp_http_provider = MCPToolProvider(
        #     transport="streamable_http",
        #     server_url=_MCP_SERVER_URL,
        #     timeout_sec=30.0,
        # )
        # ✅ MCP Streamable HTTP — using direct /tool endpoint (bypasses async MCP protocol)
        _MCP_DIRECT_BASE = "http://localhost:9101"

        _mcp_direct_registry = AgentRegistry(
            agents=[
                AgentSpec(
                    agent_id="mcp_http_direct",
                    base_url=_MCP_DIRECT_BASE,
                    protocols=["a2a"],
                    capabilities=[
                        "plan_itinerary_mcp",
                        "forecast_weather_mcp",
                        "recommend_pois_mcp",
                        "info_visa_policy_mcp",
                        "info_accommodation_mcp",
                    ],
                    sla=SLA(p95_ms=60000, success_rate=0.95),
                    cost_weight=1.0,
                )
            ]
        )

        mcp_http_provider = A2AToolProvider(
            registry=_mcp_direct_registry,
            adapter=self.a2a,
            tool_endpoints={
                "plan_itinerary_mcp":     "/tool",
                "forecast_weather_mcp":   "/tool",
                "recommend_pois_mcp":     "/tool",
                "info_visa_policy_mcp":   "/tool",
                "info_accommodation_mcp": "/tool",
            },
        )

        self.tool_router = ToolRouter(
            providers={
                "a2a":       a2a_provider,
                "local":     local_provider,
                "mcp_stdio": mcp_stdio_provider,
                "mcp_http":  mcp_http_provider,
            },
            tool_to_provider={
                # existing A2A routes — unchanged
                "forecast_weather":        "a2a",
                "info_attraction":         "a2a",
                "info_accommodation":      "a2a",
                "info_transport":          "a2a",
                "info_transport_bus": "a2a",
                "info_transport_train": "a2a",
                "plan_itinerary":          "a2a",
                "modify_itinerary":        "a2a",
                "info_visa_policy":        "a2a",
                "crowd_forecast":          "a2a",
                "forecast_price":          "a2a",
                "forecast_sustainability": "a2a",
                "recommend_pois":          "a2a",
                "recommend_restaurants":   "a2a",
                # existing local routes — unchanged
                "booking_stub":            "local",
                "book_hotel":              "local",
                # MCP stdio benchmark variants
                "booking_stub_stdio":      "mcp_stdio",
                "book_hotel_stdio":        "mcp_stdio",
                "plan_itinerary_stdio":    "mcp_stdio",
                # MCP streamable HTTP benchmark variants
                "forecast_weather_mcp":    "mcp_http",
                "recommend_pois_mcp":      "mcp_http",
                "info_visa_policy_mcp":    "mcp_http",
                "info_accommodation_mcp":  "mcp_http",
                "plan_itinerary_mcp":      "mcp_http",
            },
        )
        # ---------------------------
    # Phase 3 — Semantic Memory trigger (PGVector)
    # ---------------------------
    def _resolve_weather_city(self, entities: Dict[str, Any]) -> Optional[str]:
        city = (entities.get("city") or "").strip()
        if city:
            return city

        region = (entities.get("region") or "").strip().lower()

        REGION_DEFAULT_CITY = {
            "south": "Galle",
            "southern": "Galle",
            "hill country": "Kandy",
            "central": "Kandy",
            "east": "Trincomalee",
            "eastern": "Trincomalee",
            "north": "Jaffna",
            "northern": "Jaffna",
            "west": "Colombo",
            "western": "Colombo",
        }

        return REGION_DEFAULT_CITY.get(region)

    def _semantic_recall_for_request(
            self,
            *,
            user_id: str,
            q: str,
            k: int = 5,
            event_types: Optional[List[str]] = None,
            snippet_chars: int = 240,
        ) -> Dict[str, Any]:
            """
            Local semantic recall (no HTTP):
            - embed q
            - pgvector top-k search
            - returns lightweight payload safe to forward downstream
            """
            if not user_id or not q or len(q.strip()) < 2:
                return {"ok": True, "results": []}

            types = event_types or ["prefs_merged", "intent_parsed", "downstream_response"]

            try:
                v = embed_texts([q])[0]
                vlit = vector_literal(v)

                with db_conn() as conn:
                    rows = conn.execute(
                        """
                        SELECT event_type, created_at, doc_text, meta,
                            (embedding <=> %s::vector) AS distance
                        FROM profile_memory_embeddings
                        WHERE user_id=%s
                        AND event_type = ANY(%s)
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (vlit, user_id, types, vlit, k),
                    ).fetchall()

                results: List[Dict[str, Any]] = []
                for (etype, created_at, doc_text, meta, distance) in rows:
                    dist = float(distance)
                    similarity = 1.0 - dist

                    text = (doc_text or "").strip()
                    snippet = text[:snippet_chars] + ("…" if len(text) > snippet_chars else "")

                    meta_dict = meta if isinstance(meta, dict) else {}
                    results.append(
                        {
                            "event_type": etype,
                            "created_at": str(created_at),
                            "distance": dist,
                            "similarity": similarity,
                            "meta": meta_dict,
                            "snippet": snippet,
                        }
                    )

                return {
                    "ok": True,
                    "q": q,
                    "k": k,
                    "event_types": types,
                    "results": results,
                }

            except Exception as e:
                # do not break orchestration
                return {
                    "ok": False,
                    "error": str(e),
                    "results": [],
                }

    @staticmethod
    def _phase3_enabled() -> bool:
        return os.getenv("PHASE3_AUTO_EMBED", "0") == "1"

    @staticmethod
    def _phase3_min_events() -> int:
        try:
            return int(os.getenv("PHASE3_MIN_EVENTS", "10"))
        except Exception:
            return 10

    @staticmethod
    def _profile_events_dsn() -> str:
        return os.getenv("PROFILE_EVENTS_DB_DSN", "").strip()

    @staticmethod
    def _profile_events_schema() -> str:
        return os.getenv("PROFILE_EVENTS_SCHEMA", "public").strip()

    @staticmethod
    def _profile_events_table() -> str:
        return os.getenv("PROFILE_EVENTS_TABLE", "profile_events").strip()

    @staticmethod
    def _events_fqtn() -> str:
        return f"{OrchestratorService._profile_events_schema()}.{OrchestratorService._profile_events_table()}"

    @staticmethod
    def _cursor_table_fqtn() -> str:
        # you already created: profile_embedding_cursor
        return f"{OrchestratorService._profile_events_schema()}.profile_embedding_cursor"

    def _phase3_get_last_cursor(self, user_id: str) -> Optional[datetime]:
        dsn = self._profile_events_dsn()
        if not dsn:
            return None

        sql = f"SELECT last_embedded_at FROM {self._cursor_table_fqtn()} WHERE user_id = %s"
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                row = cur.fetchone()
                return row[0] if row else None

    def _phase3_count_new_events(self, user_id: str, since: Optional[datetime]) -> int:
        dsn = self._profile_events_dsn()
        if not dsn:
            return 0

        events_tbl = self._events_fqtn()

        if since is None:
            sql = f"SELECT COUNT(*) FROM {events_tbl} WHERE user_id = %s"
            params = (user_id,)
        else:
            sql = f"SELECT COUNT(*) FROM {events_tbl} WHERE user_id = %s AND created_at > %s"
            params = (user_id, since)

        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return int(cur.fetchone()[0])

    def _phase3_update_cursor(self, user_id: str) -> None:
        dsn = self._profile_events_dsn()
        if not dsn:
            return

        sql = f"""
        INSERT INTO {self._cursor_table_fqtn()} (user_id, last_embedded_at)
        VALUES (%s, now())
        ON CONFLICT (user_id) DO UPDATE
        SET last_embedded_at = EXCLUDED.last_embedded_at
        """
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
            conn.commit()

    def maybe_run_phase3(self, user_id: str, session_id: str) -> None:
        """
        Phase 3 trigger:
        - Runs inside /orchestrate (sync)
        - Only runs when new events since last_embedded_at >= PHASE3_MIN_EVENTS
        """
        if not user_id:
            return
        if not self._phase3_enabled():
            return

        dsn = self._profile_events_dsn()
        if not dsn:
            print("[phase3] PROFILE_EVENTS_DB_DSN not set — skipping")
            return

        min_events = self._phase3_min_events()
        last = self._phase3_get_last_cursor(user_id)
        new_events = self._phase3_count_new_events(user_id, last)

        print(f"[phase3] gate user={user_id} session={session_id} last={last} new_events={new_events} min={min_events}")

        if new_events < min_events:
            return

        # ✅ Call your semantic pipeline
        try:
            from ..profile_semantic.pipeline import run_embed_pipeline
        except Exception as e:
            print(f"[phase3] cannot import semantic pipeline: {e}")
            return

        try:
            run_embed_pipeline(user_id=user_id)
            
            print(f"[phase3] semantic embed pipeline ran OK, cursor updated user={user_id}")
        except Exception as e:
            print(f"[phase3] semantic embed pipeline FAILED: {e}")


    # ---------------------------
    # helpers
    # ---------------------------
    @staticmethod
    def _clean_session_id(req: OrchestrateRequest) -> str:
        return (req.session_id or "no_session").strip()

    @staticmethod
    def _clean_user_id(req: OrchestrateRequest) -> Optional[str]:
        return req.user_id.strip() if req.user_id else None
    @staticmethod
    def _extract_db_preferences(profile_json: Dict[str, Any] | None) -> Dict[str, Any]:
        if not profile_json:
            return {}

        db_prefs: Dict[str, Any] = {}

        # ✅ top-level (camelCase from user_service response)
        for k_src, k_dst in [
            ("budgetLevel", "budget_level"),
            ("homeCity", "home_city"),
            ("defaultParty", "default_party"),
        ]:
            v = profile_json.get(k_src)
            if v not in [None, "", "unknown"]:
                db_prefs[k_dst] = v

        # ✅ preferenceOverrides (camelCase)
        po = profile_json.get("preferenceOverrides") or {}
        if isinstance(po, dict):
            # convert keys to snake_case if your orchestrator expects that
            key_map = {
                "travelStyle": "travel_style",
                "ecoPreference": "eco_preference",
                "avoidCrowds": "avoid_crowds",
                "activityPreference": "activity_preference",
                "pacePreference": "pace_preference",
                "adventureLevel": "adventure_level",
                "budgetLevel": "budget_level",
                "budgetPerNightLkr": "budget_per_night_lkr",
                "budgetFlexibility": "budget_flexibility",
                "preferredTransport": "preferred_transport",
                "foodPreferences": "food_preferences",
                "accessibilityNeeds": "accessibility_needs",
                "walkingToleranceMinutes": "walking_tolerance_minutes",
                "accommodationType": "accommodation_type",
                "starPreference": "star_preference",
                "mustHaveAmenities": "must_have_amenities",
                "cancellationPreference": "cancellation_preference",
                "sunSensitivity": "sun_sensitivity",
                "rainPreference": "rain_preference",
                "temperaturePreference": "temperature_preference",
                "motionSickness": "motion_sickness",
            }

            for k, v in po.items():
                if v in [None, "", [], {}, "unknown"]:
                    continue
                db_prefs[key_map.get(k, k)] = v

        # ✅ OPTIONAL: also pull useful prefs from onboarding.answers
        onboarding = profile_json.get("onboarding") or {}
        answers = onboarding.get("answers") if isinstance(onboarding, dict) else None
        if isinstance(answers, dict):
            onboarding_map = {
                "avoidCrowds": "avoid_crowds",
                "rainPreference": "rain_preference",
                "tempPreference": "temperature_preference",
                "foodPreferences": "food_preferences",
                "travelInterests": "travel_style",          # up to you: map interests → travel_style
                "budgetPerNightLkr": "budget_per_night_lkr",
                "preferredTransport": "preferred_transport",
            }
            for k, v in answers.items():
                if v in [None, "", [], {}, "unknown"]:
                    continue
                mapped = onboarding_map.get(k)
                if mapped and mapped not in db_prefs:
                    db_prefs[mapped] = v

        return db_prefs

    @staticmethod
    def _sanitize_query_overrides(q: Dict[str, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {}
        for k, v in (q or {}).items():
            if v is None:
                continue
            if isinstance(v, str) and v.strip().lower() in {"unknown", "any", ""}:
                continue
            if isinstance(v, (list, dict)) and len(v) == 0:
                continue
            cleaned[k] = v
        return cleaned




    # ---------------------------
    # registry + A2A invoke + trace
    # ---------------------------
    def _invoke_capability_a2a(
        self,
        *,
        capability: str,
        endpoint: str,
        payload: dict,
        timeout: int,
        session_id: str,
        user_id: Optional[str],
    ) -> Optional[dict]:
        trace_id = str(uuid4())
        task_id = f"T-{uuid4().hex[:8]}"
        started_at = datetime.utcnow()

        # 1) trace START
        self.trace_store.add(
            TraceEvent(
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
                task_id=task_id,
                capability=capability,
                protocol="a2a",
                agent_id=None,
                endpoint=endpoint,
                status="started",
                started_at=started_at,
                request_payload=payload,
            )
        )

        # 2) pick agent
        agent = self.registry.pick(capability=capability, protocol="a2a")
        if not agent:
            finished_at = datetime.utcnow()
            self.trace_store.update(
                session_id=session_id,
                trace_id=trace_id,
                status="error",
                finished_at=finished_at,
                latency_ms=int((finished_at - started_at).total_seconds() * 1000),
                error=f"No agent found for capability={capability} protocol=a2a",
            )
            return None

        # 3) invoke
        try:
            if capability == "info_visa_policy" and USE_VISA_STUB:
                raw = json.loads(VISA_STUB_JSON.read_text(encoding="utf-8"))
            else:
                print(f"[orchestrator] calling agent={agent.agent_id} url={agent.base_url}{endpoint}")

                raw = self.a2a.invoke(
                    base_url=agent.base_url,
                    endpoint=endpoint,
                    payload=payload,
                    timeout=timeout,
                )

            finished_at = datetime.utcnow()
            self.trace_store.update(
                session_id=session_id,
                trace_id=trace_id,
                status="ok",
                agent_id=agent.agent_id,
                finished_at=finished_at,
                latency_ms=int((finished_at - started_at).total_seconds() * 1000),
                response_payload=raw,
            )
            return raw

        except Exception as e:
            print(f"[orchestrator] ERROR calling {agent.agent_id} {agent.base_url}{endpoint}: {e}")
            finished_at = datetime.utcnow()
            self.trace_store.update(
                session_id=session_id,
                trace_id=trace_id,
                status="error",
                agent_id=agent.agent_id,
                finished_at=finished_at,
                latency_ms=int((finished_at - started_at).total_seconds() * 1000),
                error=str(e),
            )
            return None
    def _export_trace(self, session_id: str) -> Dict[str, Any]:
        try:
            if hasattr(self.trace_store, "get_session"):
                events = self.trace_store.get_session(session_id=session_id)
            elif hasattr(self.trace_store, "list"):
                events = self.trace_store.list(session_id=session_id)
            else:
                events = getattr(self.trace_store, "events_by_session", {}).get(session_id, [])
        except Exception:
            events = []

        cleaned = []
        for e in (events or []):
            if hasattr(e, "__dict__"):
                d = dict(e.__dict__)
            elif hasattr(e, "model_dump"):
                d = e.model_dump()
            else:
                d = dict(e)

            for key in ("request_payload", "response_payload"):
                if key in d:
                    val = d.get(key) or {}
                    d[key] = val if len(str(val)) < 4000 else {"_truncated": True}

            cleaned.append(d)

        return {"session_id": session_id, "events": cleaned}
    def _detect_transport_mode(self, text: str) -> str:
        t = (text or "").lower()

        has_train = any(w in t for w in ["train", "trains", "railway", "rail"])
        has_bus = any(w in t for w in ["bus", "buses", "coach"])

        if has_bus and not has_train:
            return "bus"
        if has_train and not has_bus:
            return "train"
        return "both"
    def _execute_intent(self, intent_name, parsed_intent, req, db_prefs, session_state=None, request_trace_id: str | None = None) -> Any:


        handler = self.handlers.get(intent_name)
        if not handler:
            print(f"[orchestrator] No handler registered for intent={intent_name}")
            return
        recall_ok: bool = False
        recall_snips: list[str] = []

        # 1) Patch intent + confidence so mapper sees the right intent
        patched_intent = parsed_intent.model_copy(
            update={
                "intent": intent_name,
                "confidence": float((parsed_intent.scores or {}).get(intent_name, 0.0)),
            }
        )

        # 2) Extract DB prefs safely (long-term memory)
        

        # 3) Merge prefs: query overrides > DB prefs  ✅ (use imported merge_preferences)
        # NOTE: merge_preferences is imported at top:
        # from .memory.preference_merge import merge_preferences
        q_overrides = patched_intent.preference_overrides or {}
        if hasattr(q_overrides, "model_dump"):
            q_overrides = q_overrides.model_dump(exclude_none=True)
        else:
            q_overrides = dict(q_overrides)

        q_overrides = self._sanitize_query_overrides(q_overrides)
        q_overrides = q_overrides or {}
        q_overrides.pop("_unknown_amenities", None)
        q_overrides.pop("_needs_amenity_clarification", None)

        merged_prefs, pref_source = merge_preferences(db_prefs=db_prefs, query_overrides=q_overrides)
        ALLOWED_PREF_KEYS = {
            "budget_level",
            "budget_per_night_lkr",
            "budget_flexibility",
            "travel_style",
            "eco_preference",
            "avoid_crowds",
            "activity_preference",
            "pace_preference",
            "adventure_level",
            "preferred_transport",
            "food_preferences",
            "accessibility_needs",
            "walking_tolerance_minutes",
            "accommodation_type",
            "star_preference",
            "must_have_amenities",
            "cancellation_preference",
            "sun_sensitivity",
            "rain_preference",
            "temperature_preference",
            "motion_sickness",
        }
        # right before creating ToolCall (after payload ready)

        ents_for_explain = (
            patched_intent.entities.model_dump(exclude_none=True)
            if hasattr(patched_intent.entities, "model_dump")
            else dict(patched_intent.entities or {})
        )

        # recall snippets (if attached)
        # recall_snips = []
        # recall_ok = False
        # try:
        #     sc = None
        #     if "trace" in payload and isinstance(payload["trace"], dict):
        #         sc = payload["trace"].get("semantic_context")
        #     else:
        #         sc = payload.get("semantic_context")

        #     if isinstance(sc, dict):
        #         recall_ok = bool(sc.get("recall_ok"))
        #         recall_snips = [r.get("snippet") for r in (sc.get("recall") or [])[:3] if isinstance(r, dict)]
        # except Exception:
        #     pass

        # explain = ExplainPacket(
        #     intent=intent_name,
        #     domain=str(patched_intent.domain_category or ""),
        #     entities=ents_for_explain,
        #     effective_prefs=dict(merged_prefs or {}),
        #     preference_sources=dict(pref_source or {}),
        #     recall_used=recall_ok,
        #     recall_snippets=recall_snips,
        # )
        def filter_pref_overrides(q: dict) -> dict:
            return {k: v for k, v in (q or {}).items() if k in ALLOWED_PREF_KEYS}

        q_overrides = filter_pref_overrides(q_overrides)
        if req.user_id:
            self.profile_event_store.append(
                ProfileEvent(
                    user_id=req.user_id,
                    session_id=req.session_id or "no_session",
                    event_type="prefs_merged",
                    intent=intent_name,
                    payload={
                        "db_prefs": db_prefs,
                        "query_overrides": q_overrides,
                        "merged_prefs": merged_prefs,
                        "preference_sources": pref_source,
                    },
                )
            )

            # ✅ Phase 2 auto-compute hook (runs only when threshold satisfied)
            try:
                maybe_auto_compute(req.user_id, session_id=req.session_id)

            except Exception as e:
                print(f"[phase2] auto compute failed: {e}")




        patched_intent = patched_intent.model_copy(
            update={"preference_overrides": merged_prefs}
        )
        # ✅ Attach base plan for modify so recommender can patch
        # ✅ Attach base plan for modify so recommender can patch
        if intent_name == "modify_itinerary" and session_state and req.user_id:
            active_trip_id = session_state.slots.get("active_trip_id")
            if active_trip_id:
                ents = (
                    patched_intent.entities.model_dump(exclude_none=False)
                    if hasattr(patched_intent.entities, "model_dump")
                    else dict(patched_intent.entities or {})
                )

                # ✅ ALWAYS inject trip_id — don't gate on plan_json
                ents["itinerary_id"] = active_trip_id
                print(f"[modify] injecting active_trip_id={active_trip_id} into entities")

                # ✅ Only inject current_itinerary if plan_json actually exists
                trip = self.trip_repo.get_trip(trip_id=active_trip_id, user_id=req.user_id)
                if trip:
                    if trip.plan_json:
                        ents["current_itinerary"] = trip.plan_json
                    # backfill location context regardless of plan_json
                    ents.setdefault("city", session_state.slots.get("city"))
                    ents.setdefault("country", session_state.slots.get("country"))
                    if trip.start_date:
                        ents.setdefault("start_date", trip.start_date)
                else:
                    print(f"[modify] WARNING: active_trip_id={active_trip_id} not found in trip_repo for user={req.user_id}")

                patched_intent = patched_intent.model_copy(update={"entities": Entities(**ents)})
        # 4) Build contract payload via mapper
        print("[debug] entities_type =", type(patched_intent.entities))
        contract_obj = handler.mapper(patched_intent, req)

        # 5) DEBUG prints (DB vs query vs final)
        print("\n================ USER PREF DEBUG =================")
        print(f"user_id    : {req.user_id}")
        print(f"session_id : {req.session_id}")
        print(f"intent     : {intent_name}")
        print("--------------------------------------------------")
        print("DB prefs:")
        print(db_prefs if db_prefs else "None")
        print("\nQuery overrides:")
        print(q_overrides if q_overrides else "None")
        print("\nMerged prefs (effective):")
        print(merged_prefs if merged_prefs else "None")
        print("\nPreference source map (query vs db):")
        print(pref_source if pref_source else "None")
        print("==================================================\n")

        payload = contract_obj.model_dump(mode="json", exclude_none=True)
        recall_snips = []
        recall_ok = False
        try:
            sc = None
            if "trace" in payload and isinstance(payload["trace"], dict):
                sc = payload["trace"].get("semantic_context")
            else:
                sc = payload.get("semantic_context")

            if isinstance(sc, dict):
                recall_ok = bool(sc.get("recall_ok"))
                recall_snips = [r.get("snippet") for r in (sc.get("recall") or [])[:3] if isinstance(r, dict)]
        except Exception:
            pass

        explain = ExplainPacket(
            intent=intent_name,
            domain=str(patched_intent.domain_category or ""),
            entities=ents_for_explain,
            effective_prefs=dict(merged_prefs or {}),
            preference_sources=dict(pref_source or {}),
            recall_used=recall_ok,
            recall_snippets=recall_snips,
        )
     
        if intent_name == "forecast_weather":
            # entities could be a Pydantic model or dict
            ents = (
                patched_intent.entities.model_dump(exclude_none=True)
                if hasattr(patched_intent.entities, "model_dump")
                else (patched_intent.entities or {})
            )

            resolved_city = self._resolve_weather_city(ents)

            if resolved_city:
                payload["city"] = resolved_city  # enforce a real city
            else:
                # no location → fail gracefully (don’t call downstream)
                print("[orchestrator] forecast_weather missing location (no city/region mapping)")
                return {"ok": False, "error": "Missing location for weather forecast"}


        # ✅ If using envelope, store debug/trace inside trace{}
        if "trace" in payload and isinstance(payload["trace"], dict):
            payload["trace"]["preference_sources"] = pref_source
        else:
            payload["preference_sources"] = pref_source  # fallback for old-style payloads

        # ✅ Attach semantic recall
        if req.user_id and intent_name in {"plan_itinerary", "modify_itinerary", "recommend_pois"}:
            recall = self._semantic_recall_for_request(
                user_id=req.user_id,
                q=req.input_text,
                k=int(os.getenv("PHASE3_RECALL_TOPK", "5")),
            )
            semantic_context = {
                "recall": recall.get("results", []),
                "recall_ok": bool(recall.get("ok", False)),
            }

            if "trace" in payload and isinstance(payload["trace"], dict):
                payload["trace"]["semantic_context"] = semantic_context
            else:
                payload["semantic_context"] = semantic_context

           


        print(f"=== {contract_obj.__class__.__name__} payload ({intent_name}) ===")
        print(payload)
        tool_name = intent_name

        if intent_name == "info_transport":
            mode = self._detect_transport_mode(req.input_text or "")

            payload["origin"] = payload.get("origin") or payload.get("origin_city") or ""
            payload["destination"] = payload.get("destination") or payload.get("city") or ""
            payload["user_id"] = req.user_id or ""
            payload["session_id"] = req.session_id or "no_session"
            payload["query"] = req.input_text or ""

            if mode == "bus":
                tool_name = "info_transport_bus"
                handler = self.handlers[tool_name]
                payload["schedule_date"] = payload.get("schedule_date") or payload.get("start_date")
                payload["_transport_mode"] = "bus"
                print(f"[transport] BUS only → {payload['origin']} -> {payload['destination']}")

            elif mode == "train":
                tool_name = "info_transport_train"
                handler = self.handlers[tool_name]
                payload["_transport_mode"] = "train"
                print(f"[transport] TRAIN only → {payload['origin']} -> {payload['destination']}")

            else:
                print(f"[transport] BOTH → {payload['origin']} -> {payload['destination']}")
                return self._execute_transport_both(
                    parsed_intent=parsed_intent,
                    req=req,
                    db_prefs=db_prefs,
                    session_state=session_state,
                    request_trace_id=request_trace_id,
                    payload=payload,
                )



        # 6) Invoke downstream agent/service
        is_write = intent_name in WRITE_INTENTS

        idem_key = None
        if is_write:
            idem_key = stable_idempotency_key(
                user_id=req.user_id,
                session_id=req.session_id or "no_session",
                intent=intent_name,
                args=payload,
            )

        call = ToolCall(
            name=tool_name,
            args=payload,
            timeout_ms=handler.timeout * 1000,
            retries=1 if not is_write else 0,
            trace_id=request_trace_id or str(uuid4()),
            session_id=req.session_id or "no_session",
            user_id=req.user_id,
            is_write=is_write,
            idempotency_key=idem_key,
        )
        # ✅ benchmark override — route to different transport if requested
        benchmark_transport = getattr(req, "benchmark_transport", None)
        print(f"[BENCHMARK DEBUG] benchmark_transport={benchmark_transport!r}, call.name before={intent_name!r}")
        if benchmark_transport == "mcp_streamable_http":
            call = call.model_copy(update={"name": f"{tool_name}_mcp"})
        elif benchmark_transport == "mcp_stdio":
            call = call.model_copy(update={"name": f"{tool_name}_stdio"})
        print(
            "[phase4] trace_id=", call.trace_id,
            "intent=", call.name,
            "is_write=", call.is_write,
            "idem=", call.idempotency_key
        )


        # return parsed_obj
        tool_res = self.tool_router.call(call)
        if intent_name == "info_transport":
            print("[transport][debug] endpoint =", handler.endpoint)
            print("[transport][debug] mode =", payload.get("_transport_mode"))
            print("[transport][debug] raw tool response =", tool_res.raw if hasattr(tool_res, "raw") else tool_res.data)

        # ✅ Fix transport label for MCP benchmark variants
        transport_type = tool_res.transport_type or "a2a_http"
        if call.name.endswith("_mcp"):
            transport_type = "mcp_streamable_http"
        elif call.name.endswith("_stdio"):
            transport_type = "mcp_stdio"

        if self.trace_pg:
            self.trace_pg.add_event(
                trace_id=request_trace_id or call.trace_id,
                session_id=req.session_id or "no_session",
                user_id=req.user_id,
                turn_id=req.turn_id if hasattr(req, "turn_id") else None,
                event_type="tool_end",
                status="ok" if tool_res.ok else "error",
                task_id=call.name,
                capability=call.name,
                provider=tool_res.provider,
                endpoint=handler.endpoint,
                latency_ms=tool_res.latency_ms,
                transport_type=transport_type,  # ✅ corrected label
            )
        # after tool_router.call(call)
        explain.tool = {
            "intent": call.name,
            "provider": tool_res.provider,
            "endpoint": handler.endpoint,
            "latency_ms": tool_res.latency_ms,
            "is_write": call.is_write,
        }
        # generic summary (works for all types)
        srcs = pref_source or {}
        used_db = any(v == "db" for v in srcs.values())
        used_query = any(v == "query" for v in srcs.values())

        bits = []
        if used_db and not used_query:
            bits.append("Used saved preferences from your profile.")
        elif used_query:
            bits.append("Used preferences mentioned in your message.")
        if recall_ok:
            bits.append("Used recent session memory to stay consistent with your past requests.")
        explain.summary = " ".join(bits).strip()
        tool_evidence = getattr(tool_res, "evidence", None) or []

        # --- TOOL FAILURE -> AgentResult ---
        if not tool_res.ok:
            print(f"\n[DEBUG booking_result] intent={intent_name}")
            # print(f"[DEBUG booking_result] parsed_obj type={type(parsed_obj)}")
            # print(f"[DEBUG booking_result] parsed_obj = {parsed_obj}")
            return AgentResult(
                ok=False,
                answer="",
                data=None,
                evidence=tool_evidence,
                missing_fields=[],
                next_actions=[],
                confidence=0.0,
                safety_flags=[
                    SafetyFlag(
                        code="TOOL_CALL_FAILED",
                        severity=SafetySeverity.medium,
                        message=tool_res.error or "Tool failed",
                        meta={
                            "tool": call.name,
                            "provider": tool_res.provider,
                            "endpoint": handler.endpoint,
                        },
                    )
                ],
                meta={
                    "tool_name": call.name,
                    "provider": tool_res.provider,
                    "latency_ms": tool_res.latency_ms,
                    "endpoint": handler.endpoint,
                },
            )

        raw = tool_res.data

        # --- Downstream returned None/empty -> AgentResult ---
        if raw is None:
            return AgentResult(
                ok=False,
                answer="",
                data=None,
                evidence=tool_evidence,
                missing_fields=[],
                next_actions=[],
                confidence=0.0,
                safety_flags=[
                    SafetyFlag(
                        code="DOWNSTREAM_EMPTY",
                        severity=SafetySeverity.medium,
                        message="Downstream returned empty response",
                        meta={
                            "tool": call.name,
                            "provider": tool_res.provider,
                            "endpoint": handler.endpoint,
                            "explainability": explain.__dict__,
                        },
                    )
                ],
                meta={
                    "tool_name": call.name,
                    "provider": tool_res.provider,
                    "endpoint": handler.endpoint,
                },
            )

        # --- Downstream explicitly ok:false -> AgentResult ---
        # --- Downstream explicitly ok:false -> AgentResult ---
        if isinstance(raw, dict) and raw.get("ok") is False:
            # ✅ For transport: keep data even on ok:false so formatter shows fallback
            if intent_name == "info_transport":
                return AgentResult(
                    ok=True,
                    answer="",
                    data=raw,
                    evidence=tool_evidence,
                    missing_fields=[],
                    next_actions=[],
                    confidence=0.5,
                    safety_flags=[],
                    meta={
                        "tool_name": call.name,
                        "provider": tool_res.provider,
                        "endpoint": handler.endpoint,
                    },
                )
            return AgentResult(
                ok=False,
                answer="",
                data=raw,
                evidence=tool_evidence,
                missing_fields=[],
                next_actions=[],
                confidence=0.1,
                safety_flags=[
                    SafetyFlag(
                        code="DOWNSTREAM_OK_FALSE",
                        severity=SafetySeverity.medium,
                        message=str(raw.get("error") or "Downstream returned ok:false"),
                        meta={
                            "tool": call.name,
                            "provider": tool_res.provider,
                            "endpoint": handler.endpoint,
                            "explainability": explain.__dict__,
                        },
                    )
                ],
                meta={
                    "tool_name": call.name,
                    "provider": tool_res.provider,
                    "endpoint": handler.endpoint,
                    "explainability": explain.__dict__,
                },
            )

        # --- Parse response ONCE ---
        parsed_obj: Any = None
        if handler.response_model is not None:
            try:
                parsed_obj = handler.response_model(**raw)
            except Exception as e:
                # Parsing failure should not crash orchestration
                return AgentResult(
                    ok=False,
                    answer="",
                    data=raw,
                    evidence=tool_evidence,
                    missing_fields=[],
                    next_actions=[],
                    confidence=0.2,
                    safety_flags=[
                        SafetyFlag(
                            code="RESPONSE_PARSE_FAILED",
                            severity=SafetySeverity.low,
                            message=f"Response parse failed: {e}",
                            meta={
                                "tool": call.name,
                                "provider": tool_res.provider,
                                "endpoint": handler.endpoint,
                            },
                        )
                    ],
                    meta={
                        "tool_name": call.name,
                        "provider": tool_res.provider,
                        "endpoint": handler.endpoint,
                    },
                )
        else:
            parsed_obj = raw

        # --- SUCCESS -> AgentResult ---
        return AgentResult(
            ok=True,
            answer="",  # let ResponseFormatter handle user-facing text for now
            data=parsed_obj,
            evidence=tool_res.evidence or [],
            missing_fields=[],
            next_actions=[],
            confidence=0.75,
            safety_flags=[],
            meta={
                "tool_name": call.name,
                "provider": tool_res.provider,
                "latency_ms": tool_res.latency_ms,
                "endpoint": handler.endpoint,
                "explainability": explain.__dict__,
            },
        )
    def _execute_transport_both(
        self,
        *,
        parsed_intent,
        req,
        db_prefs,
        session_state,
        request_trace_id,
        payload: dict,
    ):
        origin = payload.get("origin") or payload.get("origin_city") or ""
        destination = payload.get("destination") or payload.get("city") or ""
        country = payload.get("country") or "Sri Lanka"

        train_payload = {
            "origin": origin,
            "destination": destination,
            "city": payload.get("city"),
            "country": country,
            "time_of_day": payload.get("time_of_day"),
            "days": payload.get("days"),
            "budget_level": payload.get("budget_level"),
            "preferred_transport": payload.get("preferred_transport") or [],
            "tags": payload.get("tags") or [],
            "user_id": req.user_id or "",
            "session_id": req.session_id or "no_session",
            "query": req.input_text or "",
            "_transport_mode": "train",
        }

        bus_payload = {
            "origin": origin,
            "destination": destination,
            "city": payload.get("city"),
            "country": country,
            "schedule_date": payload.get("schedule_date") or payload.get("start_date"),
            "budget_level": payload.get("budget_level"),
            "tags": payload.get("tags") or [],
            "user_id": req.user_id or "",
            "session_id": req.session_id or "no_session",
            "query": req.input_text or "",
            "_transport_mode": "bus",
        }

        train_agent = self.registry.pick(capability="info_transport_train", protocol="a2a")
        bus_agent = self.registry.pick(capability="info_transport_bus", protocol="a2a")

        if not train_agent or not bus_agent:
            return AgentResult(
                ok=False,
                answer="",
                data=None,
                evidence=[],
                missing_fields=[],
                next_actions=[],
                confidence=0.0,
                safety_flags=[
                    SafetyFlag(
                        code="TOOL_CALL_FAILED",
                        severity=SafetySeverity.medium,
                        message="Transport agents not found for both-mode routing",
                        meta={
                            "train_found": bool(train_agent),
                            "bus_found": bool(bus_agent),
                        },
                    )
                ],
                meta={"tool_name": "info_transport_both"},
            )

        train_raw = self.a2a.invoke(
            base_url=train_agent.base_url,
            endpoint="/railway/schedules/orchestrator/call/transport",
            payload=train_payload,
            timeout=60,
        )

        bus_raw = self.a2a.invoke(
            base_url=bus_agent.base_url,
            endpoint="/bus/schedules/orchestrator/call/bus-schedules",
            payload=bus_payload,
            timeout=60,
        )

        return AgentResult(
            ok=True,
            answer="",
            data={
                "_transport_mode": "both",
                "origin": origin,
                "destination": destination,
                "country": country,
                "train": train_raw,
                "bus": bus_raw,
            },
            evidence=[],
            missing_fields=[],
            next_actions=[],
            confidence=0.9,
            safety_flags=[],
            meta={"tool_name": "info_transport_both"},
        )
    def _run_intent_parser(self, req: OrchestrateRequest) -> ParsedIntent:
        result = self.intent_parser.parse(req.input_text)

        primary = result.get("primary_intent", "generic_fact_query")
        secondary = result.get("secondary_intents", [])
        scores = result.get("scores", {})
        raw_text = result.get("raw_text", req.input_text)
        entities = result.get("entities", {})
        preference_overrides = result.get("preference_overrides", {}) or {}
        domain_category = result.get("domain_category")

        # ✅ normalize amenities safely (NO extra keys!)
        if isinstance(preference_overrides, dict):
            raw_list = preference_overrides.get("must_have_amenities") or []
            normalized, unknown = normalize_amenities_with_unknown(raw_list)
            preference_overrides["must_have_amenities"] = normalized
        else:
            unknown = []

        confidence = float(scores.get(primary, 0.0))

        parsed = ParsedIntent(
            domain_category=domain_category,
            intent=primary,
            confidence=confidence,
            secondary_intents=secondary,
            scores=scores,
            entities=entities,
            raw_text=raw_text,
            preference_overrides=preference_overrides,
        )

        # ✅ return parsed AND unknown via attribute on self (simple) OR store on req/session elsewhere
        # easiest: attach to request-scope via a private attribute
        setattr(parsed, "_unknown_amenities", unknown)

        return parsed
    def _llm_routing_fallback(self, parsed_intent: ParsedIntent, input_text: str) -> ParsedIntent:
        """
        Use Groq to fix routing when DeBERTa gets it wrong.
        Triggers when:
        - confidence < 0.85, OR
        - primary intent has no handler, OR
        - secondary intents look wrong
        """
        import httpx

        primary = parsed_intent.intent or ""
        conf = float(parsed_intent.confidence or 0.0)

        # Only trigger if conf is low OR primary has no handler
        # Also trigger if query looks multi-intent but secondaries are all non-routable
        _routable_secondaries = [
            s for s in (parsed_intent.secondary_intents or [])
            if s in self.handlers
        ]
        _has_eat_signal = any(w in input_text.lower() for w in [
            "eat", "food", "restaurant", "where to eat", "dine", "dining", "hungry"
        ])
        _has_visit_signal = any(w in input_text.lower() for w in [
            "visit", "historical", "sites", "places", "attractions", "what to do", "things to do"
        ])
        _needs_secondary_fix = (
            len(_routable_secondaries) == 0
            and (_has_eat_signal or _has_visit_signal)
            and primary in self.handlers  # primary is fine, just missing secondary
        )

        # ✅ Pre-check: vague travel intent → recommend_pois (never transport)
        _vague_travel = any(w in (input_text or "").lower() for w in [
            "i want to travel", "suggest something", "help me plan",
            "where should i go", "suggest a place", "i want to visit",
            "where to go", "what to do in sri lanka",
        ])
        if _vague_travel:
            print(f"[llm-routing] vague travel detected — routing to recommend_pois")
            ents = (
                parsed_intent.entities.model_dump(exclude_none=False)
                if hasattr(parsed_intent.entities, "model_dump")
                else dict(parsed_intent.entities or {})
            )
            if not ents.get("city"):
                ents["city"] = "Colombo"
                ents["country"] = "Sri Lanka"
            return parsed_intent.model_copy(update={
                "intent": "recommend_pois",
                "confidence": 0.85,
                "secondary_intents": [],
                "scores": {**dict(parsed_intent.scores or {}), "recommend_pois": 0.85},
                "entities": Entities(**ents),
            })
        # ✅ Never override when classifier is confident about smalltalk or out_of_scope
        _out_of_scope_score = float((parsed_intent.scores or {}).get("out_of_scope", 0.0))
        _smalltalk_score = float((parsed_intent.scores or {}).get("smalltalk", 0.0))
        if _out_of_scope_score > 0.5 or _smalltalk_score > 0.5:
            print(f"[llm-routing] smalltalk={_smalltalk_score:.2f} out_of_scope={_out_of_scope_score:.2f} — not overriding")
            return parsed_intent

        should_fallback = (conf < 0.85) or (primary not in self.handlers and primary not in {
            "parse_intent", "extract_entities", "format_response",
            "validate_required_fields", "ask_followup"
        }) or _needs_secondary_fix

        if not should_fallback:
            return parsed_intent

        GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
        if not GROQ_API_KEY:
            return parsed_intent

        VALID_INTENTS = list(self.handlers.keys())

        system_prompt = f"""You are a travel assistant intent router for Sri Lanka.
    Given a user message, return a JSON object with:
    - "intent": the single best intent from this list: {VALID_INTENTS}
    - "secondary_intents": list of up to 2 additional intents from the same list (empty list if none)
    - "city": city name mentioned or null
    - "country": country mentioned, default "Sri Lanka"

    Rules:
    - "what hotels" / "find hotels" / "hotels available" → info_accommodation
    - "weather" / "rain" / "forecast" → forecast_weather  
    - "historical sites" / "temples" / "attractions" / "places to visit" → info_attraction
    - "restaurants" / "where to eat" / "food" → recommend_restaurants
    - "plan a trip" / "itinerary" → plan_itinerary
    - "places I can visit" / "what to do" / "POIs" → recommend_pois
    - If message has TWO clear requests (weather + places), put both in intent + secondary_intents
    - ONLY return valid JSON, no explanation."""

        user_prompt = f'User message: "{input_text}"'

        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 200,
                },
                timeout=8.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()

            # Strip markdown if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            llm_out = json.loads(content)

            new_intent = (llm_out.get("intent") or "").strip()
            new_secondary = [s for s in (llm_out.get("secondary_intents") or [])
                            if s in self.handlers and s != new_intent]

            if new_intent not in self.handlers:
                print(f"[llm-routing] LLM returned unknown intent={new_intent}, keeping DeBERTa result")
                return parsed_intent

            # If out_of_scope scored high, don't override it
            _out_of_scope_score = float((parsed_intent.scores or {}).get("out_of_scope", 0.0))
            _smalltalk_score = float((parsed_intent.scores or {}).get("smalltalk", 0.0))
            if _out_of_scope_score > 0.5:
                print(f"[llm-routing] out_of_scope={_out_of_scope_score:.2f} — not overriding")
                return parsed_intent
            if _smalltalk_score > 0.5:
                print(f"[llm-routing] smalltalk={_smalltalk_score:.2f} — not overriding")
                return parsed_intent

            print(f"[llm-routing] OVERRIDE: {primary}({conf:.2f}) → {new_intent} | secondary={new_secondary}")

            # Patch entities if LLM extracted city
            ents = (
                parsed_intent.entities.model_dump(exclude_none=False)
                if hasattr(parsed_intent.entities, "model_dump")
                else dict(parsed_intent.entities or {})
            )
            if llm_out.get("city") and not ents.get("city"):
                ents["city"] = llm_out["city"]
            if llm_out.get("country") and not ents.get("country"):
                ents["country"] = llm_out["country"]

            # Build updated scores
            scores = dict(parsed_intent.scores or {})
            scores[new_intent] = max(scores.get(new_intent, 0.0), 0.90)
            for s in new_secondary:
                scores[s] = max(scores.get(s, 0.0), 0.35)

            return parsed_intent.model_copy(update={
                "intent": new_intent,
                "confidence": 0.90,
                "secondary_intents": new_secondary,
                "scores": scores,
                "entities": Entities(**ents),
            })

        except Exception as e:
            print(f"[llm-routing] fallback failed: {e} — keeping DeBERTa result")
            return parsed_intent
    def orchestrate(self, req: OrchestrateRequest) -> OrchestrateResponse:
        user_id = (req.user_id or "").strip()
        session_id = (req.session_id or "").strip() or "no_session"
        request_trace_id = (req.trace_id or "").strip() or str(uuid4())
        turn_id = (req.turn_id or "").strip() or str(uuid4()) 
        # ✅ context passed from Flutter edit flow (e.g. updated booking args)
        request_context: Dict[str, Any] = dict(req.context or {}) if hasattr(req, "context") else {}
        print(f"[DEBUG edit-flow] input_text={req.input_text!r}")
        print(f"[DEBUG edit-flow] request_context={request_context}")
        if self.trace_pg:
            self.trace_pg.start_run(
                trace_id=request_trace_id,
                user_id=user_id,
                session_id=session_id,
                turn_id=turn_id,
                request_payload=req.model_dump(mode="json") if hasattr(req, "model_dump") else dict(req),
            )
            self.trace_pg.add_event(
                trace_id=request_trace_id,
                session_id=session_id,
                user_id=user_id,
                turn_id=turn_id,
                event_type="request_received",
                status="ok",
                request_payload={"input_text": req.input_text},
            )
        

        print("[trace/service]", request_trace_id, session_id, turn_id)
        session_state: Optional[SessionState] = None
        trip_id: Optional[str] = None

        bb = Blackboard(
            user_query=req.input_text or "",
            user_id=user_id,
            session_id=session_id,
        )


         # ✅ load session (per chat window / per session_id)
        session_state = None
        if user_id and session_id != "no_session":
            raw_state = self.session_store.get(user_id=user_id, session_id=session_id)
            session_state = SessionState.from_dict(raw_state)
        if session_state:
            trip_id = session_state.slots.get("active_trip_id")
        bb.slots = dict(session_state.slots) if session_state else {}
        # ✅ EVENT 1: raw query received (store raw text)
        if user_id:
            self.profile_event_store.append(
                ProfileEvent(
                    user_id=user_id,
                    session_id=session_id,
                    event_type="query_received",
                    intent=None,
                    payload={
                        "raw_text": req.input_text,
                        "source": "orchestrator",
                    },
                )
            )

        
        # ✅ fetch profile JSON from user service (single source of truth)
        profile_json = self.profile_client.get_profile(user_id) if user_id else None

        # ✅ extract db prefs from columns + preference_overrides
        db_prefs = self._extract_db_preferences(profile_json)
        bb.preferences = dict(db_prefs or {})

        # -----------------------------
        # FOLLOWUP ANSWER CONSUMPTION (LLM slot fill)
        # -----------------------------
        pending_fields = (session_state.slots.get("pending_fields") if session_state else None)

        if session_state and pending_fields:
            # Treat this user turn as a follow-up answer (could be "Kandy", "Next week", etc.)
            filled = resolve_followup(
                user_text=req.input_text or "",
                missing_fields=list(pending_fields),
                current_entities=session_state.slots,  # use slots as current memory
                current_prefs={},  # optional: you can pass db_prefs later if you want
            )

            # Merge into session slots (only if non-empty)
            if isinstance(filled, dict):
                ents_new = filled.get("entities") or {}
                prefs_new = filled.get("preference_overrides") or {}

                any_filled = False

                for k, v in (ents_new or {}).items():
                    if v in (None, "", [], {}, "unknown"):
                        continue
                    session_state.slots[k] = v
                    any_filled = True

                # Optional: merge preference overrides too
                if prefs_new and isinstance(prefs_new, dict):
                    # store under a single slot key so it doesn't pollute entity slots
                    existing_po = session_state.slots.get("pref_overrides") or {}
                    if not isinstance(existing_po, dict):
                        existing_po = {}
                    for k, v in prefs_new.items():
                        if v in (None, "", [], {}, "unknown"):
                            continue
                        existing_po[k] = v
                        any_filled = True
                    session_state.slots["pref_overrides"] = existing_po

                # Clear pending follow-up only if we actually filled something
                if any_filled:
                    session_state.slots.pop("pending_fields", None)
                    session_state.slots.pop("pending_intent", None)
                    session_state.slots.pop("pending_domain", None)
    
        parsed_intent: ParsedIntent = self._run_intent_parser(req)
        parsed_intent = self._llm_routing_fallback(parsed_intent, req.input_text)  # ← ADD THIS LINE
        # ✅ INTENT LOCK: if we are waiting for follow-up fields, keep same intent/domain
        # if session_state and session_state.slots.get("pending_fields"):
        #     locked_intent = session_state.slots.get("pending_intent")
        #     locked_domain  = session_state.slots.get("pending_domain")

        #     if locked_intent:
        #         parsed_intent = parsed_intent.model_copy(update={
        #             "intent": locked_intent,
        #             "domain_category": locked_domain or parsed_intent.domain_category,
        #             # keep classifier scores if you want; confidence can be boosted a bit
        #             "confidence": max(float(parsed_intent.confidence or 0.0), 0.95),
        #             "secondary_intents": [],
        #         })

        #         # ✅ also merge session slots into entities so the newly provided dates are used
        #         ents = (
        #             parsed_intent.entities.model_dump(exclude_none=False)
        #             if hasattr(parsed_intent.entities, "model_dump")
        #             else dict(parsed_intent.entities or {})
        #         )

        #         # session slots may contain start_date/end_date/travel_month from resolve_followup
        #         for k, v in (session_state.slots or {}).items():
        #             if v in (None, "", [], {}, "unknown"):
        #                 continue
        #             if k not in ents or ents.get(k) in (None, "", [], {}, "unknown"):
        #                 ents[k] = v

        #         parsed_intent = parsed_intent.model_copy(update={"entities": Entities(**ents)})
        # ✅ INTENT LOCK: if we are waiting for follow-up fields, keep same intent/domain
        # BUT: only lock if the user is actually answering the follow-up, not asking something new
        if session_state and session_state.slots.get("pending_fields"):
            locked_intent = session_state.slots.get("pending_intent")
            locked_domain  = session_state.slots.get("pending_domain")

            # ── ESCAPE HATCH ──────────────────────────────────────────────────────────
            # If the classifier is highly confident the user wants something DIFFERENT,
            # clear the pending lock and let the new intent through.
            _classifier_intent = parsed_intent.intent or ""
            _classifier_conf   = float(parsed_intent.confidence or 0.0)
            _lock_escape = (
                locked_intent is not None
                and _classifier_intent != locked_intent
                and _classifier_conf >= 0.85          # classifier is sure
                and _classifier_intent not in {       # and it's a real routable intent
                    "smalltalk", "out_of_scope", "generic_fact_query"
                }
            )

            if _lock_escape:
                # User has pivoted to a different topic — clear the stale lock
                print(
                    f"[intent-lock] ESCAPE: classifier={_classifier_intent}({_classifier_conf:.2f}) "
                    f"overrides lock={locked_intent} — clearing pending state"
                )
                session_state.slots.pop("pending_fields", None)
                session_state.slots.pop("pending_intent", None)
                session_state.slots.pop("pending_domain", None)
                session_state.slots.pop("pending_clarification", None)
                # Fall through — parsed_intent stays as classifier returned it

            elif locked_intent:
                # ── NORMAL LOCK PATH (user is answering the follow-up) ───────────────
                parsed_intent = parsed_intent.model_copy(update={
                    "intent": locked_intent,
                    "domain_category": locked_domain or parsed_intent.domain_category,
                    "confidence": max(float(parsed_intent.confidence or 0.0), 0.95),
                    "secondary_intents": [],
                })

                ents = (
                    parsed_intent.entities.model_dump(exclude_none=False)
                    if hasattr(parsed_intent.entities, "model_dump")
                    else dict(parsed_intent.entities or {})
                )

                # Layer 1: pull ALL relevant entity keys from session slots (previous turn context)
                ENTITY_SLOT_KEYS = {
                    "city", "destination", "origin", "origin_city", "country",
                    "days", "start_date", "end_date", "travel_month",
                    "waypoints", "include_stops", "region",
                }
                for k in ENTITY_SLOT_KEYS:
                    v = session_state.slots.get(k)
                    if v in (None, "", [], {}, "unknown"):
                        continue
                    if ents.get(k) in (None, "", [], {}, "unknown"):
                        ents[k] = v

                # Layer 2: also sweep ALL other slots (catches anything not in the explicit list)
                for k, v in (session_state.slots or {}).items():
                    if v in (None, "", [], {}, "unknown"):
                        continue
                    if k not in ents or ents.get(k) in (None, "", [], {}, "unknown"):
                        ents[k] = v

                parsed_intent = parsed_intent.model_copy(update={"entities": Entities(**ents)})
        resolved = resolve_context(
            parsed_intent=parsed_intent,
            req=req,
            session_state=session_state,
            trip_repo=self.trip_repo,
        )

        # --- APPLY resolved context into entities ---
        ents = (
            parsed_intent.entities.model_dump(exclude_none=False)
            if hasattr(parsed_intent.entities, "model_dump")
            else dict(parsed_intent.entities or {})
        )

        # Fill missing fields from session / resolver
        if not ents.get("city"):
            ents["city"] = (resolved.city if hasattr(resolved, "city") else None) or \
                        (session_state.slots.get("city") if session_state else None) or \
                        (session_state.slots.get("active_place") if session_state else None)

        if not ents.get("country"):
            ents["country"] = (resolved.country if hasattr(resolved, "country") else None) or \
                            (session_state.slots.get("country") if session_state else None)
            
                # ✅ carry origin from session if user already provided it (for corridor routing)
        if session_state and not ents.get("origin_city"):
            ents["origin_city"] = session_state.slots.get("origin_city")

        # (optional if your schema uses "origin" sometimes)
        if session_state and not ents.get("origin"):
            ents["origin"] = session_state.slots.get("origin")

        # also handle "tomorrow" already extracted - fine
        oc = ents.get("origin_city")
        if isinstance(oc, str):
            oc2 = oc.strip()
            if len(oc2) > 25 or "trip" in oc2.lower() or "." in oc2:
                ents["origin_city"] = None

        parsed_intent = parsed_intent.model_copy(update={"entities": Entities(**ents)})

        active_trip_id = None
        if session_state:
            active_trip_id = session_state.slots.get("active_trip_id")

        if not active_trip_id:
            active_trip_id = resolved.trip_id or trip_id  # fallback

        # ✅ update session slots (active context)
        if session_state:
            if resolved.city:
                session_state.slots["active_place"] = resolved.city
            if resolved.trip_id:
                session_state.slots["active_trip_id"] = resolved.trip_id
        # ✅ merge entities into session slots (save context)
        # merge entities into session slots (save context)
        if session_state:
            ents = parsed_intent.entities.model_dump(exclude_none=True)

            for k, v in ents.items():
                if v in (None, "", [], {}, "unknown"):
                    continue

                # ✅ only block stale trip references, NOT city/destination
                if parsed_intent.intent == "plan_itinerary" and k in {
                    "itinerary_id", "current_itinerary", "active_trip_id"
                }:
                    continue

                session_state.slots[k] = v

            # track last intent
            session_state.last_intent = parsed_intent.intent

            # minimal stage update (optional)
            if parsed_intent.intent in {"plan_itinerary", "modify_itinerary"}:
                session_state.conversation_stage = "itinerary"
        if user_id:
            self.profile_event_store.append(
                ProfileEvent(
                    user_id=user_id,
                    session_id=session_id,
                    event_type="intent_parsed",
                    intent=parsed_intent.intent,
                    payload={
                        "raw_text": parsed_intent.raw_text,   # ✅ store raw text (cleaned)
                        "confidence": parsed_intent.confidence,
                        "scores": parsed_intent.scores,
                        "unknown_amenities": (
                            parsed_intent.preference_overrides.get("_unknown_amenities", [])
                            if isinstance(parsed_intent.preference_overrides, dict)
                            else (
                                parsed_intent.preference_overrides.model_dump().get("_unknown_amenities", [])
                                if hasattr(parsed_intent.preference_overrides, "model_dump")
                                else []
                            )
                        ),
                        "entities": (
                            parsed_intent.entities.model_dump(exclude_none=True)
                            if hasattr(parsed_intent.entities, "model_dump")
                            else parsed_intent.entities
                        ),

                        "query_preference_overrides": (
                            parsed_intent.preference_overrides.model_dump(exclude_none=True)
                            if hasattr(parsed_intent.preference_overrides, "model_dump")
                            else dict(parsed_intent.preference_overrides or {})
                        ),
                    },
                )
            )
        # active_trip = bool(active_trip_id)
        # parsed_intent = resolve_intent(parsed_intent, req.input_text, active_trip)
        parsed_intent = apply_intent_policy(parsed_intent, req.input_text, session_state)
        # ✅ NEW: domain-based override (generic_fact_query -> real capability)
        parsed_intent = apply_domain_overrides(parsed_intent)
        # ✅ if edit context was passed (e.g. from booking edit sheet), merge into entities
        # ✅ if edit context was passed (e.g. from booking edit sheet), force book_hotel + merge entities
        if request_context:
            parsed_intent = parsed_intent.model_copy(update={
                "intent": "book_hotel",
                "domain_category": "booking",
                "confidence": 1.0,
                "secondary_intents": [],
            })
            print(f"[DEBUG edit-flow] intent AFTER override={parsed_intent.intent}")
            print(f"[DEBUG edit-flow] entities AFTER merge={parsed_intent.entities}")
            ents = (
                parsed_intent.entities.model_dump(exclude_none=False)
                if hasattr(parsed_intent.entities, "model_dump")
                else dict(parsed_intent.entities or {})
            )
            for k, v in request_context.items():
                if k == "draft_id":
                    continue  # draft_id is not an entity, handled separately
                if v is not None:
                    ents[k] = v  # context overrides whatever classifier extracted
            parsed_intent = parsed_intent.model_copy(update={"entities": Entities(**ents)})
            print(f"[context-merge] forced intent=book_hotel, merged context keys: {list(request_context.keys())}")

        bb.intents = {
            "primary": parsed_intent.intent,
            "secondary": parsed_intent.secondary_intents or [],
            "confidence": parsed_intent.confidence,
            "scores": parsed_intent.scores or {},
            "domain_category": parsed_intent.domain_category,
        }

        bb.entities = (
            parsed_intent.entities.model_dump(exclude_none=False)
            if hasattr(parsed_intent.entities, "model_dump")
            else dict(parsed_intent.entities or {})
        )

        # keep slots snapshot fresh (optional but nice)
        bb.slots = dict(session_state.slots) if session_state else bb.slots

        def _is_unknown_origin(text: str) -> bool:
            t = (text or "").strip().lower()
            return t in {"idk", "i don't know", "dont know", "not sure", "no idea", "skip", "ignore"}

        def _looks_like_city(s: str) -> bool:
            t = (s or "").strip().lower()
            if not t:
                return False
            # reject obvious full prompts / non-answers
            if any(x in t for x in ["plan", "trip", "itinerary"]):
                return False
            if "." in t:          # sentences like "Plan a 4 day trip..."
                return False
            if len(t) > 35:       # too long to be a city label
                return False
            return True

        if session_state and session_state.slots.get("pending_clarification") == "origin_city":
            raw = (req.input_text or "").strip()

            # Clear pending flag no matter what (prevents double-consumption)
            session_state.slots.pop("pending_clarification", None)

            if _is_unknown_origin(raw) or not _looks_like_city(raw):
                # don't store junk
                session_state.slots.pop("origin_city", None)
            else:
                session_state.slots["origin_city"] = raw

                # patch entities so current request can proceed
                ents = parsed_intent.entities.model_dump(exclude_none=False)
                ents["origin_city"] = raw
                parsed_intent = parsed_intent.model_copy(update={"entities": Entities(**ents)})

        tasks: List[TaskSummary] = self.task_graph_builder.build(parsed_intent)

        # ── SECONDARY INTENT INJECTION ─────────────────────────────────────
        # task_graph_builder only sees secondary_intents list from DeBERTa.
        # But good secondaries can score high WITHOUT being in that list.
        # Scan ALL scores here and inject anything we missed.
        _sec_scores  = parsed_intent.scores or {}
        _sec_primary = (parsed_intent.intent or "").strip()
        _active_types = {t.type for t in tasks}

        # Hard block: never run these as secondaries
        _sec_hard_block = DISALLOW_SECONDARY | {"book_hotel"}

        _sec_candidates: List[tuple] = []
        for _sint, _sscore in _sec_scores.items():
            _sscore = float(_sscore)
            if _sint == _sec_primary:          continue  # already primary
            if _sint in _sec_hard_block:       continue  # blocked
            if _sint not in self.handlers:     continue  # not routable
            if _sint in _active_types:         continue  # already in graph
            if _sscore < 0.12:                 continue  # noise floor

            _sec_candidates.append((_sint, _sscore))

        # sort by score, cap at 2
        _sec_candidates.sort(key=lambda x: -x[1])
        _sec_candidates = _sec_candidates[:2]

        _sec_next_num = len(tasks) + 1
        _sec_injected: List[tuple] = []
        for _sint, _sscore in _sec_candidates:
            _new_tid = f"T{_sec_next_num}"
            _sec_next_num += 1
            tasks.append(TaskSummary(
                id=_new_tid,
                type=_sint,
                status="pending",
                assigned_agent="OrchestratorAgent",
            ))
            _sec_injected.append((_new_tid, _sint, _sscore))
            print(f"[secondary-inject] {_new_tid} type={_sint} score={_sscore:.2f}")
        # ──────────────────────────────────────────────────────────────────
        if self.trace_pg:
            self.trace_pg.update_run(
                trace_id=request_trace_id,
                parsed_intent=parsed_intent.model_dump(mode="json"),
                planned_tasks={"tasks": [t.model_dump(mode="json") for t in tasks]},
            )
            self.trace_pg.add_event(
                trace_id=request_trace_id,
                session_id=session_id,
                user_id=user_id,
                turn_id=turn_id,
                event_type="task_graph_planned",
                status="ok",
                request_payload={"tasks": [t.model_dump(mode="json") for t in tasks]},
            )

        bb.tool_results = {
            "weather_result": None,
            "crowd_result": None,
            "price_result": None,
            "itinerary_result": None,
            "modify_result": None,
            "visa_result": None,
            "accommodation_result": None,
            "transport_result": None,
            "attraction_result": None,
            "restaurant_result": None,
            "pois_result": None,
            "route_clarification": None,
            "missing_fields": None,
            "followup": None,
            "booking_result": None,
            
        }
        results = bb.tool_results 
        errors: List[AgentCallError] = []

        exec_tasks: List[ExecTask] = build_exec_tasks(self.task_graph_builder, parsed_intent)

        # Wire injected secondaries into exec graph
        _existing_exec_types = {et.type for et in exec_tasks}
        for _new_tid, _sint, _sscore in _sec_injected:
            if _sint in _existing_exec_types:
                continue
            exec_tasks.append(ExecTask(
                id=_new_tid,
                type=_sint,
                assigned_agent="OrchestratorAgent",
                depends_on=[],
            ))
            print(f"[secondary-exec] wired {_new_tid} type={_sint}")

        handlers: Dict[str, HandlerFn] = {}

        for t in exec_tasks:
            ttype = (t.type or "").strip()
            fn = None 

            if ttype == "parse_intent":

                async def _parse(task, ctx, results, pi=parsed_intent, _bb=bb):
                    _bb.intents.setdefault("raw", {})
                    data = pi.model_dump(mode="json") if hasattr(pi, "model_dump") else dict(pi)
                    _bb.intents["raw"]["parsed_intent"] = data
                    return AgentResult(
                        ok=True,
                        answer="",
                        data=data,
                        evidence=[],
                        missing_fields=[],
                        next_actions=[],
                        confidence=1.0,
                        safety_flags=[],
                        meta={"task": "parse_intent"},
                    )
                fn = _parse

            elif ttype == "extract_entities":

                async def _extract(task, ctx, results, pi=parsed_intent, _bb=bb):
                    ents = pi.entities
                    data = ents.model_dump(mode="json") if hasattr(ents, "model_dump") else dict(ents or {})
                    _bb.entities = data
                    return AgentResult(
                        ok=True,
                        answer="",
                        data=data,
                        evidence=[],
                        missing_fields=[],
                        next_actions=[],
                        confidence=1.0,
                        safety_flags=[],
                        meta={"task": "extract_entities"},
                    )
                fn = _extract

            elif ttype == "format_response":
                async def _format(task, ctx, results):
                    return AgentResult(
                        ok=True,
                        answer="",
                        data={"ok": True},
                        evidence=[],
                        missing_fields=[],
                        next_actions=[],
                        confidence=1.0,
                        safety_flags=[],
                        meta={"task": "format_response"},
                    )
                fn = _format
            elif ttype == "out_of_scope":
                async def _out_of_scope(task, ctx, results):
                    return AgentResult(
                        ok=True,
                        answer="I'm GraphCeylon, a Sri Lanka travel assistant. I can help with trip planning, weather forecasts, hotels, attractions and restaurants across Sri Lanka. What would you like to explore?",
                        data={"out_of_scope": True},
                        evidence=[],
                        missing_fields=[],
                        next_actions=[],
                        confidence=1.0,
                        safety_flags=[],
                        meta={"task": "out_of_scope"},
                    )
                fn = _out_of_scope

            elif ttype == "smalltalk":
                async def _smalltalk(task, ctx, results):
                    return AgentResult(
                        ok=True,
                        answer="I'm GraphCeylon, your Sri Lanka travel assistant! I can help you plan trips, check weather, find hotels, discover attractions and restaurants. What would you like to know?",
                        data={"smalltalk": True},
                        evidence=[],
                        missing_fields=[],
                        next_actions=[],
                        confidence=1.0,
                        safety_flags=[],
                        meta={"task": "smalltalk"},
                    )
                fn = _smalltalk

            
            elif ttype == "forecast_weather":
                async def _weather(task, ctx, results):
                    # Try to inherit from plan_itinerary output if available
                    it_out = results.get("plan_itinerary") or results.get("T3")  # depends on how executor stores keys

                    ents = (
                        parsed_intent.entities.model_dump(exclude_none=False)
                        if hasattr(parsed_intent.entities, "model_dump")
                        else dict(parsed_intent.entities or {})
                    )

                    if not ents.get("start_date") and it_out:
                        it_json = it_out.model_dump(mode="json") if hasattr(it_out, "model_dump") else dict(it_out)
                        meta = it_json.get("meta") or {}

                        if meta.get("start_date"):
                            ents["start_date"] = meta["start_date"]
                        if meta.get("days") and not ents.get("days"):
                            ents["days"] = meta["days"]
                        if meta.get("destination") and not ents.get("city"):
                            ents["city"] = meta["destination"]
                        if meta.get("country") and not ents.get("country"):
                            ents["country"] = meta["country"]

                    patched_pi = parsed_intent.model_copy(update={"entities": Entities(**ents)})

                    return await anyio.to_thread.run_sync(
                        self._execute_intent,
                        "forecast_weather",
                        patched_pi,
                        req,
                        db_prefs,
                        session_state,
                        request_trace_id,
                    )

                fn = _weather

            elif ttype in self.handlers:
                def make_handler(intent_name: str, _bb: Blackboard):
                    async def _run(task, ctx, results, _intent=intent_name):

                        # ✅ If gate said missing fields, skip calling downstream planner/modifier
                        # ✅ Gate: if missing fields, skip downstream plan/modify
                        mf = []
                        gate_out = results.get("validate_required_fields") or results.get("T3")

                        if isinstance(gate_out, AgentResult) and isinstance(gate_out.data, dict):
                            mf = gate_out.data.get("missing_fields") or []

                        # Optional debug
                        ok_to_plan = (len(mf) == 0)

                        if _intent in {"plan_itinerary", "modify_itinerary", "book_hotel"} and mf:
                            return AgentResult(
                                ok=True,
                                answer="",
                                data={
                                    "skipped": True,
                                    "reason": "missing_fields",
                                    "missing_fields": mf,
                                    "ok_to_plan": False,
                                },
                                evidence=[],
                                missing_fields=mf,
                                next_actions=[],
                                confidence=1.0,
                                safety_flags=[],
                                meta={"task": _intent, "skipped": True},
                            )

                        out = await anyio.to_thread.run_sync(
                            self._execute_intent,
                            _intent,
                            parsed_intent,
                            req,
                            db_prefs,
                            session_state,
                            request_trace_id,
                        )
                        return out
                    return _run

                fn = make_handler(ttype, bb)

                
            elif ttype == "validate_required_fields":
                async def _validate(task, ctx, results, pi=parsed_intent, _bb=bb):
                    intent = (pi.intent or "").strip()

                    ents = (
                        pi.entities.model_dump(exclude_none=False)
                        if hasattr(pi.entities, "model_dump")
                        else dict(pi.entities or {})
                    )

                    # ---- REQUIRED FIELDS (demo-safe strict) ----
                    # ---- REQUIRED FIELDS (demo-safe strict) ----
                    missing: List[str] = []


                    # ✅ Only enforce these requirements for plan_itinerary
                    if intent == "plan_itinerary":
                        # Dates: require either start_date OR travel_month
                        start_date = ents.get("start_date")
                        travel_month = ents.get("travel_month")

                        if not start_date and not travel_month:
                            missing.append("start_date")  # simplest label for demo
                        days = ents.get("days")
                        if not days:
                            missing.append("days")

                        # Destination/city: if only country-level ("Sri Lanka") and no city/destination
                        city = (ents.get("city") or "").strip() if isinstance(ents.get("city"), str) else ents.get("city")
                        dest = (ents.get("destination") or "").strip() if isinstance(ents.get("destination"), str) else ents.get("destination")
                        country = (ents.get("country") or "").strip().lower() if isinstance(ents.get("country"), str) else ""

                        city_l = (city or "").lower().strip()
                        city_is_country = city_l in {"sri lanka", "srilanka"}

                        if ((not city or city_is_country) and not dest) and country in {"sri lanka"}:
                            missing.append("destination_city")
                    elif intent == "book_hotel":
                        # accept either arrival/departure OR start_date/end_date (since your entities currently use start_date/end_date)
                        arrival = ents.get("arrival") or ents.get("start_date")
                        departure = ents.get("departure") or ents.get("end_date")

                        if not arrival:
                            missing.append("arrival")
                        if not departure:
                            missing.append("departure")
                    # ✅ For modify, do not block on dates/destination (it should use active_trip_id / stored plan)
                    elif intent == "modify_itinerary":
                        missing = []

                    # Origin (only if corridor routing / include_stops / route_mode wants it)
                    # For demo: require origin_city for plan_itinerary
                    # origin_city = (ents.get("origin_city") or "").strip() if isinstance(ents.get("origin_city"), str) else ents.get("origin_city")
                    # if intent == "plan_itinerary" and not origin_city:
                    #     missing.append("origin_city")

                    followup_question = None
                    followup_options: List[str] = []

                    if missing:
                        # Build a single friendly follow-up question
                        parts = []
                        if missing:
                            parts = []
                            if "start_date" in missing:
                                parts.append("When are you planning to travel?")
                            if "days" in missing:                                          # ✅ NEW
                                parts.append("How many days are you planning to stay?")
                            if "destination_city" in missing:
                                parts.append("Which city in Sri Lanka would you like to visit?")
                            if "arrival" in missing or "departure" in missing:
                                parts.append("What are your hotel dates? (check-in + check-out)")
                                followup_options += ["2026-06-03 to 2026-06-06", "This weekend", "Next week"]

                            followup_question = "\n".join(f"- {p}" for p in parts)

                            if "days" in missing:                                          # ✅ NEW
                                followup_options += ["1 day", "2 days", "3 days", "5 days"]
                            if "destination_city" in missing:
                                followup_options += ["Kandy", "Ella", "Nuwara Eliya", "Sigiriya"]
                            if "start_date" in missing:
                                followup_options += ["This weekend", "Next week", "April 2026"]

                    # write into results so other tasks can see it
                    results["missing_fields"] = missing
                    results["followup"] = {
                        "question": followup_question,
                        "options": followup_options,
                    } if missing else None

                    # persist pending clarification (optional but good)
                    if session_state and missing:
                        session_state.slots["pending_fields"] = missing
                        session_state.slots["pending_intent"] = pi.intent          # ✅ lock intent
                        session_state.slots["pending_domain"] = pi.domain_category # ✅ optional
                        # if you want single-field gating:
                        # if "origin_city" in missing:
                        #     session_state.slots["pending_clarification"] = "origin_city"

                    return AgentResult(
                        ok=True,
                        answer="",
                        data={
                            "missing_fields": missing,
                            "followup": {
                                "question": followup_question,
                                "options": followup_options,
                            } if missing else None,
                        },
                        evidence=[],
                        missing_fields=missing,
                        next_actions=[],
                        confidence=1.0,
                        safety_flags=[],
                        meta={"task": "validate_required_fields"},
                    )
                fn = _validate


            elif ttype == "ask_followup":
                async def _ask(task, ctx, results):
                    gate_out = results.get("validate_required_fields") or results.get("T3")

                    mf = []
                    fu = {}

                    if isinstance(gate_out, AgentResult) and isinstance(gate_out.data, dict):
                        mf = gate_out.data.get("missing_fields") or []
                        fu = gate_out.data.get("followup") or {}
                    else:
                        # fallback: if you kept writing directly into results
                        mf = results.get("missing_fields") or []
                        fu = results.get("followup") or {}

                    if not mf:
                        return AgentResult(
                            ok=True,
                            answer="",
                            data={"asked": False},
                            evidence=[],
                            missing_fields=[],
                            next_actions=[],
                            confidence=1.0,
                            safety_flags=[],
                            meta={"task": "ask_followup"},
                        )

                    question = fu.get("question") or "I need a bit more info to plan your trip."
                    options = fu.get("options") or []

                    return AgentResult(
                        ok=True,
                        answer="",
                        data={
                            "asked": True,
                            "question": question,
                            "options": options,
                            "missing_fields": mf,
                        },
                        evidence=[],
                        missing_fields=mf,
                        next_actions=[
                            {
                                "action_type": "ask_followup",   # ✅ FIXED
                                "fields": mf,
                                "question": question,
                                "options": options,
                            }
                        ],
                        confidence=1.0,
                        safety_flags=[],
                        meta={"task": "ask_followup"},
                    )
                fn = _ask


            else:
                async def _unknown(task, ctx, results, tt=ttype, tid=t.id):
                    return AgentResult(
                        ok=False,
                        answer="",
                        data=None,
                        evidence=[],
                        missing_fields=[],
                        next_actions=[],
                        confidence=0.0,
                        safety_flags=[
                            SafetyFlag(
                                code="UNKNOWN_TASK_TYPE",
                                severity=SafetySeverity.medium,
                                message=f"Unknown task type: {tt}",
                                meta={"task_type": tt, "task_id": tid},
                            )
                        ],
                        meta={"task_type": tt, "task_id": tid},
                    )
                fn = _unknown

            # ✅ register BOTH
            safe_fn = wrap_task(fn, ttype, t.id)
            handlers[ttype] = safe_fn
            handlers[t.id] = safe_fn


        async def _runner():
            return await run_task_graph(exec_tasks=exec_tasks, handlers=handlers)

        out = anyio.run(_runner)
        dag_results, exec_results, ctx = normalize_executor_output(out)
        explain_packets: List[Dict[str, Any]] = []

        for task in exec_tasks:
            out = dag_results.get(task.id) or dag_results.get(task.type)
            if out is None:
                continue

            # ✅ STRICT: every task MUST return AgentResult
            if not isinstance(out, AgentResult):
                errors.append(
                    AgentCallError(
                        agent="orchestrator",
                        endpoint="",
                        status_code=0,
                        error=f"Contract breach: task '{task.type}' did not return AgentResult",
                        detail={
                            "task_id": task.id,
                            "task_type": task.type,
                            "got_type": str(type(out)),
                            "value_preview": str(out)[:500],
                        },
                    )
                )
                continue

            # ✅ AgentResult failed
            # --- Collect explainability from meta for BOTH success & failure ---
            meta = out.meta or {}
            xp = meta.get("explainability")
            if isinstance(xp, dict):
                explain_packets.append(xp)

            # ✅ AgentResult failed
            if out.ok is False:
                # fix msg construction (your old code references msg before assignment)
                msg = "Task failed"
                if out.safety_flags:
                    msg = out.safety_flags[0].message or msg
                elif out.answer:
                    msg = out.answer

                errors.append(
                    AgentCallError(
                        agent=str(meta.get("provider", meta.get("agent", "unknown"))),
                        endpoint=str(meta.get("endpoint", "")),
                        status_code=int(meta.get("status_code", 0) or 0),
                        error=msg,
                        detail=(out.model_dump(mode="json") if hasattr(out, "model_dump") else str(out)),
                    )
                )
                continue

            # ✅ Success payload is ALWAYS out.data now
            payload = out.data
            ttype = task.type

            # ✅ expose gate outputs to formatter
            if ttype == "validate_required_fields":
                if isinstance(payload, dict):
                    results["missing_fields"] = payload.get("missing_fields") or []
                    # payload["followup"] is expected shape: {"question": "...", "options": [...]}
                    results["followup"] = payload.get("followup") or None

            elif ttype == "ask_followup":
                if isinstance(payload, dict) and payload.get("asked"):
                    results["followup"] = {
                        "question": payload.get("question"),
                        "options": payload.get("options") or [],
                    }
                    results["missing_fields"] = payload.get("missing_fields") or results.get("missing_fields") or []

            # ---------------------------
            # Replace ALL "out" usages below with "payload"
            # ---------------------------

            if ttype == "plan_itinerary":
                results["itinerary_result"] = payload

                it_res = payload
                it_json = it_res.model_dump(mode="json") if hasattr(it_res, "model_dump") else dict(it_res)

                route_plan = (it_json.get("plans") or {}).get("route_plan") or {}
                needs_origin = (
                    isinstance(route_plan, dict)
                    and route_plan.get("status") == "needs_clarification"
                    and route_plan.get("reason") == "origin_required_for_corridor"
                )

                ents_now = (
                    parsed_intent.entities.model_dump(exclude_none=False)
                    if hasattr(parsed_intent.entities, "model_dump")
                    else dict(parsed_intent.entities or {})
                )
                origin_missing = not (ents_now.get("origin") or ents_now.get("origin_city"))

                if needs_origin and origin_missing:
                    results["route_clarification"] = {
                        "type": "clarify_origin",
                        "question": route_plan.get("question")
                        or "Where are you starting from (e.g., Colombo), or are you already in Kandy? If you’re not sure, I can still plan just Kandy.",
                        "options": route_plan.get("options") or ["Starting from Colombo", "Already in Kandy", "Other / Not sure"],
                    }

                    if session_state:
                        session_state.slots["pending_clarification"] = "origin_city"
                        bb.pending_actions.append(
                            {"type": "clarification", "field": "origin_city", "reason": "origin_required_for_corridor"}
                        )
                        session_state.slots["pending_destination"] = (it_json.get("meta") or {}).get("destination")
                        session_state.slots["clarification_attempts"] = int(
                            session_state.slots.get("clarification_attempts", 0)
                        ) + 1

                ok = (it_json.get("status") == "ok") or (it_json.get("ok") is True)
                if ok:
                    meta = it_json.get("meta") or {}
                    days = meta.get("days") or it_json.get("days")
                    start_date = meta.get("start_date") or it_json.get("start_date")

                    dest = meta.get("destination")
                    if not dest:
                        plans = it_json.get("plans") or {}
                        dp = plans.get("destination_plan") or {}
                        dest = dp.get("city") or dp.get("destination") or meta.get("destination")

                    title = f"{dest or 'Trip'} ({days or ''} days)".strip()

                    active_trip_id = session_state.slots.get("active_trip_id") if session_state else None

                    active_trip_dest = None
                    if active_trip_id and user_id:
                        trip = self.trip_repo.get_trip(trip_id=active_trip_id, user_id=user_id)
                        if trip:
                            active_trip_dest = (trip.destination or "").strip()

                    is_new_trip = bool(dest) and bool(active_trip_dest) and dest.lower() != active_trip_dest.lower()

                    if active_trip_id and not is_new_trip:
                        self.trip_repo.update_trip_plan(
                            trip_id=active_trip_id,
                            title=title,
                            destination=dest,
                            start_date=start_date,
                            days=int(days) if days else None,
                            plan_json=it_json,
                        )
                        trip_id = active_trip_id
                    else:
                        trip_id = self.trip_repo.create_trip(
                            user_id=user_id,
                            title=title,
                            destination=dest,
                            start_date=start_date,
                            travel_month=None,
                            days=int(days) if days else None,
                            plan_json=it_json,
                        )

                    if session_state and trip_id:
                        session_state.slots["active_trip_id"] = trip_id
                        session_state.slots["active_place"] = dest
                        session_state.slots["city"] = dest

                continue

            elif ttype == "modify_itinerary":
                results["modify_result"] = payload

            elif ttype == "info_visa_policy":
                results["visa_result"] = payload

            elif ttype == "info_accommodation":
                results["accommodation_result"] = payload

            elif ttype == "info_transport":
                results["transport_result"] = payload

            elif ttype == "info_attraction":
                results["attraction_result"] = payload

            elif ttype == "forecast_weather":
                results["weather_result"] = payload

            elif ttype == "crowd_forecast":
                results["crowd_result"] = payload

            elif ttype == "forecast_price":
                results["price_result"] = payload

            elif ttype == "recommend_pois":
                results["pois_result"] = payload

            elif ttype == "recommend_restaurants":
                results["restaurant_result"] = payload
            elif ttype == "out_of_scope":
                results["final_message_override"] = payload.get("answer") if isinstance(payload, dict) else str(payload)

            elif ttype == "smalltalk":
                results["final_message_override"] = payload.get("answer") if isinstance(payload, dict) else str(payload)
            elif ttype == "book_hotel":
                results["booking_result"] = payload

                payload_dict = (
                    payload.model_dump(mode="json")
                    if hasattr(payload, "model_dump")
                    else dict(payload or {})
                )

                is_pricing_ready = (
                    isinstance(payload_dict, dict)
                    and payload_dict.get("ok") is True
                    and payload_dict.get("status") == "pricing_ready"
                )

                if is_pricing_ready and user_id:
                    # ✅ if editing an existing draft, update it instead of creating new
                    existing_draft_id = (
                        request_context.get("draft_id")          # passed from Flutter edit flow
                        or session_state.slots.get("active_draft_id")  # stored from previous turn
                    ) if request_context else session_state.slots.get("active_draft_id")

                    draft_id = save_booking_draft(
                        user_id=user_id,
                        session_id=session_id,
                        booking_result=payload_dict,
                        existing_draft_id=existing_draft_id,    # ✅ None = create, str = update
                    )
                    if draft_id:
                        results["booking_result"]["draft_id"] = draft_id
                        if session_state:
                            session_state.slots["active_draft_id"] = draft_id

            
        # ✅ After DAG mapping: apply modify update to active trip
        # ✅ apply modify update once
        mod_res = results.get("modify_result")
        if user_id and mod_res and session_state:
            active_trip_id = session_state.slots.get("active_trip_id")
            if active_trip_id:
                mod_json = mod_res.model_dump(mode="json") if hasattr(mod_res, "model_dump") else dict(mod_res)
                ok = (mod_json.get("status") == "ok") or (mod_json.get("ok") is True)
                if ok:
                    meta = mod_json.get("meta") or {}
                    days = meta.get("days") or mod_json.get("days")
                    start_date = meta.get("start_date") or mod_json.get("start_date")

                    dest = meta.get("destination")
                    title = None
                    if dest or days:
                        title = f"{dest or 'Trip'} ({days or ''} days)".strip()

                    new_plan = mod_json.get("plan") or mod_json  # depends on response structure
                    self.trip_repo.update_trip_plan(
                        trip_id=active_trip_id,
                        title=title,
                        destination=dest,
                        start_date=start_date,
                        days=int(days) if days else None,
                        plan_json=new_plan,
                    )

        task_status_by_id: Dict[str, str] = {}
        for task in exec_tasks:
            out = dag_results.get(task.id) or dag_results.get(task.type)
            task_status_by_id[task.id] = "completed" if out not in (None, {"ok": False}) else "failed"
            
         
        print("[orchestrator] dag_results keys =", list(dag_results.keys()))

        # If exec_results has richer status, use it:
        for r in (exec_results or []):
            rid = getattr(r, "id", None)
            rstatus = getattr(r, "status", None)
            if rid and rstatus:
                task_status_by_id[rid] = rstatus

        # Update your TaskSummary list
        updated_tasks: List[TaskSummary] = []
        for ts in tasks:
            new_status = task_status_by_id.get(ts.id, ts.status)
            updated_tasks.append(ts.model_copy(update={"status": new_status}))

        tasks = updated_tasks

        if user_id:
            try:
                self.maybe_run_phase3(user_id=user_id, session_id=session_id)
            except Exception as e:
                print(f"[phase3] trigger failed: {e}")
        
        results["explainability"] = merge_explain(explain_packets)
        # Override final message for out_of_scope and smalltalk
        if results.get("final_message_override"):
            formatted = {
                "text": results["final_message_override"],
                "followups": [
                    "Weather in Colombo",
                    "Hotels in Kandy",
                    "Plan a trip to Ella",
                    "Places to visit in Galle",
                ],
                "explainability_ui": "",
                "sources": None,
            }
        else:
            formatted = self.response_formatter.format(
                user_text=req.input_text,
                parsed_intent=parsed_intent.model_dump(mode="json"),
                results=results,
                tasks=[t.model_dump(mode="json") for t in tasks],
            )

            # ✅ Unwrap if final_message is still a JSON string
            final_text = formatted.get("text", "")
            if isinstance(final_text, str) and final_text.strip().startswith("{"):
                try:
                    inner = json.loads(final_text)
                    if isinstance(inner, dict) and "text" in inner:
                        formatted["text"] = inner["text"]
                        if not formatted.get("followups") and inner.get("followups"):
                            formatted["followups"] = inner["followups"]
                except Exception:
                    pass
        # formatted = self.response_formatter.format(
        #     user_text=req.input_text,
        #     parsed_intent=parsed_intent.model_dump(mode="json"),
        #     results=results,
        #     tasks=[t.model_dump(mode="json") for t in tasks],
        # )
        # -------------------------
        # ✅ AGENTIC CLOSED LOOP: observe -> verify -> repair -> decide
        # -------------------------
        try:
            loop_out = self.agentic_loop.run(
                svc=self,
                parsed_intent=parsed_intent,
                req=req,
                db_prefs=db_prefs,
                session_state=session_state,
                request_trace_id=request_trace_id,
                results=results,
                max_repairs=int(os.getenv("AGENTIC_MAX_REPAIRS", "1")),
            )

            # Inject "what changed & why" + confidence into results so formatter can render it
            results["agentic_meta"] = {
                "confidence": loop_out.confidence,
                "quality_score": loop_out.verify_report.quality_score if loop_out.verify_report else None,
                "issues": [
                    {"code": i.code, "severity": i.severity, "message": i.message, "meta": i.meta}
                    for i in (loop_out.verify_report.issues if loop_out.verify_report else [])
                ],
                "repairs": [
                    {"name": r.name, "reason": r.reason, "meta": r.meta}
                    for r in loop_out.repairs_applied
                ],
                "changed_summary": loop_out.changed_summary,
                "verifier_meta": (
                    (loop_out.verify_report.meta or {}).get("verifier_meta", {})
                    if loop_out.verify_report else {}
                ),
            }

            if self.trace_pg:
                self.trace_pg.add_event(
                    trace_id=request_trace_id,
                    session_id=session_id,
                    user_id=user_id,
                    turn_id=turn_id,
                    event_type="agentic_loop",
                    status="ok",
                    request_payload={"agentic_meta": results["agentic_meta"]},
                )

        except Exception as e:
            print("[agentic] loop failed:", e)
        

        # ✅ If planner asked for origin clarification, append it to final message
        rc = results.get("route_clarification")
        if rc and isinstance(formatted, dict):
            formatted["text"] = (formatted.get("text") or "") + "\n\n" + str(rc.get("question") or "")
            if rc.get("options"):
                formatted["followups"] = (formatted.get("followups") or []) + list(rc["options"])

        bb.draft_answer = formatted
        bb.tool_results = results
        bb.pending_actions = bb.pending_actions or []

        bb.slots = dict(session_state.slots) if session_state else bb.slots

        print("[bb] primary:", bb.intents.get("primary"))
        print("[bb] entities:", list((bb.entities or {}).keys())[:8])
        print("[bb] tool_results non-null:", [k for k, v in bb.tool_results.items() if v is not None])
        print("[bb] pending_actions:", bb.pending_actions)
        if session_state and user_id and session_id != "no_session":
            self.session_store.save(
                user_id=user_id,
                session_id=session_id,
                state=session_state.to_dict(),
            )
        trace = self._export_trace(session_id=session_id)
        def _save_session_if_needed():
            if session_state and user_id and session_id != "no_session":
                self.session_store.save(user_id=user_id, session_id=session_id, state=session_state.to_dict())
        _save_session_if_needed()
        it = results.get("itinerary_result") or {}
        it_dict = it.model_dump(mode="json") if hasattr(it, "model_dump") else dict(it)
        print("outbound_stops count:", len(it_dict.get("outbound_stops") or []))
        print("return_stops count:", len(it_dict.get("return_stops") or []))
        return OrchestrateResponse(
            status="partial" if errors else "ok",
            message="Orchestration executed.",
            parsed_intent=parsed_intent,
            tasks=tasks,
            protocol_mode=self.protocol_mode,
            weather_result=results["weather_result"],
            crowd_result=results["crowd_result"],
            price_result=results["price_result"],
            itinerary_result=results["itinerary_result"],
            modify_result=results["modify_result"],
            visa_result=results["visa_result"],
            accommodation_result=results["accommodation_result"],
            restaurant_result = results["restaurant_result"],
            # "restaurant_result": None,
            pois_result = results["pois_result"],
            transport_result=results["transport_result"],
            booking_result=results["booking_result"],
            attraction_result=results["attraction_result"],
            final_message=formatted.get("text"),
            followups=formatted.get("followups"),
            trip_id=trip_id,
            errors=errors,
            trace=trace,
            agentic_meta=results.get("agentic_meta"),
            explainability=results.get("explainability"),
            explainability_ui=formatted.get("explainability_ui"),
            sources=formatted.get("sources"),
        )