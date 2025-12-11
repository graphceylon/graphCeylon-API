# orchestrator_core/orchestrator_service.py

from typing import List

import requests  # 👈 add this

from ..api.schemas import (
    OrchestrateRequest,
    OrchestrateResponse,
    ParsedIntent,
    TaskSummary,
)

from .intent_parser.agent import IntentParserAgent
from .task_graph_builder import TaskGraphBuilder

from .mappers.weather_mapper import map_weather_request  # 👈 add this
from .contracts.weather import WeatherForecastRequest     # 👈 add this



class OrchestratorService:
    """
    Orchestrator core.

    Current responsibilities:
      1) Call IntentParserAgent (DistilBERT multi-label model)
      2) Build a task graph from primary + secondary intents
      3) Return ParsedIntent + Task list (no execution yet)

    Later:
      - Execute tasks (call Rec Service, AttractionsAgent, etc.)
      - Support MCP / A2A / Blackboard protocols
      - Track KG evidence and HITL checkpoints
    """

    def __init__(
        self,
        intent_parser: IntentParserAgent,
        task_graph_builder: TaskGraphBuilder,
        protocol_mode: str = "direct",
    ) -> None:
        self.intent_parser = intent_parser
        self.task_graph_builder = task_graph_builder
        self.protocol_mode = protocol_mode
    def _call_weather_service(self, wf_req: WeatherForecastRequest) -> None:
        """
        TEMP: fire-and-forget call to the weather / recommender service.
        You said you don't care about the output yet, so we just log it.
        """
        url = "http://localhost:8003/forecast/weather"  # adjust later

        try:
            resp = requests.post(url, json=wf_req.model_dump())
            print("Weather service status:", resp.status_code)
            print("Weather service body:", resp.text)
        except Exception as e:
            print("Error calling weather service:", e)

    def _run_intent_parser(self, req: OrchestrateRequest) -> ParsedIntent:
        """
        Call DistilBERT intent parser and wrap result in ParsedIntent.
        """
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
            entities=entities,         # TODO: later fill with NER / slots
            raw_text=raw_text,
            preference_overrides = preference_overrides,
        )

    def orchestrate(self, req: OrchestrateRequest) -> OrchestrateResponse:
        """
        Main orchestration entrypoint used by /orchestrate.
        """
        # 1) Interpret user query → intents
        parsed_intent: ParsedIntent = self._run_intent_parser(req)

        # 2) Build initial task graph from intents
        tasks: List[TaskSummary] = self.task_graph_builder.build(parsed_intent)

        # 3) TEMP: if this is a weather forecast request, build and send WeatherForecastRequest
        if parsed_intent.intent == "forecast_weather":
            wf_req = map_weather_request(parsed_intent, req)
            print("=== WeatherForecastRequest payload ===")
            print(wf_req.model_dump())
            # Optional: actually call the weather / recommender service
            # self._call_weather_service(wf_req)

        # 4) Return orchestration plan (no execution yet)
        return OrchestrateResponse(
            status="ok",
            message="Orchestration stub executed.",
            parsed_intent=parsed_intent,
            tasks=tasks,
            protocol_mode=self.protocol_mode,
        )

