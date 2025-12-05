# api/main.py

from fastapi import FastAPI
from api.schemas import OrchestrateRequest, OrchestrateResponse
from orchestrator_core.orchestrator_service import OrchestratorService
from orchestrator_core.intent_parser.agent import IntentParserAgent
from orchestrator_core.task_graph_builder import TaskGraphBuilder

app = FastAPI(
    title="GraphCeylon Orchestrator",
    version="0.1.0",
    description="Tourism multi-agent orchestrator for Sri Lanka",
)

# 1) Instantiate the intent parser (DistilBERT multi-label model)
intent_parser_agent = IntentParserAgent(
    model_dir="models/intent_multilabel_final",  # <-- change if needed
    threshold=0.2,
    top_k_if_empty=2,
)
task_graph_builder = TaskGraphBuilder()

# 2) Instantiate the Orchestrator with the intent parser
orchestrator = OrchestratorService(
    intent_parser=intent_parser_agent,
    task_graph_builder=task_graph_builder,
    protocol_mode="direct",
)


@app.get("/")
def root():
    return {"message": "GraphCeylon Orchestrator running", "status": "ok"}


@app.post("/orchestrate", response_model=OrchestrateResponse)
def orchestrate(req: OrchestrateRequest):
    """
    Main orchestration entrypoint.
    Currently:
      - runs DistilBERT intent parser
      - returns a dummy task graph
    """
    return orchestrator.orchestrate(req)
