from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .schemas import OrchestrateRequest, OrchestrateResponse
from ..orchestrator_core.orchestrator_service import OrchestratorService
from ..orchestrator_core.intent_parser.agent import IntentParserAgent
from ..orchestrator_core.task_graph_builder import TaskGraphBuilder
from .events_routes import router as events_router
from .booking_routes import router as booking_router
from .benchmark_routes import router as benchmark_router
from fastapi.responses import HTMLResponse
from .phase2_routes import router as phase2_router
from .semantic_routes import router as semantic_router
from .trip_routes import router as trips_router
from .stream_router import router as stream_router 
from uuid import uuid4
from ..orchestrator_core.trace_utils import ensure_ids
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="GraphCeylon Orchestrator",
    version="0.1.0",
    description="Tourism multi-agent orchestrator for Sri Lanka",
)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(events_router)
app.include_router(stream_router)
app.include_router(phase2_router)
app.include_router(semantic_router)
app.include_router(trips_router)
app.include_router(booking_router)
app.include_router(benchmark_router, prefix="/benchmark")

intent_parser_agent = IntentParserAgent(

    # model_dir=r"C:/Users/HP/OneDrive/Documents/graphCeylon-API/models/orchestrator/intent_multilabel_final_v4",
    # model_dir=r"/Users/dev/Desktop/graphCeylon-API/models/orchestrator/intent_multilabel_final_v5",

    # model_dir=r"C:/Users/HP/OneDrive/Documents/graphCeylon-API/models/orchestrator/intent_multilabel_final_v4",
    #model_dir=r"/Users/dev/Desktop/graphCeylon-API/models/orchestrator/intent_multilabel_final_v4",

    threshold=0.2,
    top_k_if_empty=2,
)

task_graph_builder = TaskGraphBuilder()

orchestrator = OrchestratorService(
    intent_parser=intent_parser_agent,
    task_graph_builder=task_graph_builder,
    protocol_mode="direct",
)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    with open("static/dashboard.html") as f:
        return f.read()
    
@app.get("/")
def root():
    return {"message": "GraphCeylon Orchestrator running", "status": "ok"}

@app.post("/orchestrate", response_model=OrchestrateResponse)
def orchestrate(req: OrchestrateRequest):
    req = ensure_ids(req)
    print("[trace]", req.trace_id, req.session_id, req.turn_id)
    return orchestrator.orchestrate(req)

@app.get("/trace/{session_id}")
def get_trace(session_id: str):
    sid = session_id.strip()
    return {
        "session_id": sid,
        "events": [e.model_dump() for e in orchestrator.trace_store.list(sid)],
    }
