from fastapi import FastAPI

from .schemas import OrchestrateRequest, OrchestrateResponse
from ..orchestrator_core.orchestrator_service import OrchestratorService
from ..orchestrator_core.intent_parser.agent import IntentParserAgent
from ..orchestrator_core.task_graph_builder import TaskGraphBuilder

from ..profile.routes import router as profile_router
from ..profile.models import Base as ProfileBase
from ..profile.db import engine as profile_engine

app = FastAPI(
    title="GraphCeylon Orchestrator",
    version="0.1.0",
    description="Tourism multi-agent orchestrator for Sri Lanka",
)

# ✅ 1) Create tables on startup
@app.on_event("startup")
def _startup():
    ProfileBase.metadata.create_all(bind=profile_engine)

# ✅ 2) Mount profile API routes
app.include_router(profile_router)

# 1) Instantiate the intent parser
intent_parser_agent = IntentParserAgent(
    model_dir="C:\Desktop\graphCeylon-API\models\orchestrator\intent_multilabel_final",
    threshold=0.2,
    top_k_if_empty=2,
)

task_graph_builder = TaskGraphBuilder()

# 2) Instantiate the Orchestrator
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
    return orchestrator.orchestrate(req)

@app.get("/trace/{session_id}")
def get_trace(session_id: str):
    sid = session_id.strip()
    return {
        "session_id": sid,
        "events": [e.model_dump() for e in orchestrator.trace_store.list(sid)],
    }
