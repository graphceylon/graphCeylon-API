"""
mcp_server_http.py
------------------
MCP server over Streamable HTTP transport (new MCP spec).
Wraps your existing remote agent calls (recommender, visa_kg) as MCP tools.

Run:
    uvicorn mcp_server_http:fastapi_app --host 0.0.0.0 --port 9100

Or add to your docker-compose alongside other services.

Install deps:
    pip install mcp fastapi uvicorn
"""
from __future__ import annotations
from fastapi import FastAPI, Request, Response
from starlette.responses import Response
import asyncio
import json
import anyio
import os
import time
from typing import Any
from starlette.responses import Response

import httpx
# from fastapi import FastAPI
from mcp.server import Server
# from mcp.server.streamable_http import StreamableHTTPServerTransport
import uuid
from mcp.server.streamable_http import StreamableHTTPServerTransport
from fastapi import FastAPI, Request
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult,
)

# ---- Config -------------------------------------------------------------

RECOMMENDER_BASE_URL = os.getenv(
    "RECOMMENDER_SERVICE_URL", "http://127.0.0.1:8003"
).rstrip("/")

VISA_KG_BASE_URL = os.getenv(
    "VISA_KG_SERVICE_URL", "http://kg_service:8000"
).rstrip("/")

# ---- Tool schemas -------------------------------------------------------

WEATHER_SCHEMA = {
    "type": "object",
    "properties": {
        "city":       {"type": "string"},
        "start_date": {"type": "string"},
        "end_date":   {"type": "string"},
        "days":       {"type": "integer"},
        "country":    {"type": "string"},
        "raw_text":   {"type": "string"},
    },
    "required": ["city"],
}

POIS_SCHEMA = {
    "type": "object",
    "properties": {
        "city":         {"type": "string"},
        "destination":  {"type": "string"},
        "days":         {"type": "integer"},
        "travel_style": {"type": "string"},
    },
}

VISA_SCHEMA = {
    "type": "object",
    "properties": {
        "nationality":   {"type": "string", "description": "Traveller's passport country"},
        "destination":   {"type": "string", "default": "Sri Lanka"},
    },
    "required": ["nationality"],
}

ACCOMMODATION_SCHEMA = {
    "type": "object",
    "properties": {
        "city":                 {"type": "string"},
        "check_in":             {"type": "string"},
        "check_out":            {"type": "string"},
        "guests":               {"type": "integer"},
        "budget_level":         {"type": "string"},
        "must_have_amenities":  {"type": "array", "items": {"type": "string"}},
    },
    "required": ["city"],
}

PLAN_ITINERARY_SCHEMA = {
    "type": "object",
    "properties": {
        "destination": {"type": "string"},
        "city":        {"type": "string"},
        "days":        {"type": "integer"},
        "start_date":  {"type": "string"},
        "travel_style":{"type": "string"},
    },
    "required": ["days"],
}

# ---- HTTP helper --------------------------------------------------------

async def _post(base_url: str, endpoint: str, payload: dict, timeout: float = 20.0) -> dict:
    url = f"{base_url}{endpoint}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json() if resp.content else {}


# ---- MCP Server ---------------------------------------------------------

app = Server("graphceylon-remote-tools")


@app.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(
        tools=[
            Tool(
                name="forecast_weather",
                description="Get weather forecast for a Sri Lanka destination.",
                inputSchema=WEATHER_SCHEMA,
            ),
            Tool(
                name="recommend_pois",
                description="Recommend points of interest for a destination.",
                inputSchema=POIS_SCHEMA,
            ),
            Tool(
                name="info_visa_policy",
                description="Get visa and entry requirements for Sri Lanka.",
                inputSchema=VISA_SCHEMA,
            ),
            Tool(
                name="info_accommodation",
                description="Search available hotels and accommodation.",
                inputSchema=ACCOMMODATION_SCHEMA,
            ),
            Tool(
                name="plan_itinerary",
                description="Generate a full travel itinerary for Sri Lanka.",
                inputSchema=PLAN_ITINERARY_SCHEMA,
            ),
        ]
    )


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    t_start = time.perf_counter()

    ROUTES: dict[str, tuple[str, str]] = {
        "forecast_weather":   (RECOMMENDER_BASE_URL, "/forecast/weather"),
        "recommend_pois":     (RECOMMENDER_BASE_URL, "/recommend/pois"),
        "plan_itinerary":     (RECOMMENDER_BASE_URL, "/itinerary/plan"),
        "info_visa_policy":   (VISA_KG_BASE_URL,     "/graphrag/visa-policy"),
        "info_accommodation": (VISA_KG_BASE_URL,     "/hotels/orchestrator/call/hotels/search"),
    }

    if name not in ROUTES:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}))],
            isError=True,
        )

    base_url, endpoint = ROUTES[name]

    # Add required fields the recommender expects
    payload = {
        "intent": name,
        "raw_text": arguments.get("raw_text", ""),  # required field
        **arguments,
    }

    try:
        result = await _post(base_url, endpoint, payload)
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        if isinstance(result, dict):
            result["_transport"] = "mcp_streamable_http"
            result["_latency_ms"] = latency_ms
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, default=str))],
            isError=False,
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"ok": False, "error": str(e), "_latency_ms": latency_ms}))],
            isError=True,
        )


# ---- ASGI app -----------------------------------------------------------

import anyio
import uuid
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

_sessions: dict = {}

async def _run_session(transport, ready_event):
    try:
        async with transport.connect() as (read, write):
            ready_event.set()  # signal that connect() is ready
            await app.run(read, write, app.create_initialization_options())
    except Exception as e:
        print(f"[MCP session error] {e}")
        ready_event.set()  # unblock even on error


async def handle_mcp(scope, receive, send):
    from starlette.requests import Request as StarletteRequest
    req = StarletteRequest(scope, receive)
    session_id = req.headers.get("mcp-session-id")

    if session_id and session_id in _sessions:
        transport = _sessions[session_id]
    else:
        session_id = session_id or str(uuid.uuid4())
        transport = StreamableHTTPServerTransport(mcp_session_id=session_id)
        _sessions[session_id] = transport

        ready_event = asyncio.Event()
        asyncio.create_task(_run_session(transport, ready_event))
        await ready_event.wait()  # wait until connect() has yielded

    await transport.handle_request(scope, receive, send)


async def handle_health(scope, receive, send):
    response = JSONResponse({"ok": True, "server": "graphceylon-mcp-streamable-http"})
    await response(scope, receive, send)


fastapi_app = Starlette(routes=[
    Route("/health", handle_health, methods=["GET"]),
    Mount("/mcp", app=handle_mcp),
])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=9101)