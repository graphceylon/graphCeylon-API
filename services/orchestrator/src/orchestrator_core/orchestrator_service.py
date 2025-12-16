from __future__ import annotations

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

# ✅ registry + adapter + tracing (use RELATIVE imports)
from .runtime.registry.registry import AgentRegistry
from .runtime.registry.models import AgentSpec, SLA
from .runtime.adapters.a2a import A2AHttpAdapter
from .runtime.trace import InMemoryTraceStore, TraceEvent


RECOMMENDER_BASE_URL = os.getenv(
    "RECOMMENDER_SERVICE_URL",
    "http://recommender_service:8003",
).rstrip("/")


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
        }

        # ✅ 2) registry
        self.registry = AgentRegistry(
            agents=[
                AgentSpec(
                    agent_id="recommender",
                    base_url=RECOMMENDER_BASE_URL,
                    protocols=["a2a"],  # later: ["a2a", "mcp", "blackboard"]
                    capabilities=list(self.handlers.keys()),
                    sla=SLA(p95_ms=1200, success_rate=0.98),
                    cost_weight=1.0,
                )
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
        session_id = self._clean_session_id(req)
        user_id = self._clean_user_id(req)

        parsed_intent: ParsedIntent = self._run_intent_parser(req)
        tasks: List[TaskSummary] = self.task_graph_builder.build(parsed_intent)

        # keep schema stable
        results: Dict[str, Any] = {
            "weather_result": None,
            "crowd_result": None,
            "price_result": None,
            "itinerary_result": None,
            "modify_result": None,
        }

        handler = self.handlers.get(parsed_intent.intent)

        if handler:
            contract_obj = handler.mapper(parsed_intent, req)
            payload = contract_obj.model_dump()

            print(f"=== {contract_obj.__class__.__name__} payload ===")
            print(payload)

            raw = self._invoke_capability_a2a(
                capability=parsed_intent.intent,
                endpoint=handler.endpoint,
                payload=payload,
                timeout=handler.timeout,
                session_id=session_id,
                user_id=user_id,
            )

            if raw is not None and handler.response_model is not None and handler.result_field:
                try:
                    results[handler.result_field] = handler.response_model(**raw)
                except Exception as e:
                    print("Error parsing response into model:", e)

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
        )
