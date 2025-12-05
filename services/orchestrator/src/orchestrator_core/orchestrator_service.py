# orchestrator_core/orchestrator_service.py

from typing import List

from api.schemas import (
    OrchestrateRequest,
    OrchestrateResponse,
    ParsedIntent,
    TaskSummary,
)
from orchestrator_core.intent_parser.agent import IntentParserAgent
from orchestrator_core.task_graph_builder import TaskGraphBuilder


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

        Today:
          - Run intent parser
          - Build a task graph from intents
          - Return tasks (no execution yet)

        Later:
          - Execute each task (HTTP calls to C3, AttractionsAgent, etc.)
          - Maintain execution state + evidence
          - Apply protocol-specific behavior (MCP / A2A / blackboard)
        """
        # 1) Interpret user query → intents
        parsed_intent: ParsedIntent = self._run_intent_parser(req)

        # 2) Build initial task graph from intents
        tasks: List[TaskSummary] = self.task_graph_builder.build(parsed_intent)

        # 3) Return orchestration plan (no execution yet)
        return OrchestrateResponse(
            status="ok",
            message="Orchestration stub executed.",
            parsed_intent=parsed_intent,
            tasks=tasks,
            protocol_mode=self.protocol_mode,
        )
