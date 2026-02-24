# /Users/dev/Desktop/graphCeylon-API/services/orchestrator/src/orchestrator_core/orchestrator_service.py

from __future__ import annotations
import json
from pathlib import Path
import psycopg
from .context_resolver import resolve_context

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type
from uuid import uuid4

import os
import re
from pydantic import BaseModel

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
import os

from .mappers.crowd_mapper import map_crowd_request
from .contracts.crowd import CrowdForecastResponse

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

EDIT_VERBS = [
    "make it", "extend", "shorten", "change", "shift", "move", "swap",
    "redo", "regenerate", "replan", "remove", "delete", "drop", "exclude",
    "modify", "update", "edit"
]

EXPLICIT_HOTEL = ["book hotel", "hotel booking", "reserve hotel", "find hotels", "rooms", "check-in", "check out"]
EXPLICIT_VISA  = ["visa", "eta", "entry requirements"]
EXPLICIT_WEATHER = ["weather", "rain", "temperature", "forecast"]
EXPLICIT_TRANSPORT = ["how to go", "bus", "train", "taxi", "transport", "route"]

def norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())

def has_edit_signal(text: str, entities) -> bool:
    t = norm(text)
    if getattr(entities, "days", None):
        return True
    if getattr(entities, "start_date", None):
        return True
    if re.search(r"\bday\s*\d+\b", t):   # swap day 1 etc.
        return True
    return any(v in t for v in EDIT_VERBS)

def has_explicit_other_intent(text: str) -> bool:
    t = norm(text)
    # if any explicit other-intent phrases exist, don't override
    if any(k in t for k in EXPLICIT_HOTEL): return True
    if any(k in t for k in EXPLICIT_VISA): return True
    if any(k in t for k in EXPLICIT_WEATHER): return True
    if any(k in t for k in EXPLICIT_TRANSPORT): return True
    return False

def resolve_intent(parsed_intent, req_text: str, active_trip: bool):
    t = req_text or ""
    conf = float(getattr(parsed_intent, "confidence", 0.0))
    entities = parsed_intent.entities

    # If no active trip, keep classifier behavior (mostly)
    if not active_trip:
        return parsed_intent

    # Active trip exists: default to modify when edit signals appear
    if has_edit_signal(t, entities) and not has_explicit_other_intent(t):
        parsed_intent.intent = "modify_itinerary"
        parsed_intent.domain_category = "itinerary"
        return parsed_intent

    # If confidence is super low but looks like a start_date edit, still force modify
    if conf < 0.60 and getattr(entities, "start_date", None) and not has_explicit_other_intent(t):
        parsed_intent.intent = "modify_itinerary"
        parsed_intent.domain_category = "itinerary"

    return parsed_intent

def normalize_executor_output(out: Any) -> tuple[dict, list]:
    """
    Normalize TaskExecutor.run() output into:
      (dag_results_dict, exec_results_list)
    """

    # Case: already dict
    if isinstance(out, dict):
        return out, []

    # Case: ((dict, list), anything)
    if isinstance(out, tuple) and len(out) == 2:
        a, b = out

        if isinstance(a, tuple) and len(a) == 2 and isinstance(a[0], dict):
            dag, execs = a
            return dag, execs if isinstance(execs, list) else []

        if isinstance(b, tuple) and len(b) == 2 and isinstance(b[0], dict):
            dag, execs = b
            return dag, execs if isinstance(execs, list) else []

        if isinstance(a, dict):
            return a, b if isinstance(b, list) else []

    return {}, []



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
        self.response_formatter = ResponseFormatter()
        self.task_graph_builder = task_graph_builder
        self.protocol_mode = protocol_mode
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
        self.trace_store = InMemoryTraceStore(max_per_session=500)


        # ✅ 1) capability handlers
        self.handlers: Dict[str, IntentHandler] = {
            "info_transport": IntentHandler(
                endpoint="/railway/schedules/orchestrator/call/transport",      # ✅ your KG endpoint here
                mapper=map_transport_request,
                response_model=None,                # or TransportInfoResponse later
                timeout=20,
                result_field="transport_result",
            ),
            "info_attraction": IntentHandler(
                endpoint="/sub-attractions/orchestrator/call/sub-attractions",
                mapper=map_attraction_request,
                response_model=None,
                timeout=20,
                result_field="attraction_result",
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
                timeout=30,
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
                response_model=None,
                timeout=20,
                result_field=None,
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
                    capabilities=["info_visa_policy", "info_accommodation", "info_transport", "info_attraction"],


                    sla=SLA(p95_ms=1500, success_rate=0.98),
                    cost_weight=1.0,
                ),
            ]
        )

        # ✅ 3) A2A adapter
        self.a2a = A2AHttpAdapter()
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

    def _execute_intent(self, intent_name, parsed_intent, req, db_prefs, session_state=None) -> Any:


        handler = self.handlers.get(intent_name)
        if not handler:
            print(f"[orchestrator] No handler registered for intent={intent_name}")
            return

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

        merged_prefs, pref_source = merge_preferences(db_prefs=db_prefs, query_overrides=q_overrides)
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
        if intent_name == "modify_itinerary" and session_state and req.user_id:
            active_trip_id = session_state.slots.get("active_trip_id")
            if active_trip_id:
                trip = self.trip_repo.get_trip(trip_id=active_trip_id, user_id=req.user_id)
                if trip and trip.plan_json:
                    # Put these into patched_intent.entities so mapper can pick them up
                    ents = (
                        patched_intent.entities.model_dump(exclude_none=True)
                        if hasattr(patched_intent.entities, "model_dump")
                        else dict(patched_intent.entities or {})
                    )
                    ents["itinerary_id"] = active_trip_id
                    ents["current_itinerary"] = trip.plan_json

                    # also backfill location if missing
                    ents.setdefault("city", session_state.slots.get("city"))
                    ents.setdefault("country", session_state.slots.get("country"))
                    ents.setdefault("start_date", trip.start_date)

                    patched_intent = patched_intent.model_copy(update={"entities": ents})
        # 4) Build contract payload via mapper
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
        # ✅ Weather location resolver (prevents 500 when city is missing)
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

        # 6) Invoke downstream agent/service
        raw = self._invoke_capability_a2a(
            capability=intent_name,
            endpoint=handler.endpoint,
            payload=payload,
            timeout=handler.timeout,
            session_id=req.session_id or "no_session",
            user_id=req.user_id,
        )
       

        # ✅ EVENT: downstream result
        if req.user_id:
            self.profile_event_store.append(
                ProfileEvent(
                    user_id=req.user_id,
                    session_id=req.session_id or "no_session",
                    event_type="downstream_response",
                    intent=intent_name,
                    payload={
                        "endpoint": handler.endpoint,
                        "ok": raw is not None,
                        "response": raw if raw is not None else None,
                    },
                )
            )

        if raw is None:
            return


        # 7) Parse response ONCE (support response_model=None)
        parsed_obj: Any = None
        if handler.response_model is not None:
            try:
                parsed_obj = handler.response_model(**raw)
            except Exception as e:
                print(f"[orchestrator] Error parsing response for intent={intent_name}: {e}")
                parsed_obj = None
        else:
            print(f"[orchestrator] Raw response for {intent_name}:")
            print(raw)
            parsed_obj = raw

        return parsed_obj


    # ---------------------------
    # intent parse
    # ---------------------------
    def _run_intent_parser(self, req: OrchestrateRequest) -> ParsedIntent:
        result = self.intent_parser.parse(req.input_text)

        primary = result.get("primary_intent", "generic_fact_query")
        secondary = result.get("secondary_intents", [])
        scores = result.get("scores", {})
        raw_text = result.get("raw_text", req.input_text)
        entities = result.get("entities", {})
        preference_overrides = result.get("preference_overrides", {})
        domain_category = result.get("domain_category")

        confidence = float(scores.get(primary, 0.0))

        return ParsedIntent(
            domain_category=domain_category,
            intent=primary,
            confidence=confidence,
            secondary_intents=secondary,
            scores=scores,
            entities=entities,
            raw_text=raw_text,
            preference_overrides=preference_overrides,
        )

    # ---------------------------
    # main orchestrate
    # ---------------------------
    def orchestrate(self, req: OrchestrateRequest) -> OrchestrateResponse:
        user_id = (req.user_id or "").strip()
        session_id = (req.session_id or "").strip() or "no_session"
        session_state: Optional[SessionState] = None
        trip_id: Optional[str] = None


         # ✅ load session (per chat window / per session_id)
        session_state = None
        if user_id and session_id != "no_session":
            raw_state = self.session_store.get(user_id=user_id, session_id=session_id)
            session_state = SessionState.from_dict(raw_state)
        if session_state:
            trip_id = session_state.slots.get("active_trip_id")

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

        parsed_intent: ParsedIntent = self._run_intent_parser(req)
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

        # also handle "tomorrow" already extracted - fine

        parsed_intent = parsed_intent.model_copy(update={"entities": ents})

        active_trip_id = None
        if session_state:
            active_trip_id = session_state.slots.get("active_trip_id")

        if not active_trip_id:
            active_trip_id = resolved.trip_id or trip_id  # fallback
#         raw = (req.input_text or "").lower().strip()
#         duration_edit = bool(re.search(
#     r"\b(?:make(?:\s+it)?(?:\s+the\s+trip)?|change(?:\s+it)?|set)\s+\d{1,2}\s+day(?:s)?\b",
#     raw
# ))

#         active_trip_id = None
#         if session_state:
#             active_trip_id = session_state.slots.get("active_trip_id")
        # if not active_trip_id:
        #     active_trip_id = resolved.trip_id or trip_id  # fallback

        # if active_trip_id and duration_edit:
        #     scores = dict(parsed_intent.scores or {})
        #     scores["modify_itinerary"] = max(scores.get("modify_itinerary", 0.0), 0.95)

        #     ents = (
        #         parsed_intent.entities.model_dump(exclude_none=True)
        #         if hasattr(parsed_intent.entities, "model_dump")
        #         else dict(parsed_intent.entities or {})
        #     )
        #     ents["itinerary_id"] = active_trip_id

        #     parsed_intent = parsed_intent.model_copy(update={
        #         "intent": "modify_itinerary",
        #         "confidence": 0.95,
        #         "secondary_intents": [],   # prevent book_hotel DAG branch
        #         "scores": scores,
        #         "entities": ents,
        #     })

        # active_trip_id is decided above
        raw = (req.input_text or "").lower().strip()

        refers = any(w in raw for w in ["there", "it", "that place", "that city", "in that area"])

        if refers and not ents.get("city") and session_state:
            ents["city"] = session_state.slots.get("active_place") or session_state.slots.get("city")
            ents["country"] = ents.get("country") or session_state.slots.get("country")

        duration_edit = bool(re.search(
            r"\b(?:make(?:\s+it)?(?:\s+the\s+trip)?|change(?:\s+it)?|set)\s+\d{1,2}\s+day(?:s)?\b",
            raw
        ))

        date_edit = bool(re.search(
            r"\b(?:start|begin)\s+(?:the\s+trip\s+)?on\s+\d{4}-\d{2}-\d{2}\b",
            raw
        )) or bool(getattr(parsed_intent.entities, "start_date", None))

        # if user is clearly talking about hotels/bookings, don't force modify
        hotel_like = bool(re.search(
            r"\b(hotel|book|booking|reserve|reservation|check[-\s]?in|check[-\s]?out)\b",
            raw
        ))

        generic_modify = bool(re.search(
            r"\b(modify|change|update|edit|remove|delete|drop|swap|move|redo|regenerate|replan)\b",
            raw
        ))

        if active_trip_id and (duration_edit or date_edit or generic_modify) and not hotel_like:
            scores = dict(parsed_intent.scores or {})

            # hard boost modify
            scores["modify_itinerary"] = 0.95

            # suppress booking branches so cancel_booking/book_hotel doesn't get scheduled
            for k in ["book_hotel", "cancel_booking", "modify_booking", "check_availability"]:
                if k in scores:
                    scores[k] = min(scores[k], 0.01)

            ents = (
                parsed_intent.entities.model_dump(exclude_none=True)
                if hasattr(parsed_intent.entities, "model_dump")
                else dict(parsed_intent.entities or {})
            )
            ents["itinerary_id"] = active_trip_id

            parsed_intent = parsed_intent.model_copy(update={
                "intent": "modify_itinerary",
                "domain_category": "itinerary",
                "confidence": 0.95,
                "secondary_intents": [],   # ✅ critical
                "scores": scores,          # ✅ critical
                "entities": ents,
            })

        # ✅ update session slots (active context)
        if session_state:
            if resolved.city:
                session_state.slots["active_place"] = resolved.city
            if resolved.trip_id:
                session_state.slots["active_trip_id"] = resolved.trip_id
        # ✅ merge entities into session slots (save context)
        if session_state:
            ents = (
                parsed_intent.entities.model_dump(exclude_none=True)
                if hasattr(parsed_intent.entities, "model_dump")
                else (parsed_intent.entities or {})
            )

            # merge new slots
            for k, v in ents.items():
                if v in (None, "", [], {}, "unknown"):
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
        active_trip = bool(active_trip_id)
        parsed_intent = resolve_intent(parsed_intent, req.input_text, active_trip)
        tasks: List[TaskSummary] = self.task_graph_builder.build(parsed_intent)

        results: Dict[str, Any] = {
            "weather_result": None,
            "crowd_result": None,
            "price_result": None,
            "itinerary_result": None,
            "modify_result": None,
            "visa_result": None,
            "accommodation_result": None,
            "transport_result": None,
            "attraction_result": None,
        }

                # ---------------------------
        # NEW: Execute task graph (DAG)
      
        # ---------------------------
        # ---------------------------
        # ---------------------------
        # Execute task graph (DAG)
        # ---------------------------

        # 1) Build ExecTasks from your graph builder
        exec_tasks: List[ExecTask] = build_exec_tasks(self.task_graph_builder, parsed_intent)

        handlers: Dict[str, HandlerFn] = {}

        for t in exec_tasks:
            ttype = (t.type or "").strip()

            if ttype in {"parse_intent", "extract_entities", "format_response"}:
                async def _noop(task, ctx, results):
                    return {"ok": True}
                fn = _noop

            elif ttype in self.handlers:
                def make_handler(intent_name: str):
                    async def _run(task, ctx, results):
                        return await anyio.to_thread.run_sync(
                            self._execute_intent,
                            intent_name,
                            parsed_intent,
                            req,
                            db_prefs,
                            session_state,
                        )
                    return _run
                fn = make_handler(ttype)

            else:
                async def _unknown(task, ctx, results, tt=ttype):
                    return {"ok": False, "error": f"Unknown task type: {tt}"}
                fn = _unknown

            # register both keys (NO extra overwrite)
            handlers[ttype] = fn
            handlers[t.id] = fn

        

        





        # 3) Run the graph (IMPORTANT: anyio.run takes only a coroutine function)
        async def _runner():
            return await run_task_graph(exec_tasks=exec_tasks, handlers=handlers)

        dag_results, exec_results, ctx = anyio.run(_runner)

        # 🔥 Map DAG outputs into response fields
        for task in exec_tasks:
            out = dag_results.get(task.id)
            if not out:
                continue

            ttype = task.type

            if ttype == "plan_itinerary":
                results["itinerary_result"] = out

                it_res = out
                it_json = it_res.model_dump(mode="json") if hasattr(it_res, "model_dump") else dict(it_res)

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

                    if active_trip_id:
                        # ✅ UPDATE same row
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
                        # ✅ CREATE new trip
                        trip_id = self.trip_repo.create_trip(
                            user_id=user_id,
                            title=title,
                            destination=dest,
                            start_date=start_date,
                            travel_month=None,
                            days=int(days) if days else None,
                            plan_json=it_json,
                        )

                    # ✅ THIS is where you put it (AFTER trip_id is decided)
                    if session_state and trip_id:
                        session_state.slots["active_trip_id"] = trip_id

                continue
            elif ttype == "modify_itinerary":
                results["modify_result"] = out

            if ttype == "info_visa_policy":
                results["visa_result"] = out
            elif ttype == "info_accommodation":
                results["accommodation_result"] = out
            elif ttype == "info_transport":
                results["transport_result"] = out
            elif ttype == "info_attraction":
                results["attraction_result"] = out

            elif ttype == "forecast_weather":
                results["weather_result"] = out
            elif ttype == "crowd_forecast":
                results["crowd_result"] = out
            elif ttype == "forecast_price":
                results["price_result"] = out
            

            
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



        


        # 6) OPTIONAL but recommended: update TaskSummary statuses from exec_results
        #    If your TaskExecutor returns ExecResult objects with fields like id/status.
        #    Otherwise, mark as completed if output exists.
        # 🔥 Update task status based on DAG execution
        task_status_by_id: Dict[str, str] = {}
        for task in exec_tasks:
            out = dag_results.get(task.id, None)
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

        formatted = self.response_formatter.format(
            user_text=req.input_text,
            parsed_intent=parsed_intent.model_dump(mode="json"),
            results=results,
            tasks=[t.model_dump(mode="json") for t in tasks],
        )
        if session_state and user_id and session_id != "no_session":
            self.session_store.save(
                user_id=user_id,
                session_id=session_id,
                state=session_state.to_dict(),
            )

        return OrchestrateResponse(
            status="ok",
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
            transport_result=results["transport_result"],
            attraction_result=results["attraction_result"],
            final_message=formatted.get("text"),
            followups=formatted.get("followups"),
            trip_id=trip_id,
        )