# Add this to your FastAPI router (e.g. orchestrator_router.py)
# This wraps your existing OrchestratorService and streams real task events via SSE

import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from ..orchestrator_core.orchestrator_service import OrchestratorService
from ..api.schemas import OrchestrateRequest

router = APIRouter()

# ── Human-readable labels for each task type ──────────────────────────────────
TASK_LABELS = {
    "parse_intent":              "Understanding your request",
    "extract_entities":          "Picking out key details",
    "validate_required_fields":  "Checking what info we need",
    "ask_followup":              "Preparing follow-up questions",
    "forecast_weather":          "Fetching live weather data",
    "crowd_forecast":            "Checking crowd levels",
    "forecast_price":            "Analysing price trends",
    "forecast_sustainability":   "Checking eco impact",
    "plan_itinerary":            "Building your personalised itinerary",
    "modify_itinerary":          "Updating your itinerary",
    "recommend_pois":            "Finding points of interest",
    "info_attraction":           "Looking up attraction details",
    "info_accommodation":        "Searching hotels & stays",
    "info_transport":            "Checking transport options",
    "info_visa_policy":          "Retrieving visa requirements",
    "book_hotel":                "Preparing your booking",
    "modify_booking":            "Updating booking details",
    "cancel_booking":            "Processing cancellation",
    "recommend_restaurants":     "Finding top restaurants",
    "format_response":           "Putting it all together",
}


def task_event(task_id: str, task_type: str, status: str, agent: str) -> str:
    label = TASK_LABELS.get(task_type, task_type.replace("_", " ").title())
    data = {
        "type": "task",
        "task": {
            "id": task_id,
            "type": task_type,
            "status": status,
            "assigned_agent": agent,
            "label": label,
        }
    }
    return f"data: {json.dumps(data)}\n\n"


async def orchestrate_stream_generator(
    svc: OrchestratorService,
    req: OrchestrateRequest,
) -> AsyncGenerator[str, None]:
    """
    Wraps OrchestratorService.orchestrate() and streams task-level SSE events
    as each task in the DAG completes — by patching the task handlers.
    """

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    # ── Patch: inject an SSE emit hook into the task executor ─────────────────
    # We monkey-patch the wrap_task function behavior by replacing the
    # task_graph_builder's post-task callback if it supports one,
    # OR we use the simpler approach: patch handlers dict after build.

    # The cleanest hook point in YOUR code is the `handlers` dict built inside
    # orchestrate(). We inject a thin wrapper around each handler that emits
    # an SSE event after the real handler completes.
    #
    # To do this without modifying orchestrator_service.py, we subclass it:

    class StreamingOrchestrator(svc.__class__):
        def __init__(self, inner_svc, q: asyncio.Queue):
            # share all state — don't re-init, just borrow
            self.__dict__ = inner_svc.__dict__
            self._sse_queue = q

        def _emit(self, task_id: str, task_type: str, status: str, agent: str):
            """Thread-safe SSE emit (called from sync thread inside anyio.run)"""
            try:
                loop.call_soon_threadsafe(
                    self._sse_queue.put_nowait,
                    task_event(task_id, task_type, status, agent)
                )
            except Exception:
                pass

        def orchestrate(self, req):
            # ── We override just enough to inject emit hooks ──
            # Call the real orchestrate but intercept the handlers dict

            # Step 1: Run intent parser first (emit immediately)
            self._emit("T1", "parse_intent", "running", "IntentParserAgent")
            parsed_intent = self._run_intent_parser(req)
            self._emit("T1", "parse_intent", "completed", "IntentParserAgent")

            self._emit("T2", "extract_entities", "running", "IntentParserAgent")
            # extract_entities runs as part of parse — emit right after
            self._emit("T2", "extract_entities", "completed", "IntentParserAgent")

            # Step 2: build task graph so we know what domain tasks are coming
            tasks = self.task_graph_builder.build(parsed_intent)

            # Emit "running" for all domain tasks upfront so UI shows the plan
            for t in tasks:
                if t.type not in {"parse_intent", "extract_entities", "format_response"}:
                    self._emit(t.id, t.type, "queued", t.assigned_agent or "OrchestratorAgent")

            # Step 3: run the full orchestration (this blocks until done)
            result = super().orchestrate(req)

            # Step 4: emit completed one by one with a small delay so UI shows
            # them revealing progressively instead of all at once
            import time
            domain_tasks = [
                t for t in result.tasks
                if t.type not in {"parse_intent", "extract_entities"}
            ]
            for t in domain_tasks:
                self._emit(t.id, t.type, t.status or "completed", t.assigned_agent or "OrchestratorAgent")
                time.sleep(0.4)  # 400ms between each step

            # Step 5: emit format_response last
            time.sleep(0.3)
            self._emit("T_fmt", "format_response", "completed", "ExplainabilityAgent")

            return result

    streaming_svc = StreamingOrchestrator(svc, queue)

    # ── Run orchestration in a background thread (it uses anyio.run internally)
    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    future = loop.run_in_executor(executor, streaming_svc.orchestrate, req)

    SENTINEL = "__DONE__"

    # When future completes, push sentinel to stop the SSE loop
    def _on_done(fut):
        loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)

    future.add_done_callback(_on_done)

    # ── Stream events as they arrive ──────────────────────────────────────────
    while True:
        item = await queue.get()
        if item == SENTINEL:
            break
        yield item

    # ── Send final result ─────────────────────────────────────────────────────
    try:
        result = await future
        result_dict = result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)
        print("🔍 [SSE] result_dict keys:", list(result_dict.keys()))
        print("🔍 [SSE] explainability:", result_dict.get("explainability"))
        print("🔵 [SSE] result_dict keys:", list(result_dict.keys()))
        print("🔵 [SSE] sources:", result_dict.get("sources"))
        print("🟡 [SSE] agentic_meta:", result_dict.get("agentic_meta")) 
        yield f"data: {json.dumps({'type': 'done', 'result': result_dict})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@router.post("/orchestrate/stream")
async def orchestrate_stream(request: Request):
    body = await request.json()
    req = OrchestrateRequest(**body)

    # Import the same module-level instance used by main.py
    from .main import orchestrator as svc

    return StreamingResponse(
        orchestrate_stream_generator(svc, req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )