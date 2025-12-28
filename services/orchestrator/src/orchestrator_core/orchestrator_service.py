# /Users/dev/Desktop/graphCeylon-API/services/orchestrator/src/orchestrator_core/orchestrator_service.py

from __future__ import annotations
import json
from pathlib import Path

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type
from uuid import uuid4

import os
from pydantic import BaseModel

from ..api.schemas import (
    OrchestrateRequest,
    OrchestrateResponse,
    ParsedIntent,
    TaskSummary,
)

from .intent_parser.agent import IntentParserAgent
from .task_graph_builder import TaskGraphBuilder

# ---- mappers + contracts ----
from .mappers.weather_mapper import map_weather_request
from .contracts.weather import WeatherForecastResponse

from .mappers.crowd_mapper import map_crowd_request
from .contracts.crowd import CrowdForecastResponse

from .mappers.price_mapper import map_price_request
from .contracts.price import PriceForecastResponse

from .mappers.itinerary_mapper import map_itinerary_request
from .contracts.itinerary import ItineraryPlanResponse

from .mappers.itinerary_modify_mapper import map_itinerary_modify_request
from .contracts.itinerary_modify import ItineraryModifyResponse

from .mappers.sustainability_mapper import map_sustainability_request
from .mappers.recommend_pois_mapper import map_recommend_pois_request

from .agent_mappers.visa_policy_mapper import map_visa_policy_request
from .agent_contracts.visa_policy import VisaPolicyResponse  # optional (enable later)

# ✅ registry + adapter + tracing (use RELATIVE imports)
from .runtime.registry.registry import AgentRegistry
from .runtime.registry.models import AgentSpec, SLA
from .runtime.adapters.a2a import A2AHttpAdapter
from .runtime.trace import InMemoryTraceStore, TraceEvent

from ..profile.profile_client import ProfileClient


from .memory.preference_merge import merge_preferences




VISA_STUB_JSON = Path(__file__).resolve().parent / "visa_policy" / "visa.json"
# this points to: orchestrator_core/visa_policy/visa.json


RECOMMENDER_BASE_URL = os.getenv(
    "RECOMMENDER_SERVICE_URL",
    "http://recommender_service:8003",
).rstrip("/")

# ✅ NEW: Visa/KG base URL (your friend’s KG interface layer service)
VISA_KG_BASE_URL = os.getenv(
    "VISA_KG_SERVICE_URL",
    "http://visa_kg_service:8006",
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
        self.task_graph_builder = task_graph_builder
        self.protocol_mode = protocol_mode

        # ✅ Profile client (User Service)
        self.profile_client = ProfileClient()

        # ✅ trace store
        self.trace_store = InMemoryTraceStore(max_per_session=500)


        # ✅ 1) capability handlers
        self.handlers: Dict[str, IntentHandler] = {
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
                endpoint="/visa/policy",
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
                    capabilities=["info_visa_policy"],
                    sla=SLA(p95_ms=1500, success_rate=0.98),
                    cost_weight=1.0,
                ),
            ]
        )

        # ✅ 3) A2A adapter
        self.a2a = A2AHttpAdapter()

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

    def _execute_intent(
        self,
        intent_name: str,
        parsed_intent: ParsedIntent,
        req: OrchestrateRequest,
        results: Dict[str, Any],
        db_prefs: Dict[str, Any],
    ) -> None:

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


        patched_intent = patched_intent.model_copy(
            update={"preference_overrides": merged_prefs}
        )

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

        payload = contract_obj.model_dump(exclude_none=True)
        payload["preference_sources"] = pref_source  # ✅ add this


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

        # 8) Store into OrchestrateResponse result bucket
        if handler.result_field and handler.result_field in results:
            results[handler.result_field] = parsed_obj


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

        # ✅ fetch profile JSON from user service (single source of truth)
        profile_json = self.profile_client.get_profile(user_id) if user_id else None

        # ✅ extract db prefs from columns + preference_overrides
        db_prefs = self._extract_db_preferences(profile_json)

        parsed_intent: ParsedIntent = self._run_intent_parser(req)
        tasks: List[TaskSummary] = self.task_graph_builder.build(parsed_intent)

        results: Dict[str, Any] = {
            "weather_result": None,
            "crowd_result": None,
            "price_result": None,
            "itinerary_result": None,
            "modify_result": None,
            "visa_result": None,
        }

        intents_to_run: List[str] = []
        seen = set()

        def _add(i: str):
            if i and i not in seen:
                intents_to_run.append(i)
                seen.add(i)

        _add(parsed_intent.intent)
        for s in (parsed_intent.secondary_intents or []):
            _add(s)

        print(f"[orchestrator] intents_to_run={intents_to_run}")

        # 2) Execute each intent sequentially
        for intent_name in intents_to_run:
            self._execute_intent(intent_name, parsed_intent, req, results, db_prefs)


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
        )

