"""
mcp_server_local.py
-------------------
MCP server over STDIO transport.
Wraps your existing local tools (booking_stub, book_hotel_flow) as MCP tools.

Run standalone:
    python mcp_server_local.py

Or let MCPToolProvider spawn it as a subprocess.

Install dep:
    pip install mcp
"""
from __future__ import annotations
import asyncio
import json
import sys
import time
from typing import Any

# MCP SDK
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult,
)

# ✅ Import your existing local tool logic
# Adjust import path if running from a different working directory
try:
    from orchestrator_core.tools.hotel_booking_tool import book_hotel_flow
    from orchestrator_core.orchestrator_service import booking_stub
    from orchestrator_core.runtime.tools.models import ToolCall
except ImportError:
    # Fallback stubs for isolated testing
    def book_hotel_flow(call):  # type: ignore
        args = call.args if hasattr(call, "args") else call
        return {
            "ok": True,
            "status": "pricing_ready",
            "city": args.get("city", "Kandy"),
            "check_in": args.get("check_in", "2026-06-01"),
            "check_out": args.get("check_out", "2026-06-04"),
            "guests": args.get("guests", 2),
            "available_hotels": [
                {
                    "hotel_id": "HTL001",
                    "name": "Sigiriya Eco Resort",
                    "room_type": "Deluxe Room",
                    "price_lkr": 22000,
                    "meal_plan": "Breakfast Included",
                },
            ],
            "message": "Select a hotel to proceed.",
        }

    def booking_stub(call):  # type: ignore
        return {
            "ok": True,
            "status": "verified",
            "booking_id": "BK-STUB001",
            "message": "Booking confirmed (stub).",
        }

    class ToolCall:  # type: ignore
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)


# ---- Tool schemas -------------------------------------------------------

BOOK_HOTEL_SCHEMA = {
    "type": "object",
    "properties": {
        "city":       {"type": "string", "description": "Destination city"},
        "check_in":   {"type": "string", "description": "Check-in date (YYYY-MM-DD)"},
        "check_out":  {"type": "string", "description": "Check-out date (YYYY-MM-DD)"},
        "guests":     {"type": "integer", "description": "Number of guests", "default": 2},
        "budget_level": {"type": "string", "enum": ["budget", "mid", "luxury"]},
        "must_have_amenities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Required amenities e.g. ['wifi','pool']",
        },
    },
    "required": ["city", "check_in", "check_out"],
}

BOOKING_STUB_SCHEMA = {
    "type": "object",
    "properties": {
        "hotel_id":   {"type": "string"},
        "city":       {"type": "string"},
        "check_in":   {"type": "string"},
        "check_out":  {"type": "string"},
        "guests":     {"type": "integer"},
    },
    "required": ["hotel_id"],
}

# ---- Server setup -------------------------------------------------------

app = Server("graphceylon-local-tools")


@app.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(
        tools=[
            Tool(
                name="book_hotel_flow",
                description=(
                    "Search available hotels and initiate booking flow. "
                    "Returns hotel options with pricing for user selection."
                ),
                inputSchema=BOOK_HOTEL_SCHEMA,
            ),
            Tool(
                name="booking_stub",
                description=(
                    "Confirm a hotel booking (HITL stub). "
                    "Sends booking for human verification and returns confirmation."
                ),
                inputSchema=BOOKING_STUB_SCHEMA,
            ),
        ]
    )


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    t_start = time.perf_counter()

    try:
        # Build a minimal ToolCall-like object
        call = ToolCall(
            name=name,
            args=arguments,
            trace_id="mcp-stdio",
            session_id="mcp-stdio",
        )

        if name == "book_hotel_flow":
            # book_hotel_flow may be sync or async
            if asyncio.iscoroutinefunction(book_hotel_flow):
                result = await book_hotel_flow(call)
            else:
                result = await asyncio.to_thread(book_hotel_flow, call)

        elif name == "booking_stub":
            result = await asyncio.to_thread(booking_stub, call)

        else:
            result = {"ok": False, "error": f"Unknown tool: {name}"}

        latency_ms = int((time.perf_counter() - t_start) * 1000)

        # Attach transport metadata
        if isinstance(result, dict):
            result["_transport"] = "mcp_stdio"
            result["_latency_ms"] = latency_ms

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, default=str))],
            isError=False,
        )

    except Exception as e:
        latency_ms = int((time.perf_counter() - t_start) * 1000)
        err = {"ok": False, "error": str(e), "_transport": "mcp_stdio", "_latency_ms": latency_ms}
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(err))],
            isError=True,
        )


# ---- Entry point --------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())