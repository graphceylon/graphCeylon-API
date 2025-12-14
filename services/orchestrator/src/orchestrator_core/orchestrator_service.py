# orchestrator_core/orchestrator_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

import os
import requests
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
from .contracts.weather import WeatherForecastRequest, WeatherForecastResponse

from .mappers.crowd_mapper import map_crowd_request
from .contracts.crowd import CrowdForecastRequest, CrowdForecastResponse

from .mappers.price_mapper import map_price_request
from .contracts.price import PriceForecastRequest, PriceForecastResponse

from .mappers.itinerary_mapper import map_itinerary_request
from .contracts.itinerary import ItineraryPlanRequest, ItineraryPlanResponse

from .mappers.itinerary_modify_mapper import map_itinerary_modify_request
from .contracts.itinerary_modify import ItineraryModifyRequest, ItineraryModifyResponse

from .mappers.sustainability_mapper import map_sustainability_request
from .contracts.sustainability import SustainabilityForecastRequest  # response optional later

from .mappers.recommend_pois_mapper import map_recommend_pois_request
from .contracts.recommend_pois import RecommendPOIsRequest  # response optional later


RECOMMENDER_BASE_URL = os.getenv("RECOMMENDER_SERVICE_URL", "http://recommender_service:8003").rstrip("/")


@dataclass(frozen=True)
class IntentHandler:
    endpoint: str
    mapper: Callable[[ParsedIntent, OrchestrateRequest], BaseModel]
    response_model: Optional[Type[BaseModel]] = None
    timeout: int = 20
    # which OrchestrateResponse field to populate (keep your existing schema)
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

        # One place to register everything
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
            # If you don’t have response models yet, keep response_model=None.
            "forecast_sustainability": IntentHandler(
                endpoint="/forecast/sustainability",
                mapper=map_sustainability_request,
                response_model=None,
                timeout=20,
                result_field=None,  # you’re not returning sustainability_result yet
            ),
            "recommend_pois": IntentHandler(
                endpoint="/recommend/pois",
                mapper=map_recommend_pois_request,
                response_model=None,
                timeout=20,
                result_field=None,  # you’re not returning recommend_pois_result yet
            ),
        }

    # ---------------------------
    # Generic HTTP caller (one function for all)
    # ---------------------------
    def _post_to_recommender(self, endpoint: str, payload: dict, timeout: int) -> Optional[dict]:
        url = f"{RECOMMENDER_BASE_URL}{endpoint}"
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json() if resp.content else None
        except Exception as e:
            print(f"Error calling recommender {url}:", e)
            return None

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

    def orchestrate(self, req: OrchestrateRequest) -> OrchestrateResponse:
        parsed_intent: ParsedIntent = self._run_intent_parser(req)
        tasks: List[TaskSummary] = self.task_graph_builder.build(parsed_intent)

        # Keep your existing response fields so schema doesn't break
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

            print(f"=== {contract_obj.__class__.__name__} payload ===")
            print(contract_obj.model_dump())

            raw = self._post_to_recommender(
                endpoint=handler.endpoint,
                payload=contract_obj.model_dump(),
                timeout=handler.timeout,
            )

            # If you have a response model, parse it and put into the correct field
            if raw is not None:
                if handler.response_model is not None:
                    try:
                        parsed = handler.response_model(**raw)
                    except Exception as e:
                        print("Error parsing response into model:", e)
                        parsed = None
                else:
                    # For endpoints you haven't finalized yet (sustainability/recommend_pois)
                    print(f"Response from {parsed_intent.intent}:")
                    print(raw)
                    parsed = None

                if handler.result_field and handler.result_field in results:
                    results[handler.result_field] = parsed

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
